import ctypes
import os
from ctypes import wintypes
import hashlib
import json
import re
import shutil
import subprocess
import sys
import time
import uuid
import logging
from pathlib import Path
import keyboard
from PySide6.QtCore import (
    QBuffer,
    QByteArray,
    QEasingCurve,
    QIODevice,
    QLockFile,
    QMimeData,
    QParallelAnimationGroup,
    QPoint,
    QPropertyAnimation,
    Qt,
    QTimer,
    QUrl,
    Signal,
)
from PySide6.QtGui import QCursor, QGuiApplication, QImage, QPixmap, QRegion
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
from sidedock.autostart import is_enabled as autostart_enabled, set_enabled as set_autostart_enabled
from sidedock.version import __version__
from sidedock.presentation import card_kind, preview_text
from sidedock.interaction import shortcut_keys, select_paste_target
from sidedock.storage import atomic_write_json, can_capture, file_digest, managed_bytes, MAX_FILE_BYTES, MAX_TEXT_BYTES, MAX_MANAGED_BYTES
from sidedock.theme import build_dock_qss, resolve_colors
from sidedock.widgets import (
    DraggableCard,
    GWL_EXSTYLE,
    QuickPastePopup,
    SettingsPanel,
    WS_EX_NOACTIVATE,
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

    def __init__(self):
        super().__init__()
        self._ignore_clipboard = False
        self._capture_paused = False
        self._is_dragging_out = False
        self._is_dragging_dock = False
        self.is_pinned = False
        self.is_expanded = False
        self.rapid_buffer = []
        self._search_target = None
        self._paste_generation = 0
        self._hotkey_removers = []
        self._slot_removers = []

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

        capture_btn = QPushButton("Capture")
        capture_btn.setObjectName("CaptureBtn")
        capture_btn.setCursor(Qt.PointingHandCursor)
        capture_btn.clicked.connect(self.trigger_capture)

        clear_btn = QPushButton("Clear")
        clear_btn.setObjectName("HeaderBtn")
        clear_btn.setToolTip("Clear unstarred items")
        clear_btn.setCursor(Qt.PointingHandCursor)
        clear_btn.clicked.connect(self.clear_unpinned)

        self.pin_btn = QPushButton("Pin")
        self.pin_btn.setObjectName("HeaderBtn")
        self.pin_btn.setCheckable(True)
        self.pin_btn.setCursor(Qt.PointingHandCursor)
        self.pin_btn.toggled.connect(self.toggle_pin)

        close_btn = QPushButton("×")
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
        self.search_input.setPlaceholderText("Search your clipboard…")
        self.search_input.setAccessibleName("Search clipboard")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.mousePressEvent = self.on_search_click
        self.search_input.textChanged.connect(self.refresh_list)
        items_layout.addWidget(self.search_input)
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
        self.pages.addWidget(items_page)
        self.pages.addWidget(self.settings_panel)
        layout.addWidget(self.pages)

        # Bottom bar: mirrors resize grip & Settings ⚙ depending on Left/Right edge
        self.bottom_bar = QHBoxLayout()
        self.bottom_bar.setContentsMargins(0, 0, 0, 0)
        self.grip = QSizeGrip(self)
        self.grip.setFixedSize(16, 16)
        self.grip.setToolTip("Drag to resize SideDock")

        self.gear_btn = QPushButton("Settings ⚙")
        self.gear_btn.setObjectName("GearBtn")
        self.gear_btn.setCursor(Qt.PointingHandCursor)
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
        self.trigger_after_paste_signal.connect(self.open_remaining_popup)
        self.trigger_all_slots_signal.connect(self.open_all_slots_popup)
        self.pick_slot_signal.connect(self.quick_popup.pick_number)

        self.quick_popup.slots_changed.connect(self.sync_slot_hotkeys)
        self.setup_tray()
        self.register_hotkeys()
        app = QApplication.instance()
        app.screenRemoved.connect(self.on_screen_removed)
        app.screenAdded.connect(self.on_screen_added)
        for monitor in app.screens():
            monitor.availableGeometryChanged.connect(self.on_monitor_geometry_changed)
        self.update_monitor_mask()

    def setup_tray(self):
        self.tray = QSystemTrayIcon(QApplication.instance().windowIcon(), self)
        self.tray.setToolTip(f"SideDock {__version__}")
        self.tray_menu = QMenu()
        self.tray_menu.addAction("Show dock", self.show_from_tray)
        self.tray_pause = self.tray_menu.addAction("Pause clipboard capture")
        self.tray_pause.setCheckable(True)
        self.tray_pause.setChecked(self._capture_paused)
        self.tray_pause.toggled.connect(self.set_capture_paused)
        self.tray_shortcuts = self.tray_menu.addAction("Enable global shortcuts")
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
            logging.exception("Unable to register shortcuts")

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
            logging.exception("Unable to register popup shortcuts")

    def set_shortcuts_enabled(self, enabled):
        self.settings["shortcuts_enabled"] = enabled
        self.save_json(self.settings_file, self.settings)
        self.quick_popup.dismiss()
        self.register_hotkeys()

    def on_screen_added(self, screen):
        screen.availableGeometryChanged.connect(self.on_monitor_geometry_changed)

    def on_screen_removed(self, screen):
        if self.monitor == screen:
            self.monitor = QGuiApplication.primaryScreen()
            if self.monitor is not None:
                self.settings["monitor"] = self.monitor.name()
                self.on_monitor_geometry_changed()

    def on_monitor_geometry_changed(self, *_):
        if self.monitor is None:
            return
        self.update_edge_coords()
        self.anim_group.stop()
        self.move(self.x_shown if self.is_expanded else self.x_hidden, self.y_pos)
        self.update_monitor_mask()

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
        screen = self.monitor.availableGeometry()
        min_y = screen.top() + 8
        max_y = max(min_y, screen.bottom() - self.dock_height - 8)
        self.y_pos = max(min_y, min(self.y_pos, max_y))

        if self.dock_side == "left":
            self.x_shown = screen.left() + 12
            self.x_hidden = screen.left() - self.dock_width + 6
        else:
            self.x_shown = screen.right() - self.dock_width - 12
            self.x_hidden = screen.right() - 6

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
        self.capture_status.setText("PAUSED" if self._capture_paused else "LOCAL")
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
        self.rapid_buffer = []
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

    def clear_unpinned(self):
        kept = [item for item in self.saved_items if item.get("pinned")]
        removed = [item for item in self.saved_items if not item.get("pinned")]
        self.save_json(self.index_file, kept)
        self.saved_items = kept
        self.rapid_buffer = []
        self.quick_popup.dismiss()
        for item in removed:
            self.remove_managed_file(item)
        self.refresh_list()

    def remove_managed_file(self, item):
        if item["type"] in ("image", "file"):
            p = Path(item["path"])
            if p.parent == self.files_dir and not any(other.get("path") == str(p) for other in self.saved_items):
                try:
                    p.unlink(missing_ok=True)
                except OSError:
                    logging.exception("Could not delete stored copy")

    def showEvent(self, event):
        super().showEvent(event)
        self.restore_no_activate()
        self.apply_theme()
        QTimer.singleShot(0, self.sync_list_width)

    def on_search_click(self, event):
        identity = window_identity(user32.GetForegroundWindow())
        if identity and identity[1] != os.getpid():
            self._search_target = identity
        hwnd = int(self.winId())
        ex_style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        ctypes.windll.user32.SetWindowLongW(
            hwnd, GWL_EXSTYLE, ex_style & ~WS_EX_NOACTIVATE
        )
        self.activateWindow()
        QLineEdit.mousePressEvent(self.search_input, event)

    def restore_no_activate(self):
        hwnd = int(self.winId())
        ex_style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        ctypes.windll.user32.SetWindowLongW(
            hwnd, GWL_EXSTYLE, ex_style | WS_EX_NOACTIVATE
        )

    def on_ctrl_v(self):
        if len(self.rapid_buffer) >= 2:
            self.trigger_after_paste_signal.emit()

    def open_remaining_popup(self):
        remaining = list(enumerate(self.rapid_buffer[1:3], start=2))
        self.rapid_buffer = []
        if not self.settings.get("shortcuts_enabled", True):
            return
        self.quick_popup.show_slots(remaining, f"Also Copied ({self.shortcut_keys()[2]}+2/3)")

    def open_all_slots_popup(self):
        items = self.rapid_buffer if self.rapid_buffer else self.saved_items[:3]
        numbered = list(enumerate(items[:3], start=1))
        if not self.settings.get("shortcuts_enabled", True):
            return
        self.quick_popup.show_slots(numbered, f"Quick Paste ({self.shortcut_keys()[2]}+1/2/3)")

    def paste_item_now(self, item):
        if item["type"] in ("image", "file") and not Path(item["path"]).exists():
            return
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

    def trigger_capture(self):
        self.collapse(force=True)
        QTimer.singleShot(
            260, lambda: subprocess.Popen(["explorer", "ms-screenclip:"])
        )

    def is_cursor_in_dock_zone(self):
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
                self.is_pinned
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
        if not self.is_expanded:
            self.expand()
        super().enterEvent(event)

    def leaveEvent(self, event):
        if not self.is_pinned and not self._is_dragging_out and not self._is_dragging_dock:
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
        self.safe_process_mime(event.mimeData())
        event.acceptProposedAction()

    def toggle_pin(self, checked):
        self.is_pinned = checked
        if not checked and not self.underMouse():
            self.hide_timer.start(300)

    def expand(self):
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

    def collapse(self, force=False):
        if (self.is_pinned or self._is_dragging_out or self._is_dragging_dock) and not force:
            return
        self.hover_watch.stop()
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

        self.safe_process_mime(self.clipboard.mimeData())

    def record_new_item(self, item):
        item.setdefault("pinned", False)
        self.save_json(self.index_file, [item, *self.saved_items])
        self.saved_items.insert(0, item)
        self.rapid_buffer.insert(0, item)
        self.rapid_buffer = self.rapid_buffer[:3]
        self.refresh_list()

    def safe_process_mime(self, mime):
        try:
            self.process_mime(mime)
        except (OSError, ValueError):
            logging.exception("SideDock could not capture an item")

    def process_mime(self, mime):
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
                        self.record_new_item({"type": "file", "name": src.name, "path": str(src)})
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
                    self.record_new_item({"type": kind, "path": str(dest), "hash": digest, "name": src.name})
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
                self.record_new_item({"type": "image", "path": str(file_path), "hash": img_hash})
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
            self.record_new_item({"type": "text", "content": text})

    def matches_query(self, item, query):
        if not query:
            return True
        if item["type"] == "text":
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
        self.history_status.setText(f"{len(visible)} SHOWN  ·  {len(pinned)} STARRED" if query else f"{len(visible)} ITEMS  ·  {len(pinned)} STARRED")
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
        self.sync_list_width()

    def render_item(self, item):
        card = DraggableCard(
            item, self.colors, self.paste_item_now, self.set_drag_out_state
        )
        card.setCursor(Qt.PointingHandCursor)
        card.setToolTip("Click to copy and paste · Drag to another app")
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
        star_btn = QPushButton("★" if is_fav else "☆")
        star_btn.setFixedSize(24, 24)
        star_btn.setCursor(Qt.PointingHandCursor)
        star_btn.setToolTip("Remove favorite" if is_fav else "Keep as favorite")
        star_btn.setAccessibleName(star_btn.toolTip())
        star_color = "#f4f4f5" if self.colors["is_dark"] else "#27272a"
        muted = "#a1a1aa" if self.colors["is_dark"] else "#52525b"
        star_btn.setStyleSheet(f"QPushButton {{ background: transparent; color: {star_color if is_fav else muted}; border: none; font-size: 16px; }}")
        star_btn.clicked.connect(lambda _, it=item: self.toggle_favorite(it))
        top.addWidget(star_btn)

        remove_btn = QPushButton("×")
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
        self.rapid_buffer = [entry for entry in self.rapid_buffer if entry is not item]
        self.quick_popup.dismiss()
        self.remove_managed_file(item)
        self.refresh_list()

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
    if "--smoke-test" in sys.argv:
        # Exercise packaged Qt resources without reading user data, registering
        # global hooks, or monitoring the clipboard.
        colors = resolve_colors({"mode": "deep_dark"})
        popup = QuickPastePopup(lambda _: None)
        popup.apply_theme(colors)
        panel = SettingsPanel({}, lambda: None, lambda _: None, lambda: None)
        panel.add_capture_control(False, lambda _: None)
        card = DraggableCard({"type": "text", "content": "test"}, colors, lambda _: None, lambda _: None)
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
    try:
        dock = SideDock()
    except (OSError, ValueError) as exc:
        QMessageBox.critical(None, "SideDock", str(exc))
        lock.unlock()
        return
    dock.show()
    print("SideDock is running! Hover your screen edge.")
    exit_code = app.exec()
    lock.unlock()
    sys.exit(exit_code)

if __name__ == "__main__":
    main()