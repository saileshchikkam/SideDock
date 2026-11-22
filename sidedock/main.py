import ctypes
import hashlib
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
import keyboard
from PySide6.QtCore import (
    QBuffer,
    QByteArray,
    QEasingCurve,
    QIODevice,
    QMimeData,
    QParallelAnimationGroup,
    QPoint,
    QPropertyAnimation,
    Qt,
    QTimer,
    QUrl,
    Signal,
)
from PySide6.QtGui import QCursor, QGuiApplication, QImage, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizeGrip,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from sidedock.theme import build_dock_qss, resolve_colors
from sidedock.widgets import (
    DraggableCard,
    GWL_EXSTYLE,
    QuickPastePopup,
    SettingsPanel,
    WS_EX_NOACTIVATE,
)

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
        self._is_dragging_out = False
        self._is_dragging_dock = False
        self.is_pinned = False
        self.is_expanded = False
        self.rapid_buffer = []

        # 1. Local PC storage setup
        self.data_dir = Path.home() / "SideDockData"
        self.files_dir = self.data_dir / "files"
        self.files_dir.mkdir(parents=True, exist_ok=True)
        self.index_file = self.data_dir / "items.json"
        self.settings_file = self.data_dir / "settings.json"
        self.saved_items = self.load_json(self.index_file, [])
        self.settings = self.load_json(
            self.settings_file, {"mode": "deep_dark", "side": "right", "y": None}
        )

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
        screen = QGuiApplication.primaryScreen().availableGeometry()
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
        layout.setContentsMargins(14, 6, 14, 10)
        layout.setSpacing(8)

        # Top drag grabber bar
        layout.addWidget(DockGrabber(self))

        # Header with Capture, Clear, Pin, and Close buttons
        header = QHBoxLayout()
        header.setSpacing(5)
        title = QLabel("SideDock")
        title.setStyleSheet("font-size: 14px; font-weight: 700;")

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
        close_btn.clicked.connect(QApplication.quit)

        header.addWidget(title)
        header.addStretch()
        header.addWidget(capture_btn)
        header.addWidget(clear_btn)
        header.addWidget(self.pin_btn)
        header.addWidget(close_btn)
        layout.addLayout(header)

        # Stacked pages: [0] Items View, [1] Settings View
        self.pages = QStackedWidget()
        items_page = QWidget()
        items_layout = QVBoxLayout(items_page)
        items_layout.setContentsMargins(0, 0, 0, 0)
        items_layout.setSpacing(8)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search text, files, or images...")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.mousePressEvent = self.on_search_click
        self.search_input.textChanged.connect(self.refresh_list)
        items_layout.addWidget(self.search_input)

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

        # 7. Quick-Paste 8s popup + hotkeys
        self.quick_popup = QuickPastePopup(self.paste_item_now)
        self.trigger_after_paste_signal.connect(self.open_remaining_popup)
        self.trigger_all_slots_signal.connect(self.open_all_slots_popup)
        self.pick_slot_signal.connect(self.quick_popup.pick_number)

        keyboard.add_hotkey("ctrl+v", self.on_ctrl_v, suppress=False)
        keyboard.add_hotkey("ctrl+shift+v", lambda: self.trigger_all_slots_signal.emit(), suppress=True)
        keyboard.add_hotkey("ctrl+alt+1", lambda: self.pick_slot_signal.emit(1), suppress=True)
        keyboard.add_hotkey("ctrl+alt+2", lambda: self.pick_slot_signal.emit(2), suppress=True)
        keyboard.add_hotkey("ctrl+alt+3", lambda: self.pick_slot_signal.emit(3), suppress=True)

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
        screen = QGuiApplication.primaryScreen().availableGeometry()
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
        self.update_edge_coords()
        self.update_footer_layout()
        self.save_json(self.settings_file, self.settings)
        self.expand()

    def snap_to_side_edge(self):
        screen = QGuiApplication.primaryScreen().availableGeometry()
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
        except (json.JSONDecodeError, OSError):
            return default

    def save_json(self, path, data):
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def apply_theme(self, drag_highlight=False):
        self.colors = resolve_colors(self.settings)
        self.container.setStyleSheet(build_dock_qss(self.colors, drag_highlight))

    def on_settings_changed(self):
        self.save_json(self.settings_file, self.settings)
        self.apply_theme()
        self.refresh_list()

    def toggle_settings(self):
        self.pages.setCurrentIndex(1 if self.pages.currentIndex() == 0 else 0)

    def clear_unpinned(self):
        kept = []
        for item in self.saved_items:
            if item.get("pinned"):
                kept.append(item)
            elif item["type"] in ("image", "file"):
                p = Path(item["path"])
                if p.exists() and p.parent == self.files_dir:
                    p.unlink(missing_ok=True)
        self.saved_items = kept
        self.rapid_buffer = []
        self.save_json(self.index_file, self.saved_items)
        self.refresh_list()

    def showEvent(self, event):
        super().showEvent(event)
        self.restore_no_activate()
        self.apply_theme()
        QTimer.singleShot(0, self.sync_list_width)

    def on_search_click(self, event):
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
        self.quick_popup.show_slots(remaining, "Also Copied (Ctrl+Alt+2/3)")

    def open_all_slots_popup(self):
        items = self.rapid_buffer if self.rapid_buffer else self.saved_items[:3]
        numbered = list(enumerate(items[:3], start=1))
        self.quick_popup.show_slots(numbered, "Quick Paste (Ctrl+Alt+1/2/3)")

    def paste_item_now(self, item):
        if item["type"] == "image":
            self.copy_image_back(item["path"])
        elif item["type"] == "file":
            self.copy_file_back(item["path"])
        else:
            self.copy_text_back(item["content"])
        QTimer.singleShot(80, lambda: keyboard.send("ctrl+v"))

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
     super().resizeEvent(event)

    def trigger_capture(self):
        self.collapse(force=True)
        QTimer.singleShot(
            260, lambda: subprocess.Popen(["explorer", "ms-screenclip:"])
        )

    def is_cursor_in_dock_zone(self):
        pos = QCursor.pos()
        screen = QGuiApplication.primaryScreen().availableGeometry()
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
        self.process_mime(event.mimeData())
        event.acceptProposedAction()

    def toggle_pin(self, checked):
        self.is_pinned = checked
        if not checked and not self.underMouse():
            self.hide_timer.start(300)

    def expand(self):
        if self.settings.get("mode") == "windows":
            self.apply_theme()
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
        if ctypes.windll.user32.IsClipboardFormatAvailable(EXCLUDE_CLIPBOARD_FMT):
            return

        self.process_mime(self.clipboard.mimeData())

    def record_new_item(self, item):
        item.setdefault("pinned", False)
        self.saved_items.insert(0, item)
        self.rapid_buffer.insert(0, item)
        self.rapid_buffer = self.rapid_buffer[:3]
        self.save_json(self.index_file, self.saved_items)
        self.refresh_list()

    def process_mime(self, mime):
        if mime.hasUrls():
            for url in mime.urls():
                if not url.isLocalFile():
                    continue
                src = Path(url.toLocalFile())
                if not src.exists():
                    continue

                if src.is_file():
                    dest = self.files_dir / f"{int(time.time() * 1000)}_{src.name}"
                    shutil.copy2(src, dest)
                    saved_path = str(dest)
                else:
                    saved_path = str(src)

                if src.is_file() and src.suffix.lower() in IMAGE_EXTS:
                    img_hash = hashlib.md5(Path(saved_path).read_bytes()).hexdigest()
                    if self.saved_items and self.saved_items[0].get("hash") == img_hash:
                        continue
                    item = {"type": "image", "path": saved_path, "hash": img_hash, "name": src.name}
                else:
                    if self.saved_items and self.saved_items[0].get("name") == src.name:
                        continue
                    item = {"type": "file", "name": src.name, "path": saved_path}

                self.record_new_item(item)
            return

        if mime.hasImage():
            image = QImage(mime.imageData())
            if image.isNull():
                return

            ba = QByteArray()
            buf = QBuffer(ba)
            buf.open(QIODevice.WriteOnly)
            image.save(buf, "PNG")
            img_bytes = bytes(ba)
            img_hash = hashlib.md5(img_bytes).hexdigest()

            if self.saved_items and self.saved_items[0].get("hash") == img_hash:
                return

            file_path = self.files_dir / f"img_{int(time.time() * 1000)}.png"
            file_path.write_bytes(img_bytes)

            item = {"type": "image", "path": str(file_path), "hash": img_hash}
            self.record_new_item(item)
            return

        if mime.hasText():
            text = mime.text().strip()
            if not text:
                return
            if self.saved_items and self.saved_items[0].get("content") == text:
                return

            item = {"type": "text", "content": text}
            self.record_new_item(item)

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

        for item in pinned + unpinned:
            if self.matches_query(item, query):
                self.render_item(item)
        self.sync_list_width()

    def render_item(self, item):
        if item["type"] in ("file", "image") and not Path(item["path"]).exists():
            return

        card = DraggableCard(
            item, self.colors["is_dark"], self.paste_item_now, self.set_drag_out_state
        )
        card.setCursor(Qt.PointingHandCursor)

        row = QHBoxLayout(card)
        row.setContentsMargins(10, 8, 8, 8)
        row.setSpacing(4)

        content = QLabel()
        content.setObjectName("CardText")
        content.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        content.setMinimumWidth(0)
        content.setStyleSheet("background: transparent; border: none; font-size: 12px;")

        if item["type"] == "image":
            max_img_w = max(90, self.dock_width - 125)
            pixmap = QPixmap(item["path"]).scaled(
                max_img_w, 100, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            content.setPixmap(pixmap)
        elif item["type"] == "file":
            fname = re.sub(r"(\S{20})", lambda m: m.group(1) + "\u200b", item["name"])
            content.setWordWrap(True)
            content.setText(f"📄  {fname}")
        else:
            text = item["content"]
            preview = text if len(text) <= 110 else text[:107] + "..."
            preview = re.sub(r"(\S{20})", lambda m: m.group(1) + "\u200b", preview)
            content.setWordWrap(True)
            content.setText(preview)

        copied_badge = QLabel("Copied!")
        copied_badge.setStyleSheet(
            "background: rgba(16, 185, 129, 200); color: white; border-radius: 6px; padding: 1px 5px; font-size: 10px;"
        )
        copied_badge.hide()
        card.copied_badge = copied_badge

        is_fav = item.get("pinned", False)
        star_btn = QPushButton("★" if is_fav else "☆")
        star_btn.setFixedSize(20, 20)
        star_btn.setCursor(Qt.PointingHandCursor)
        star_color = "#eab308" if is_fav else ("#94a3b8" if self.colors["is_dark"] else "#64748b")
        star_btn.setStyleSheet(f"""
            QPushButton {{ background: transparent; color: {star_color}; border: none; font-size: 13px; }}
            QPushButton:hover {{ color: #fde047; }}
        """)
        star_btn.clicked.connect(lambda _, it=item: self.toggle_favorite(it))

        remove_btn = QPushButton("×")
        remove_btn.setObjectName("CloseBtn")
        remove_btn.setFixedSize(20, 20)
        remove_btn.setCursor(Qt.PointingHandCursor)
        remove_btn.clicked.connect(lambda _, it=item: self.remove_item(it))

        actions = QHBoxLayout()
        actions.setSpacing(2)
        actions.addWidget(copied_badge)
        actions.addWidget(star_btn)
        actions.addWidget(remove_btn)

        row.addWidget(content, 1)
        row.addLayout(actions)
        row.setAlignment(actions, Qt.AlignTop | Qt.AlignRight)
        self.list_layout.insertWidget(self.list_layout.count() - 1, card)

    def toggle_favorite(self, item):
        item["pinned"] = not item.get("pinned", False)
        self.save_json(self.index_file, self.saved_items)
        self.refresh_list()

    def remove_item(self, item):
        if item in self.saved_items:
            self.saved_items.remove(item)
            self.save_json(self.index_file, self.saved_items)
        if item["type"] in ("image", "file"):
            p = Path(item["path"])
            if p.exists() and p.parent == self.files_dir:
                p.unlink(missing_ok=True)
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
    dock = SideDock()
    dock.show()
    print("SideDock is running! Hover your screen edge.")
    sys.exit(app.exec())

if __name__ == "__main__":
    main()