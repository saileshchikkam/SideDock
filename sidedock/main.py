import ctypes
import os
from ctypes import wintypes
import hashlib
import json
import re
import shutil
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path
import keyboard
from PySide6.QtCore import (
    QAbstractAnimation,
    QBuffer,
    QByteArray,
    QEasingCurve,
    QIODevice,
    QLockFile,
    QMimeData,
    QParallelAnimationGroup,
    QPoint,
    QPropertyAnimation,
    QRect,
    Qt,
    QTimer,
    QUrl,
    Signal,
)
from PySide6.QtGui import QCursor, QDesktopServices, QGuiApplication, QImage, QPixmap, QRegion
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QMenu,
    QSystemTrayIcon,
    QPushButton,
    QScrollArea,
    QSizeGrip,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from sidedock.branding import app_icon
from sidedock.diagnostics import log as diagnostic_log, start_diagnostics
from sidedock.autostart import is_enabled as autostart_enabled, set_enabled as set_autostart_enabled
from sidedock.version import __version__
from sidedock.presentation import card_kind, preview_text
from sidedock.interaction import shortcut_keys, select_paste_target, CopyBurst
from sidedock.storage import atomic_write_json, can_capture, file_digest, managed_bytes, orphaned_managed_copies, cleanup_orphaned_copies, MAX_FILE_BYTES, MAX_TEXT_BYTES, MAX_MANAGED_BYTES
from sidedock.ocr import find_tesseract, extract_text_from_png
from sidedock.composer import NoteComposer, OCRWorkspace
from sidedock.region_capture import RegionCaptureOverlay
from sidedock.theme import build_dock_qss, resolve_colors
from sidedock.widgets import (
    DraggableCard,
    QuickPastePopup,
    SettingsPanel,
)
from sidedock.windowing import (
    edge_available, is_topmost, pointer_hits_dock, raise_without_activation, set_no_activate,
)

user32 = ctypes.windll.user32
user32.GetForegroundWindow.restype = wintypes.HWND
user32.SetForegroundWindow.argtypes = [wintypes.HWND]
user32.SetForegroundWindow.restype = wintypes.BOOL
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowThreadProcessId.restype = wintypes.DWORD

def window_identity(hwnd):
    pid = wintypes.DWORD()
    tid = user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid)) if hwnd else 0
    return (hwnd, pid.value, tid) if tid else None

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}
EXCLUDE_CLIPBOARD_FMT = ctypes.windll.user32.RegisterClipboardFormatW(
    "ExcludeClipboardContentFromMonitorProcessing"
)


class DockGrabber(QWidget):
    """Top pill bar to drag SideDock vertically and snap to left or right edge."""

    def __init__(self, dock):
        super().__init__()
        self.dock = dock
        self._offset = None
        self.setFixedHeight(14)
        self.setCursor(Qt.OpenHandCursor)
        self.setToolTip("Drag to move (Left/Right edge, Top to Bottom)")

        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 2, 0, 4)
        bar = QFrame()
        bar.setObjectName("DragHandle")
        bar.setFixedSize(44, 4)
        lay.addWidget(bar, 0, Qt.AlignCenter)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._offset = event.globalPosition().toPoint() - self.dock.pos()
            self.dock.hide_timer.stop()
            self.dock.hover_watch.stop()
            self.dock._is_dragging_dock = True
            self.dock.clearMask()
            self.setCursor(Qt.ClosedHandCursor)

    def mouseMoveEvent(self, event):
        if self._offset is not None and (event.buttons() & Qt.LeftButton):
            self.dock.move(event.globalPosition().toPoint() - self._offset)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self._offset is not None:
            self._offset = None
            self.setCursor(Qt.OpenHandCursor)
            self.dock._is_dragging_dock = False
            self.dock.snap_to_side_edge()


class SideDock(QWidget):
    trigger_after_paste_signal = Signal()
    trigger_all_slots_signal = Signal()
    pick_slot_signal = Signal(int)
    ocr_ready_signal = Signal(int, str)
    ocr_error_signal = Signal(int, str)

    def __init__(self):
        super().__init__()
        self._ignore_clipboard = False
        self._capture_paused = False
        self._is_dragging_out = False
        self._is_dragging_dock = False
        self.is_pinned = False
        self.is_expanded = False
        self.copy_burst = CopyBurst()
        self._search_target = None
        self._paste_generation = 0
        self._internal_paste_popup_guard_until = 0.0
        self._hotkey_removers = []
        self._slot_removers = []
        self._editing = False
        self._ocr_request_id = 0
        self._region_overlay = None
        self._region_pending = False
        self._edge_samples = 0
        self._edge_requires_exit = False

        # 1. Local PC storage setup
        self.data_dir = Path.home() / "SideDockData"
        self.files_dir = self.data_dir / "files"
        self.files_dir.mkdir(parents=True, exist_ok=True)
        self.index_file = self.data_dir / "items.json"
        self.settings_file = self.data_dir / "settings.json"
        self.saved_items = self.load_json(self.index_file, [])
        if not isinstance(self.saved_items, list):
            raise ValueError("Invalid clipboard history; existing file has been preserved")
        self.settings = self.load_json(
            self.settings_file, {"mode": "deep_dark", "side": "right", "y": None}
        )

        if not isinstance(self.settings, dict):
            raise ValueError("Invalid settings; existing file has been preserved")
        self._capture_paused = self.settings.get("capture_paused", False)

        # 2. Frameless, always on top, hidden from taskbar
        self.setWindowFlags(
            Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAcceptDrops(True)
        self.setMinimumSize(300, 490)
        self.setMaximumSize(560, 820)

        # 3. Hidden (6px edge-peek) and expanded positions
        self.dock_width, self.dock_height = 300, 490
        self.dock_side = self.settings.get("side", "right")
        self.monitor = next((screen for screen in QGuiApplication.screens() if screen.name() == self.settings.get("monitor")), QGuiApplication.primaryScreen())
        screen = self.monitor.availableGeometry()
        default_y = screen.top() + (screen.height() - self.dock_height) // 2
        saved_y = self.settings.get("y")
        self.y_pos = saved_y if isinstance(saved_y, int) else default_y
        self.update_edge_coords()

        self.setGeometry(
            self.x_hidden, self.y_pos, self.dock_width, self.dock_height
        )
        self.setWindowOpacity(0.06)

        # 4. Smooth slide + fade animation
        self.pos_anim = QPropertyAnimation(self, b"pos")
        self.pos_anim.setDuration(220)
        self.pos_anim.setEasingCurve(QEasingCurve.OutCubic)

        self.opacity_anim = QPropertyAnimation(self, b"windowOpacity")
        self.opacity_anim.setDuration(220)
        self.opacity_anim.setEasingCurve(QEasingCurve.OutCubic)

        self.anim_group = QParallelAnimationGroup(self)
        self.anim_group.addAnimation(self.pos_anim)
        self.anim_group.addAnimation(self.opacity_anim)

        self.hide_timer = QTimer(self)
        self.hide_timer.setSingleShot(True)
        self.hide_timer.timeout.connect(self.attempt_collapse)
        self.hover_watch = QTimer(self)
        self.hover_watch.timeout.connect(self.attempt_collapse)
        self.edge_watch = QTimer(self)
        self.edge_watch.setInterval(100)
        self.edge_watch.timeout.connect(self.check_edge_hover)

        # 5. Rounded glass container
        self.container = QFrame(self)
        self.container.setObjectName("DockContainer")
        self.container.setGeometry(0, 0, self.dock_width, self.dock_height)

        layout = QVBoxLayout(self.container)
        layout.setContentsMargins(13, 6, 13, 11)
        layout.setSpacing(9)

        # Top drag grabber bar
        layout.addWidget(DockGrabber(self))

        # Header with Capture, Clear, Pin, and Close buttons
        header = QHBoxLayout()
        header.setSpacing(5)
        mark = QLabel()
        mark.setPixmap(QApplication.instance().windowIcon().pixmap(24, 24))
        title = QLabel("SideDock")
        title.setObjectName("BrandTitle")
        self.capture_status = QLabel()
        self.capture_status.setObjectName("StatusLabel")
        self.update_capture_status()

        capture_btn = QPushButton("Screenshot")
        capture_btn.setToolTip("Capture a screen region using Windows Snipping Tool")
        capture_btn.setObjectName("CaptureBtn")
        capture_btn.setCursor(Qt.PointingHandCursor)
        capture_btn.clicked.connect(self.trigger_capture)

        ocr_btn = QPushButton("Text OCR")
        ocr_btn.setObjectName("HeaderBtn")
        ocr_btn.setCursor(Qt.PointingHandCursor)
        ocr_btn.setToolTip("Select a screen region, recognize English text offline, and save as an editable card (requires Tesseract)")
        ocr_btn.clicked.connect(self.trigger_ocr_capture)

        clear_btn = QPushButton("Clear")
        clear_btn.setObjectName("HeaderBtn")
        clear_btn.setToolTip("Remove all unstarred history items (cannot be undone)")
        clear_btn.setCursor(Qt.PointingHandCursor)
        clear_btn.clicked.connect(self.clear_unpinned)

        self.pin_btn = QPushButton("Pin")
        self.pin_btn.setObjectName("HeaderBtn")
        self.pin_btn.setCheckable(True)
        self.pin_btn.setToolTip("Keep SideDock expanded until you unpin it")
        self.pin_btn.setCursor(Qt.PointingHandCursor)
        self.pin_btn.toggled.connect(self.toggle_pin)

        close_btn = QPushButton("x")
        close_btn.setObjectName("CloseBtn")
        close_btn.setFixedSize(22, 22)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setToolTip("Quit SideDock")
        close_btn.setAccessibleName("Quit SideDock")
        close_btn.clicked.connect(QApplication.quit)

        header.addWidget(mark)
        header.addWidget(title)
        header.addStretch()
        header.addWidget(self.capture_status)
        header.addWidget(close_btn)
        layout.addLayout(header)
        toolbar = QHBoxLayout()
        toolbar.setSpacing(5)
        toolbar.addWidget(capture_btn, 2)
        toolbar.addWidget(ocr_btn, 2)
        toolbar.addWidget(clear_btn, 1)
        toolbar.addWidget(self.pin_btn, 1)
        layout.addLayout(toolbar)

        # Stacked pages: [0] Items View, [1] Settings View
        self.pages = QStackedWidget()
        items_page = QWidget()
        items_layout = QVBoxLayout(items_page)
        items_layout.setContentsMargins(0, 0, 0, 0)
        items_layout.setSpacing(8)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search your clipboard.")
        self.search_input.setAccessibleName("Search clipboard")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.mousePressEvent = self.on_search_click
        self.search_input.setToolTip("Find text, notes, image cards and file names")
        self.search_input.textChanged.connect(self.refresh_list)
        items_layout.addWidget(self.search_input)
        add_row = QHBoxLayout()
        add_row.addStretch()
        self.add_note_button = QPushButton("+ Add Note")
        self.add_note_button.setObjectName("NoteBtn")
        self.add_note_button.setToolTip("Create a local text note without using the clipboard")
        self.add_note_button.setCursor(Qt.PointingHandCursor)
        self.add_note_button.clicked.connect(lambda: self.open_note_editor())
        add_row.addWidget(self.add_note_button)
        items_layout.addLayout(add_row)
        self.history_status = QLabel()
        self.history_status.setObjectName("StatusLabel")
        items_layout.addWidget(self.history_status)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.horizontalScrollBar().setEnabled(False)
        self.scroll.setStyleSheet("background: transparent;")

        self.list_widget = QWidget()
        self.list_widget.setStyleSheet("background: transparent;")
        self.list_layout = QVBoxLayout(self.list_widget)
        self.list_layout.setContentsMargins(0, 0, 6, 0)
        self.list_layout.setSpacing(8)
        self.list_layout.addStretch()

        self.scroll.setWidget(self.list_widget)
        items_layout.addWidget(self.scroll)

        self.settings_panel = SettingsPanel(
            self.settings,
            self.on_settings_changed,
            self.set_dock_side,
            lambda: self.pages.setCurrentIndex(0),
        )
        self.settings_panel.add_capture_control(self._capture_paused, self.set_capture_paused)
        self.settings_panel.add_shortcut_controls(self.on_shortcut_settings_changed)
        self.pages.addWidget(items_page)
        self.settings_panel.add_storage_controls(self.open_data_folder, self.clean_unused_copies)
        settings_scroll = QScrollArea()
        settings_scroll.setWidgetResizable(True)
        settings_scroll.setFrameShape(QFrame.NoFrame)
        settings_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        settings_scroll.setWidget(self.settings_panel)
        self.pages.addWidget(settings_scroll)
        self.note_composer = NoteComposer(self.save_composed_note, self.cancel_note_editor)
        self.pages.addWidget(self.note_composer)
        self.ocr_workspace = OCRWorkspace(self.start_region_ocr, self.ocr_from_clipboard,
                                          self.ocr_from_recent, self.leave_ocr_workspace)
        self.pages.addWidget(self.ocr_workspace)
        layout.addWidget(self.pages)

        # Bottom bar: mirrors resize grip & Settings ? depending on Left/Right edge
        self.bottom_bar = QHBoxLayout()
        self.bottom_bar.setContentsMargins(0, 0, 0, 0)
        self.grip = QSizeGrip(self)
        self.grip.setFixedSize(16, 16)
        self.grip.setToolTip("Drag to resize SideDock")

        self.gear_btn = QPushButton("Settings ?")
        self.gear_btn.setObjectName("GearBtn")
        self.gear_btn.setCursor(Qt.PointingHandCursor)
        self.gear_btn.setToolTip("Themes, monitor position, keyboard shortcuts and privacy")
        self.gear_btn.clicked.connect(self.toggle_settings)

        self.update_footer_layout()
        layout.addLayout(self.bottom_bar)

        self.apply_theme()
        self.refresh_list()

        # 6. Reliable Windows clipboard watcher
        self.clipboard = QApplication.clipboard()
        self._last_clip_seq = ctypes.windll.user32.GetClipboardSequenceNumber()
        self.clip_timer = QTimer(self)
        self.clip_timer.timeout.connect(self.check_clipboard)
        self.clip_timer.start(250)
        QApplication.instance().aboutToQuit.connect(self.unregister_hotkeys)

        # 7. Quick-Paste 8s popup + hotkeys
        self.quick_popup = QuickPastePopup(self.paste_item_now)
        self.quick_popup.apply_theme(self.colors)
        self.ocr_ready_signal.connect(self.on_ocr_ready)
        self.ocr_error_signal.connect(self.on_ocr_error)
        self.trigger_after_paste_signal.connect(self.open_remaining_popup)
        self.trigger_all_slots_signal.connect(self.open_all_slots_popup)
        self.pick_slot_signal.connect(self.quick_popup.pick_number)

        self.quick_popup.slots_changed.connect(self.sync_slot_hotkeys)
        self.setup_tray()
        self.refresh_storage_usage()
        self.register_hotkeys()
        app = QApplication.instance()
        app.screenRemoved.connect(self.on_screen_removed)
        app.screenAdded.connect(self.on_screen_added)
        for monitor in app.screens():
            self.on_screen_added(monitor)
        self.update_monitor_mask()
        self.health_timer = QTimer(self)
        self._health_sample = time.monotonic(), time.process_time()
        self.health_timer.timeout.connect(self.log_heartbeat)
        self.health_timer.start(60_000)
        self.log_dock_state("initialized")

    def log_heartbeat(self):
        previous_wall, previous_cpu = self._health_sample
        now, cpu = self._health_sample = time.monotonic(), time.process_time()
        elapsed = now - previous_wall
        diagnostic_log.info("event loop interval=%.2fs process_cpu=%.2fs", elapsed, cpu - previous_cpu)
        self.log_dock_state("heartbeat")

    def log_dock_state(self, reason):
        screen = self.monitor
        hwnd = int(self.winId())
        diagnostic_log.info(
            "dock reason=%s visible=%s topmost=%s expanded=%s geometry=%s "
            "screen=%s work_area=%s dpi=%s scale=%s clipboard_timer=%s hover_timer=%s edge_timer=%s",
            reason, self.isVisible(), is_topmost(hwnd), self.is_expanded, self.geometry().getRect(),
            screen.geometry().getRect() if screen else None,
            screen.availableGeometry().getRect() if screen else None,
            screen.logicalDotsPerInch() if screen else None,
            screen.devicePixelRatio() if screen else None,
            self.clip_timer.isActive(), self.hover_watch.isActive(), self.edge_watch.isActive(),
        )

    def setup_tray(self):
        self.tray = QSystemTrayIcon(QApplication.instance().windowIcon(), self)
        self.tray.setToolTip(f"SideDock {__version__}")
        self.tray_menu = QMenu()
        self.tray_menu.addAction("Show dock", self.show_from_tray)
        self.tray_pause = self.tray_menu.addAction("Pause clipboard capture")
        self.tray_pause.setCheckable(True)
        self.tray_pause.setChecked(self._capture_paused)
        self.tray_pause.toggled.connect(self.set_capture_paused)
        self.tray_shortcuts = self.tray_menu.addAction("Enable SideDock shortcuts")
        self.tray_shortcuts.setCheckable(True)
        self.tray_shortcuts.setChecked(self.settings.get("shortcuts_enabled", True))
        self.tray_shortcuts.toggled.connect(self.set_shortcuts_enabled)
        shortcut_menu = self.tray_menu.addMenu("Shortcut preset")
        shortcut_menu.addAction("Classic: Ctrl+Shift+V", lambda: self.set_shortcut_preset("classic"))
        shortcut_menu.addAction("Alternative: Ctrl+Alt+V", lambda: self.set_shortcut_preset("alternative"))
        self.tray_startup = self.tray_menu.addAction("Start with Windows")
        self.tray_startup.setCheckable(True)
        try:
            self.tray_startup.setChecked(autostart_enabled())
        except OSError:
            self.tray_startup.setEnabled(False)
        self.tray_startup.toggled.connect(self.toggle_autostart)
        self.tray_menu.addSeparator()
        self.tray_menu.addAction(f"SideDock {__version__}").setEnabled(False)
        self.tray_menu.addAction("Quit SideDock", QApplication.quit)
        self.tray.setContextMenu(self.tray_menu)
        self.tray.activated.connect(lambda reason: self.show_from_tray() if reason == QSystemTrayIcon.Trigger else None)
        self.tray.show()

    def toggle_autostart(self, enabled):
        try:
            set_autostart_enabled(enabled)
        except OSError as exc:
            self.tray_startup.blockSignals(True)
            self.tray_startup.setChecked(not enabled)
            self.tray_startup.blockSignals(False)
            QMessageBox.warning(None, "SideDock", f"Could not change startup: {exc}")

    def show_from_tray(self):
        self.show()
        self.expand()

    def unregister_hotkeys(self):
        for remove in self._slot_removers + self._hotkey_removers:
            try:
                remove()
            except (KeyError, ValueError):
                pass
        self._slot_removers.clear()
        self._hotkey_removers.clear()

    def shortcut_keys(self):
        return shortcut_keys(self.settings.get("shortcut_preset"))

    def set_shortcut_preset(self, preset):
        self.settings["shortcut_preset"] = preset
        self.settings_panel.sync_shortcut_controls()
        self.save_json(self.settings_file, self.settings)
        self.quick_popup.dismiss()
        self.register_hotkeys()

    def register_hotkeys(self):
        self.unregister_hotkeys()
        if not self.settings.get("shortcuts_enabled", True):
            return
        try:
            self._hotkey_removers.append(keyboard.add_hotkey("ctrl+v", self.on_ctrl_v, suppress=False))
            self._hotkey_removers.append(keyboard.add_hotkey(self.shortcut_keys()[0], lambda: self.trigger_all_slots_signal.emit(), suppress=True))
            self.sync_slot_hotkeys()
        except (ValueError, OSError):
            self.unregister_hotkeys()
            diagnostic_log.error("Unable to register shortcuts")

    def sync_slot_hotkeys(self):
        for remove in self._slot_removers:
            try:
                remove()
            except (KeyError, ValueError):
                pass
        self._slot_removers.clear()
        if not self.settings.get("shortcuts_enabled", True):
            return
        try:
            for number in self.quick_popup.slot_map:
                self._slot_removers.append(keyboard.add_hotkey(f"{self.shortcut_keys()[1]}+{number}", lambda n=number: self.pick_slot_signal.emit(n), suppress=True))
        except (ValueError, OSError):
            diagnostic_log.error("Unable to register popup shortcuts")

    def set_shortcuts_enabled(self, enabled):
        self.settings["shortcuts_enabled"] = enabled
        if not enabled:
            # An explicit opt-out cancels any pending rapid-copy offer.
            self.copy_burst.clear()
        self.settings_panel.sync_shortcut_controls()
        if hasattr(self, "tray_shortcuts"):
            self.tray_shortcuts.blockSignals(True)
            self.tray_shortcuts.setChecked(enabled)
            self.tray_shortcuts.blockSignals(False)
        self.save_json(self.settings_file, self.settings)
        self.quick_popup.dismiss()
        self.register_hotkeys()

    def on_shortcut_settings_changed(self, kind, value):
        if kind == "enabled":
            self.set_shortcuts_enabled(bool(value))
        elif kind == "preset":
            self.set_shortcut_preset(value)
        self.refresh_list()

    def on_screen_added(self, screen):
        screen.availableGeometryChanged.connect(self.on_monitor_geometry_changed)
        screen.geometryChanged.connect(self.on_monitor_geometry_changed)
        screen.logicalDotsPerInchChanged.connect(self.on_monitor_geometry_changed)
        if self.monitor is None or (
            self.monitor != screen and screen.name() == self.settings.get("monitor")
        ):
            self.monitor = screen
            self.on_monitor_geometry_changed()

    def on_screen_removed(self, screen):
        if self.monitor == screen:
            screens = [item for item in QGuiApplication.screens() if item != screen]
            primary = QGuiApplication.primaryScreen()
            self.monitor = primary if primary in screens else next(iter(screens), None)
            self.on_monitor_geometry_changed()

    def on_monitor_geometry_changed(self, *_):
        if self.monitor is None:
            return
        self.update_edge_coords()
        self.anim_group.stop()
        self._edge_samples = 0
        self.move(self.x_shown if self.is_expanded else self.x_hidden, self.y_pos)
        self.setWindowOpacity(0.98 if self.is_expanded else 0.06)
        self.update_monitor_mask()
        self.log_dock_state("monitor geometry")

    def update_monitor_mask(self):
        if not hasattr(self, "monitor") or self.monitor is None:
            return
        visible = self.geometry().intersected(self.monitor.availableGeometry())
        if visible == self.geometry():
            self.clearMask()
        elif not visible.isEmpty():
            self.setMask(QRegion(visible.translated(-self.x(), -self.y())))

    def moveEvent(self, event):
        if not self._is_dragging_dock:
            self.update_monitor_mask()
        super().moveEvent(event)

    def sync_list_width(self):
        vw = self.scroll.viewport().width()
        if vw > 40:
            self.list_widget.setFixedWidth(vw)

    def update_footer_layout(self):
        while self.bottom_bar.count():
            self.bottom_bar.takeAt(0)
        if self.dock_side == "left":
            self.bottom_bar.addWidget(self.gear_btn, 0, Qt.AlignLeft | Qt.AlignBottom)
            self.bottom_bar.addStretch()
            self.bottom_bar.addWidget(self.grip, 0, Qt.AlignRight | Qt.AlignBottom)
        else:
            self.bottom_bar.addWidget(self.grip, 0, Qt.AlignLeft | Qt.AlignBottom)
            self.bottom_bar.addStretch()
            self.bottom_bar.addWidget(self.gear_btn, 0, Qt.AlignRight | Qt.AlignBottom)

    def update_edge_coords(self):
        if self.monitor is None:
            return
        screen = self.monitor.availableGeometry()
        min_y = screen.top() + 8
        max_y = max(min_y, screen.top() + screen.height() - self.dock_height - 8)
        self.y_pos = max(min_y, min(self.y_pos, max_y))

        if self.dock_side == "left":
            self.x_shown = screen.left() + 12
            self.x_hidden = screen.left() - self.dock_width + 6
        else:
            right_edge = screen.left() + screen.width()
            self.x_shown = right_edge - self.dock_width - 12
            self.x_hidden = right_edge - 6

    def set_dock_side(self, side):
        self.dock_side = side
        self.settings["side"] = side
        self.update_edge_coords()
        self.update_footer_layout()
        self.save_json(self.settings_file, self.settings)
        self.expand()

    def snap_to_side_edge(self):
        self.monitor = QGuiApplication.screenAt(QCursor.pos()) or self.monitor
        self.settings["monitor"] = self.monitor.name()
        screen = self.monitor.availableGeometry()
        center_x = self.x() + self.dock_width // 2
        self.dock_side = "left" if center_x < screen.center().x() else "right"
        self.y_pos = self.y()
        self.update_edge_coords()
        self.update_footer_layout()

        self.settings["side"] = self.dock_side
        self.settings["y"] = self.y_pos
        self.save_json(self.settings_file, self.settings)
        self.settings_panel.sync_buttons()
        self.expand()

    def load_json(self, path, default):
        if not path.exists():
            return default
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            raise ValueError(f"Cannot read {path.name}; existing file has been preserved") from exc

    def save_json(self, path, data):
        atomic_write_json(path, data)

    def update_capture_status(self):
        self.capture_status.setText("PAUSED" if self._capture_paused else "")
        self.capture_status.setToolTip("Automatic clipboard capture paused" if self._capture_paused else "Clipboard capture active; data stays on this PC")

    def set_capture_paused(self, paused):
        self._capture_paused = paused
        self.update_capture_status()
        self.settings_panel.capture_button.blockSignals(True)
        self.settings_panel.capture_button.setChecked(paused)
        self.settings_panel.capture_button.blockSignals(False)
        if hasattr(self, "tray_pause"):
            self.tray_pause.blockSignals(True)
            self.tray_pause.setChecked(paused)
            self.tray_pause.blockSignals(False)
        self._last_clip_seq = user32.GetClipboardSequenceNumber()
        self._ignore_clipboard = False
        self.settings["capture_paused"] = paused
        self.copy_burst.clear()
        self.quick_popup.dismiss()
        self.save_json(self.settings_file, self.settings)

    def apply_theme(self, drag_highlight=False):
        self.colors = resolve_colors(self.settings)
        self.container.setStyleSheet(build_dock_qss(self.colors, drag_highlight))
        if hasattr(self, "quick_popup"):
            self.quick_popup.apply_theme(self.colors)

    def on_settings_changed(self):
        self.save_json(self.settings_file, self.settings)
        self.apply_theme()
        self.refresh_list()

    def toggle_settings(self):
        self.pages.setCurrentIndex(1 if self.pages.currentIndex() == 0 else 0)
        self.refresh_storage_usage()

    def _enable_editor_focus(self):
        """Allow keyboard focus while editing within the dock."""
        self._editing = True
        self.hide_timer.stop()
        self.hover_watch.stop()
        self.anim_group.stop()
        self.move(self.x_shown, self.y_pos)
        self.is_expanded = True
        self.setWindowOpacity(0.98)
        self.edge_watch.stop()
        self.show()
        set_no_activate(int(self.winId()), False)
        self.activateWindow()
        self.note_composer.editor.setFocus(Qt.OtherFocusReason)

    def open_note_editor(self, initial="", source="note"):
        if not can_capture(self.saved_items):
            if source == "ocr":
                self.ocr_workspace.set_status("History is full. Remove a card before saving.")
                self.pages.setCurrentIndex(3)
            else:
                self.history_status.setText("HISTORY FULL - remove an item first")
            return
        self.note_composer.set_content(initial, source)
        self.pages.setCurrentIndex(2)
        self._enable_editor_focus()

    def _finish_editing(self):
        self._editing = False
        self.note_composer.editor.clearFocus()
        self.restore_no_activate()
        self.pages.setCurrentIndex(0)
        self.refresh_list()
        if self.is_expanded:
            self.hover_watch.start(150)

    def cancel_note_editor(self):
        self._finish_editing()

    def save_composed_note(self, content, source):
        if not content.strip():
            self.note_composer.show_error("Write some text before saving.")
            return
        if len(content.encode("utf-8")) > MAX_TEXT_BYTES:
            self.note_composer.show_error("Maximum note size is 256 KiB.")
            return
        if not can_capture(self.saved_items):
            self.note_composer.show_error("History is full. Remove a card first.")
            return
        entry = ({"type": "text", "content": content, "source": "ocr"}
                 if source == "ocr" else {"type": "note", "content": content})
        try:
            self.record_new_item(entry, rapid=False)
        except (OSError, ValueError) as exc:
            self.note_composer.show_error(f"Unable to save note: {exc}")
            return
        self._finish_editing()

    def refresh_storage_usage(self):
        try:
            total = managed_bytes(self.files_dir)
            orphaned = orphaned_managed_copies(self.files_dir, self.saved_items)
            mb = total / (1024 * 1024)
            self.settings_panel.set_storage_usage(f"{len(self.saved_items)} saved items � {mb:.1f} MiB managed copies � {len(orphaned)} unused copies")
        except OSError:
            self.settings_panel.set_storage_usage("Storage usage unavailable")

    def open_data_folder(self):
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.data_dir)))

    def clean_unused_copies(self):
        candidates = orphaned_managed_copies(self.files_dir, self.saved_items)
        if not candidates:
            QMessageBox.information(self, "SideDock", "No unused managed copies found. Your saved history has not been changed.")
            return
        answer = QMessageBox.question(self, "Clean unused copies",
            f"Delete {len(candidates)} unreferenced SideDock-managed file copies? Saved cards and original source files will be preserved.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if answer != QMessageBox.Yes:
            return
        try:
            count = cleanup_orphaned_copies(self.files_dir, self.saved_items)
        except OSError as exc:
            QMessageBox.warning(self, "SideDock", f"Some copies could not be removed: {exc}")
        else:
            QMessageBox.information(self, "SideDock", f"Removed {count} unused managed copies.")
        self.refresh_storage_usage()

    def clear_unpinned(self):
        kept = [item for item in self.saved_items if item.get("pinned")]
        removed = [item for item in self.saved_items if not item.get("pinned")]
        self.save_json(self.index_file, kept)
        self.saved_items = kept
        self.copy_burst.clear()
        self.quick_popup.dismiss()
        for item in removed:
            self.remove_managed_file(item)
        self.refresh_list()
        self.refresh_storage_usage()

    def remove_managed_file(self, item):
        if item["type"] in ("image", "file"):
            p = Path(item["path"])
            if p.parent == self.files_dir and not any(other.get("path") == str(p) for other in self.saved_items):
                try:
                    p.unlink(missing_ok=True)
                except OSError:
                    diagnostic_log.error("Could not delete stored copy")

    def showEvent(self, event):
        super().showEvent(event)
        self.restore_no_activate()
        self.apply_theme()
        if not self.is_expanded:
            self.edge_watch.start()
        QTimer.singleShot(0, self.sync_list_width)
        self.log_dock_state("show")

    def hideEvent(self, event):
        self.edge_watch.stop()
        self._edge_samples = 0
        super().hideEvent(event)
        self.log_dock_state("hide")

    def on_search_click(self, event):
        identity = window_identity(user32.GetForegroundWindow())
        if identity and identity[1] != os.getpid():
            self._search_target = identity
        set_no_activate(int(self.winId()), False)
        self.activateWindow()
        QLineEdit.mousePressEvent(self.search_input, event)

    def restore_no_activate(self):
        set_no_activate(int(self.winId()), True)

    def on_ctrl_v(self):
        # Windows native Ctrl+V is never suppressed or replaced. Do not
        # intercept the distinct Ctrl+Shift+V / Ctrl+Alt+V shortcuts here.
        if keyboard.is_pressed("shift") or keyboard.is_pressed("alt"):
            return
        self.trigger_after_paste_signal.emit()

    def open_remaining_popup(self):
        # This handler runs in Qt's UI thread; wait for the native paste.
        QTimer.singleShot(140, self.show_recent_copies_popup)

    def show_recent_copies_popup(self):
        if (not self.settings.get("shortcuts_enabled", True)
                or self._editing
                or time.monotonic() < self._internal_paste_popup_guard_until):
            return
        # Offer previous copies ONLY for a fresh, rapid multi-copy batch.
        # Native Ctrl+V already pasted slot 1 (the most recent copy).
        # Never show old saved history or show the newest item again.
        remaining = self.copy_burst.consume_remaining(time.monotonic())
        if remaining:
            self.quick_popup.show_slots(
                remaining, f"Also copied ({self.shortcut_keys()[2]}+2/3)"
            )

    def open_all_slots_popup(self):
        items = self.copy_burst.items if self.copy_burst.items else self.saved_items[:3]
        numbered = list(enumerate(items[:3], start=1))
        if not self.settings.get("shortcuts_enabled", True):
            return
        self.quick_popup.show_slots(numbered, f"Quick Paste ({self.shortcut_keys()[2]}+1/2/3)")

    def paste_item_now(self, item):
        if item["type"] in ("image", "file") and not Path(item["path"]).exists():
            return
        # Explicitly choosing a card/Quick-Paste item completes the manual
        # workflow; do not surprise the user with a later Ctrl+V offer.
        self.copy_burst.clear()
        if item["type"] == "image":
            self.copy_image_back(item["path"])
        elif item["type"] == "file":
            self.copy_file_back(item["path"])
        else:
            self.copy_text_back(item["content"])
        self._paste_generation += 1
        generation = self._paste_generation
        foreground = window_identity(user32.GetForegroundWindow())
        target = select_paste_target(foreground, self._search_target, os.getpid())
        self._search_target = None
        if target is None or window_identity(target[0]) != target:
            return
        self.restore_no_activate()
        foreground = window_identity(user32.GetForegroundWindow())
        if foreground and foreground[1] == os.getpid():
            user32.SetForegroundWindow(target[0])
        def send_if_target():
            if generation == self._paste_generation and window_identity(user32.GetForegroundWindow()) == target:
                self._internal_paste_popup_guard_until = time.monotonic() + 0.75
                keyboard.send("ctrl+v")
        QTimer.singleShot(80, send_if_target)

    def set_drag_out_state(self, active):
        self._is_dragging_out = active
        if active:
            self.hide_timer.stop()
        elif not self.is_pinned and not self.underMouse():
            self.hide_timer.start(300)

    def resizeEvent(self, event):
     self.dock_width = self.width()
     self.dock_height = self.height()
     self.container.setGeometry(0, 0, self.dock_width, self.dock_height)
     self.sync_list_width()
     if not self._is_dragging_dock:
         self.y_pos = self.y()
         self.update_edge_coords()
     if self.is_expanded and (QApplication.mouseButtons() & Qt.LeftButton):
         self.hide_timer.stop()
         self.anim_group.stop()
         self.setWindowOpacity(0.98)
     self.update_monitor_mask()
     super().resizeEvent(event)

    def trigger_ocr_capture(self):
        """Open OCR controls inside SideDock, never the external Snipping Tool."""
        self.ocr_workspace.set_status(
            "Select a region, clipboard image or saved screenshot. Processing stays local."
        )
        self.pages.setCurrentIndex(3)
        self.expand()

    def leave_ocr_workspace(self):
        self.pages.setCurrentIndex(0)
        self.refresh_list()

    def start_region_ocr(self):
        self.ocr_workspace.set_status("Drag across the screen to select text. Esc cancels.")
        self._region_pending = True
        self.collapse(force=True)
        QTimer.singleShot(320, self._show_region_overlay)

    def _show_region_overlay(self):
        self._region_pending = False
        screen = QGuiApplication.screenAt(QCursor.pos()) or self.monitor
        if screen is None:
            self.ocr_workspace.set_status("No active screen found.")
            self.expand()
            return
        overlay = RegionCaptureOverlay(screen)
        self._region_overlay = overlay
        overlay.captured.connect(self._on_region_captured)
        overlay.cancelled.connect(self._on_region_cancelled)
        overlay.show()
        overlay.raise_()
        overlay.activateWindow()
        overlay.setFocus(Qt.OtherFocusReason)

    def _on_region_cancelled(self):
        self._region_overlay = None
        self.ocr_workspace.set_status("Selection cancelled.")
        self.expand()

    def _on_region_captured(self, image):
        self._region_overlay = None
        self.expand()
        self._start_ocr_worker(image)

    def ocr_from_clipboard(self):
        mime = self.clipboard.mimeData()
        if mime is None or not mime.hasImage():
            self.ocr_workspace.set_status("No image is on the clipboard. Copy a screenshot first.")
            return
        self._start_ocr_worker(QImage(mime.imageData()))

    def ocr_from_recent(self):
        saved_image = next((item for item in self.saved_items
                            if item.get("type") == "image"
                            and Path(item.get("path", "")).is_file()), None)
        if saved_image is None:
            self.ocr_workspace.set_status("No saved image found in SideDock history.")
            return
        self._start_ocr_worker(QImage(saved_image["path"]))

    def _start_ocr_worker(self, image):
        if image.isNull():
            self.ocr_workspace.set_status("The selected image could not be read.")
            return
        engine = find_tesseract()
        if not engine:
            self.ocr_workspace.set_status(
                "OCR engine unavailable in this installation. Use the new build with "
                "bundled OCR or install Tesseract locally."
            )
            return
        encoded = QByteArray()
        buffer = QBuffer(encoded)
        buffer.open(QIODevice.WriteOnly)
        saved = image.save(buffer, "PNG")
        buffer.close()
        if not saved:
            self.ocr_workspace.set_status("Could not prepare image for OCR.")
            return
        png = bytes(encoded)
        self._ocr_request_id += 1
        current = self._ocr_request_id
        self.ocr_workspace.set_status("Recognizing text locally.")
        def worker():
            try:
                text = extract_text_from_png(png, executable=engine)
                self.ocr_ready_signal.emit(current, text)
            except (OSError, ValueError, subprocess.SubprocessError) as exc:
                self.ocr_error_signal.emit(current, str(exc))
        threading.Thread(target=worker, daemon=True).start()

    def on_ocr_ready(self, request_id, content):
        if request_id != self._ocr_request_id:
            return
        if not content.strip():
            self.ocr_workspace.set_status("No readable text was found. Try a larger selection.")
            return
        self.open_note_editor(initial=content, source="ocr")

    def on_ocr_error(self, request_id, message):
        if request_id == self._ocr_request_id:
            self.ocr_workspace.set_status("OCR failed: " + message[:180])

    def trigger_capture(self):
        self.collapse(force=True)
        QTimer.singleShot(
            260, lambda: subprocess.Popen(["explorer", "ms-screenclip:"])
        )

    def check_edge_hover(self):
        if self.monitor is None or self._region_pending or self._region_overlay is not None:
            self._edge_samples = 0
            return
        screen = self.monitor.availableGeometry()
        pos = QCursor.pos()
        x = screen.left() if self.dock_side == "left" else self.x_hidden
        strip = QRect(x, self.y_pos, 6, self.dock_height)
        if not screen.contains(pos) or not strip.contains(pos):
            self._edge_samples = 0
            self._edge_requires_exit = False
            return
        if (
            self._edge_requires_exit or self.anim_group.state() == QAbstractAnimation.State.Running
            or not edge_available(int(self.winId()), polling=True)
        ):
            self._edge_samples = 0
            return
        self._edge_samples += 1
        if self._edge_samples >= 2:
            diagnostic_log.info("edge fallback pointer_hits_dock=%s", pointer_hits_dock(int(self.winId())))
            self.expand(source="edge polling")

    def is_cursor_in_dock_zone(self):
        if self.monitor is None:
            return False
        pos = QCursor.pos()
        screen = self.monitor.availableGeometry()
        in_y = self.y_pos <= pos.y() <= self.y_pos + self.dock_height
        if not in_y:
            return False
        if self.dock_side == "left":
            return screen.left() - 2 <= pos.x() <= self.x_shown + self.dock_width
        return self.x_shown <= pos.x() <= screen.right() + 2

    def attempt_collapse(self):
            if (
                not self.is_expanded
                or self.is_pinned
                or self._editing
                or self._is_dragging_out
                or self._is_dragging_dock
                or (QApplication.mouseButtons() & Qt.LeftButton)
            ):
                return
            if self.is_cursor_in_dock_zone():
                if not self.hover_watch.isActive():
                    self.hover_watch.start(150)
                return
            self.hover_watch.stop()
            self.collapse()

    def enterEvent(self, event):
        self.hide_timer.stop()
        if (
            not self.is_expanded and not self._edge_requires_exit
            and not self._region_pending and self._region_overlay is None
            and self.anim_group.state() != QAbstractAnimation.State.Running
            and edge_available(int(self.winId()))
        ):
            self.expand(source="window hover")
        super().enterEvent(event)

    def leaveEvent(self, event):
        if self.is_expanded and not self.is_pinned and not self._editing and not self._is_dragging_out and not self._is_dragging_dock:
            self.hide_timer.start(300)
        super().leaveEvent(event)

    def dragEnterEvent(self, event):
        if self._is_dragging_out:
            return
        mime = event.mimeData()
        if mime.hasUrls() or mime.hasImage() or mime.hasText():
            event.acceptProposedAction()
            self.hide_timer.stop()
            self.apply_theme(drag_highlight=True)
            if not self.is_expanded:
                self.expand()

    def dragLeaveEvent(self, event):
        self.apply_theme(drag_highlight=False)
        if not self.is_pinned and not self._is_dragging_out:
            self.hide_timer.start(300)

    def dropEvent(self, event):
        if self._is_dragging_out:
            return
        self.apply_theme(drag_highlight=False)
        # Dragging items into the dock is not a Ctrl+C copying burst.
        self.safe_process_mime(event.mimeData(), rapid=False)
        event.acceptProposedAction()

    def toggle_pin(self, checked):
        self.is_pinned = checked
        if not checked and not self.underMouse():
            self.hide_timer.start(300)

    def expand(self, source="dock"):
        self.edge_watch.stop()
        self._edge_samples = 0
        self.hide_timer.stop()
        if not self.is_expanded:
            self.restore_no_activate()
            raise_without_activation(int(self.winId()))
        if self.settings.get("mode") == "windows":
            previous = self.colors
            self.apply_theme()
            if self.colors != previous:
                self.refresh_list()
        self.is_expanded = True
        self.hover_watch.start(150)
        self.anim_group.stop()
        self.pos_anim.setStartValue(self.pos())
        self.pos_anim.setEndValue(QPoint(self.x_shown, self.y_pos))
        self.opacity_anim.setStartValue(self.windowOpacity())
        self.opacity_anim.setEndValue(0.98)
        self.anim_group.start()
        self.log_dock_state("expand " + source)

    def collapse(self, force=False):
        if (self.is_pinned or self._is_dragging_out or self._is_dragging_dock) and not force:
            return
        self.hover_watch.stop()
        self.hide_timer.stop()
        self._edge_samples = 0
        self._edge_requires_exit = force
        if self.isVisible():
            self.edge_watch.start()
        self.search_input.clearFocus()
        self._search_target = None
        self.restore_no_activate()
        self.is_expanded = False
        self.anim_group.stop()
        self.pos_anim.setStartValue(self.pos())
        self.pos_anim.setEndValue(QPoint(self.x_hidden, self.y_pos))
        self.opacity_anim.setStartValue(self.windowOpacity())
        self.opacity_anim.setEndValue(0.06)
        self.anim_group.start()
        self.log_dock_state("collapse")

    def check_clipboard(self):
        seq = ctypes.windll.user32.GetClipboardSequenceNumber()
        if seq == self._last_clip_seq:
            return
        self._last_clip_seq = seq

        if self._ignore_clipboard:
            self._ignore_clipboard = False
            return
        if self._capture_paused:
            return
        if ctypes.windll.user32.IsClipboardFormatAvailable(EXCLUDE_CLIPBOARD_FMT):
            return
        started = time.monotonic()
        try:
            self.safe_process_mime(self.clipboard.mimeData())
        finally:
            elapsed = time.monotonic() - started
            if elapsed >= 0.25:
                diagnostic_log.warning("slow clipboard capture elapsed=%.2fs", elapsed)

    def record_new_item(self, item, rapid=True):
        item.setdefault("pinned", False)
        self.save_json(self.index_file, [item, *self.saved_items])
        self.saved_items.insert(0, item)
        self.refresh_storage_usage()
        if rapid:
            # A new copy invalidates any still-visible previous selection.
            if self.quick_popup.slot_map:
                self.quick_popup.dismiss()
            self.copy_burst.record(item, time.monotonic())
        self.refresh_list()

    def safe_process_mime(self, mime, rapid=True):
        try:
            self.process_mime(mime, rapid=rapid)
        except (OSError, ValueError):
            diagnostic_log.error("SideDock could not capture an item")

    def process_mime(self, mime, rapid=True):
        if mime is None or not can_capture(self.saved_items):
            return
        if mime.hasUrls() and any(url.isLocalFile() for url in mime.urls()):
            for url in mime.urls():
                if not can_capture(self.saved_items) or not url.isLocalFile():
                    continue
                src = Path(url.toLocalFile())
                if not src.exists():
                    continue
                latest = self.saved_items[0] if self.saved_items else {}
                if src.is_dir():
                    if latest.get("path") != str(src):
                        self.record_new_item({"type": "file", "name": src.name, "path": str(src)}, rapid=rapid)
                    continue
                size = src.stat().st_size
                if size > MAX_FILE_BYTES or managed_bytes(self.files_dir) + size > MAX_MANAGED_BYTES:
                    continue
                digest = file_digest(src)
                kind = "image" if src.suffix.lower() in IMAGE_EXTS else "file"
                if latest.get("hash") == digest and latest.get("type") == kind and latest.get("name") == src.name:
                    continue
                dest = self.files_dir / f"{uuid.uuid4().hex}_{src.name}"
                try:
                    shutil.copy2(src, dest)
                    if dest.stat().st_size > size:
                        raise ValueError("File grew during capture")
                    self.record_new_item({"type": kind, "path": str(dest), "hash": digest, "name": src.name}, rapid=rapid)
                except (OSError, ValueError):
                    dest.unlink(missing_ok=True)
                    raise
            return

        if mime.hasImage():
            image = QImage(mime.imageData())
            if image.isNull() or image.sizeInBytes() > MAX_FILE_BYTES:
                return
            ba = QByteArray()
            buf = QBuffer(ba)
            buf.open(QIODevice.WriteOnly)
            if not image.save(buf, "PNG"):
                return
            img_bytes = bytes(ba)
            if len(img_bytes) > MAX_FILE_BYTES or managed_bytes(self.files_dir) + len(img_bytes) > MAX_MANAGED_BYTES:
                return
            img_hash = hashlib.md5(img_bytes).hexdigest()
            if self.saved_items and self.saved_items[0].get("hash") == img_hash:
                return
            file_path = self.files_dir / f"img_{uuid.uuid4().hex}.png"
            try:
                file_path.write_bytes(img_bytes)
                self.record_new_item({"type": "image", "path": str(file_path), "hash": img_hash}, rapid=rapid)
            except (OSError, ValueError):
                file_path.unlink(missing_ok=True)
                raise
            return

        if mime.hasText():
            text = mime.text()
            if not text.strip() or len(text.encode("utf-8")) > MAX_TEXT_BYTES:
                return
            if self.saved_items and self.saved_items[0].get("content") == text:
                return
            self.record_new_item({"type": "text", "content": text}, rapid=rapid)

    def matches_query(self, item, query):
        if not query:
            return True
        if item["type"] in ("text", "note"):
            return query in item["content"].lower()
        if item["type"] == "file":
            return query in item["name"].lower()
        if item["type"] == "image":
            name = item.get("name", "screenshot image").lower()
            return query in name or query in "screenshot image photo"
        return True

    def refresh_list(self):
        while self.list_layout.count() > 1:
            child = self.list_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        query = self.search_input.text().strip().lower()
        pinned = [it for it in self.saved_items if it.get("pinned")]
        unpinned = [it for it in self.saved_items if not it.get("pinned")]

        visible = [item for item in pinned + unpinned if self.matches_query(item, query)
                   and (item["type"] not in ("file", "image") or Path(item["path"]).exists())]
        self.history_status.setText(f"{len(visible)} SHOWN  �  {len(pinned)} STARRED" if query else f"{len(visible)} ITEMS  �  {len(pinned)} STARRED")
        for item in visible:
            self.render_item(item)
        if not visible:
            empty = QWidget()
            empty_layout = QVBoxLayout(empty)
            empty_layout.setContentsMargins(8, 35, 8, 15)
            heading = QLabel("No matches" if query else "Your clipboard is ready")
            heading.setObjectName("EmptyTitle")
            heading.setAlignment(Qt.AlignCenter)
            detail = QLabel("Try a different search." if query else "Copy something or drop a file here to get started.")
            detail.setObjectName("SubLabel")
            detail.setWordWrap(True)
            detail.setAlignment(Qt.AlignCenter)
            empty_layout.addWidget(heading)
            empty_layout.addWidget(detail)
            self.list_layout.insertWidget(0, empty)
            if not query and not self.saved_items:
                hint = QLabel("Quick-Paste: Ctrl+Alt+V" if self.settings.get("shortcut_preset") == "alternative" else "Quick-Paste: Ctrl+Shift+V")
                hint.setObjectName("SubLabel")
                hint.setAlignment(Qt.AlignCenter)
                hint.setToolTip("Change shortcuts in Settings")
                self.list_layout.insertWidget(1, hint)
        self.sync_list_width()

    def render_item(self, item):
        card = DraggableCard(
            item, self.colors, self.paste_item_now, self.set_drag_out_state
        )
        card.setCursor(Qt.PointingHandCursor)
        card.setToolTip("Click to copy or paste � Drag to another app")
        body = QVBoxLayout(card)
        body.setContentsMargins(10, 7, 9, 9)
        body.setSpacing(5)

        top = QHBoxLayout()
        top.setSpacing(4)
        kind = QLabel(card_kind(item))
        kind.setObjectName("CardMeta")
        kind.setAttribute(Qt.WA_TransparentForMouseEvents)
        top.addWidget(kind)
        top.addStretch()

        copied_badge = QLabel("Copied!")
        copied_badge.setStyleSheet("background: #166534; color: white; border-radius: 5px; padding: 1px 5px; font-size: 10px;")
        copied_badge.setAttribute(Qt.WA_TransparentForMouseEvents)
        copied_badge.hide()
        card.copied_badge = copied_badge
        top.addWidget(copied_badge)

        is_fav = item.get("pinned", False)
        star_btn = QPushButton("?" if is_fav else "?")
        star_btn.setFixedSize(24, 24)
        star_btn.setObjectName("CardAction")
        star_btn.setCursor(Qt.PointingHandCursor)
        star_btn.setToolTip("Remove favorite" if is_fav else "Keep as favorite")
        star_btn.setAccessibleName(star_btn.toolTip())
        star_color = "#f4f4f5" if self.colors["is_dark"] else "#27272a"
        muted = "#a1a1aa" if self.colors["is_dark"] else "#52525b"
        star_btn.setStyleSheet(f"QPushButton {{ color: {star_color if is_fav else muted}; font-size: 16px; }}")
        star_btn.clicked.connect(lambda _, it=item: self.toggle_favorite(it))
        top.addWidget(star_btn)

        remove_btn = QPushButton("x")
        remove_btn.setObjectName("CloseBtn")
        remove_btn.setFixedSize(24, 24)
        remove_btn.setCursor(Qt.PointingHandCursor)
        remove_btn.setToolTip("Remove item")
        remove_btn.setAccessibleName("Remove clipboard item")
        remove_btn.clicked.connect(lambda _, it=item: self.remove_item(it))
        top.addWidget(remove_btn)
        body.addLayout(top)

        content = QLabel()
        content.setObjectName("CardText")
        content.setTextFormat(Qt.PlainText)
        content.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        content.setMinimumWidth(0)
        content.setAttribute(Qt.WA_TransparentForMouseEvents)
        content.setStyleSheet("background: transparent; border: none; font-size: 12px;")
        if item["type"] == "image":
            max_img_w = max(90, self.dock_width - 65)
            pixmap = QPixmap(item["path"]).scaled(max_img_w, 120, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            content.setPixmap(pixmap)
        else:
            text = item["name"] if item["type"] == "file" else item["content"]
            preview = re.sub(r"(\S{20})", lambda m: m.group(1) + "\u200b", preview_text(text))
            content.setWordWrap(True)
            content.setText(preview)
        body.addWidget(content)
        self.list_layout.insertWidget(self.list_layout.count() - 1, card)

    def toggle_favorite(self, item):
        item["pinned"] = not item.get("pinned", False)
        self.save_json(self.index_file, self.saved_items)
        self.refresh_list()

    def remove_item(self, item):
        if item in self.saved_items:
            remaining = self.saved_items.copy()
            remaining.remove(item)
            self.save_json(self.index_file, remaining)
            self.saved_items = remaining
        self.copy_burst.forget(item)
        self.quick_popup.dismiss()
        self.remove_managed_file(item)
        self.refresh_list()
        self.refresh_storage_usage()

    def copy_text_back(self, text):
        self._ignore_clipboard = True
        self.clipboard.setText(text)

    def copy_image_back(self, path):
        self._ignore_clipboard = True
        self.clipboard.setImage(QImage(path))

    def copy_file_back(self, path):
        self._ignore_clipboard = True
        mime = QMimeData()
        mime.setUrls([QUrl.fromLocalFile(path)])
        self.clipboard.setMimeData(mime)

def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName("SideDock")
    app.setApplicationVersion(__version__)
    app.setWindowIcon(app_icon())
    if "--smoke-test-ocr" in sys.argv:
        # Test a true high-contrast file fixture created outside the packaged
        # executable. The OCR model must actually recognize its text.
        path_index = sys.argv.index("--smoke-test-ocr")
        sample_path = (Path(sys.argv[path_index + 1]) if path_index + 1 < len(sys.argv)
                       else Path("build/ocr-smoke-fixture.png"))
        try:
            picture = QImage(str(sample_path))
            if picture.isNull():
                raise RuntimeError(f"Unusable OCR smoke fixture: {sample_path}")
            encoded = QByteArray()
            buffer = QBuffer(encoded)
            buffer.open(QIODevice.WriteOnly)
            if not picture.save(buffer, "PNG"):
                raise RuntimeError("Could not encode OCR fixture as PNG")
            buffer.close()
            result = extract_text_from_png(bytes(encoded)).replace(" ", "").upper()
            Path("build").mkdir(exist_ok=True)
            Path("build/ocr-smoke-diagnostic.txt").write_text(
                "engine_found=" + str(bool(find_tesseract())) + "\n" +
                "recognized=" + repr(result[:150]) + "\n", encoding="utf-8",
            )
            if "SIDEDOCK" not in result:
                raise RuntimeError("Bundled OCR returned unexpected text: " + repr(result[:150]))
        except Exception:
            import traceback
            Path("build").mkdir(exist_ok=True)
            Path("build/ocr-smoke-diagnostic.txt").write_text(
                traceback.format_exc(), encoding="utf-8"
            )
            raise SystemExit(1)
        return
    if "--smoke-test" in sys.argv:
        # Exercise packaged Qt resources without reading user data, registering
        # global hooks, or monitoring the clipboard.
        colors = resolve_colors({"mode": "deep_dark"})
        popup = QuickPastePopup(lambda _: None)
        popup.apply_theme(colors)
        composer = NoteComposer(lambda *_: None, lambda: None)
        composer.set_content("A sample note")
        ocr_panel = OCRWorkspace(lambda: None, lambda: None, lambda: None, lambda: None)
        ocr_panel.set_status("Ready")
        panel = SettingsPanel({}, lambda: None, lambda _: None, lambda: None)
        panel.add_capture_control(False, lambda _: None)
        panel.add_shortcut_controls(lambda *_: None)
        panel.add_storage_controls(lambda: None, lambda: None)
        panel.set_storage_usage("0 items")
        panel.sync_shortcut_controls()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(panel)
        card = DraggableCard({"type": "text", "content": "test"}, colors, lambda _: None, lambda _: None)
        note = DraggableCard({"type": "note", "content": "Manual note"}, colors, lambda _: None, lambda _: None)
        if not panel.shortcut_toggle.isChecked() or not hasattr(panel, "storage_usage") or composer.editor.toPlainText() != "A sample note":
            raise SystemExit(2)
        if app.windowIcon().isNull() or not build_dock_qss(colors):
            raise SystemExit(2)
        return
    data_dir = Path.home() / "SideDockData"
    data_dir.mkdir(parents=True, exist_ok=True)
    lock = QLockFile(str(data_dir / "instance.lock"))
    lock.setStaleLockTime(0)
    if not lock.tryLock(0):
        QMessageBox.information(None, "SideDock", "SideDock is already running or its data directory is locked.")
        return
    finish_diagnostics = start_diagnostics(data_dir, __version__)
    exit_code = 1
    try:
        try:
            dock = SideDock()
        except (OSError, ValueError) as exc:
            diagnostic_log.error("startup failed type=%s", type(exc).__name__)
            QMessageBox.critical(None, "SideDock", str(exc))
            raise SystemExit(exit_code) from None
        dock.show()
        exit_code = app.exec()
    except Exception:
        sys.excepthook(*sys.exc_info())
        raise SystemExit(1) from None
    finally:
        if finish_diagnostics is not None:
            finish_diagnostics(exit_code)
        lock.unlock()
    sys.exit(exit_code)

if __name__ == "__main__":
    main()
