import ctypes
from PySide6.QtCore import QMimeData, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QCursor, QDrag, QGuiApplication, QImage
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QPushButton,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)

GWL_EXSTYLE = -20
WS_EX_NOACTIVATE = 0x08000000


class DraggableCard(QFrame):
    def __init__(self, item, colors, on_click_cb, on_drag_state_cb):
        super().__init__()
        self.item = item
        self.is_dark = colors['is_dark']
        self.accent = colors['accent']
        self.setObjectName('ClipboardCard')
        self.flash_timer = QTimer(self)
        self.flash_timer.setSingleShot(True)
        self.flash_timer.timeout.connect(self._reset_flash)
        self.on_click_cb = on_click_cb
        self.on_drag_state_cb = on_drag_state_cb
        self._drag_start = None
        self._did_drag = False
        self.copied_badge = None
        self.apply_default_style()

    def apply_default_style(self):
        favorite = self.item.get("pinned", False)
        bg = "rgba(255,255,255,23)" if self.is_dark else "rgba(0,0,0,10)"
        border = ("#71717a" if self.is_dark else "#a1a1aa") if favorite else ("#41414b" if self.is_dark else "#d4d4d8")
        r, g, b = self.accent
        self.setStyleSheet(f"""
            QFrame#ClipboardCard {{
                background-color: {bg};
                border: 1px solid {border};
                border-radius: 12px;
            }}
            QFrame#ClipboardCard:hover {{
                background-color: rgba({r},{g},{b},30);
                border-color: rgba({r},{g},{b},130);
            }}
        """)

    def flash_copied(self):
        self.setStyleSheet("""
            QFrame#ClipboardCard {
                background-color: rgba(22,163,74,35);
                border: 1px solid #22c55e;
                border-radius: 12px;
            }
        """)
        if self.copied_badge:
            self.copied_badge.show()
        self.flash_timer.start(850)

    def _reset_flash(self):
        if self.copied_badge:
            self.copied_badge.hide()
        self.apply_default_style()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_start = event.pos()
            self._did_drag = False
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if not (event.buttons() & Qt.LeftButton) or self._drag_start is None:
            return
        if (event.pos() - self._drag_start).manhattanLength() < QApplication.startDragDistance():
            return

        self._did_drag = True
        self.on_drag_state_cb(True)

        drag = QDrag(self)
        mime = QMimeData()
        if self.item["type"] == "image":
            mime.setUrls([QUrl.fromLocalFile(self.item["path"])])
            mime.setImageData(QImage(self.item["path"]))
        elif self.item["type"] == "file":
            mime.setUrls([QUrl.fromLocalFile(self.item["path"])])
        else:
            mime.setText(self.item["content"])

        drag.setMimeData(mime)
        try:
            drag.exec(Qt.CopyAction)
        finally:
            self.on_drag_state_cb(False)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and not self._did_drag:
            self.flash_copied()
            self.on_click_cb(self.item)
        self._drag_start = None
        super().mouseReleaseEvent(event)


class QuickPastePopup(QWidget):
    slots_changed = Signal()
    def __init__(self, on_pick_callback):
        super().__init__()
        self.on_pick = on_pick_callback
        self.slot_map = {}
        self.seconds_left = 8

        self.setWindowFlags(
            Qt.WindowStaysOnTopHint
            | Qt.FramelessWindowHint
            | Qt.Tool
            | Qt.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedWidth(300)

        self.container = QFrame(self)
        self.container.setObjectName("QuickPopup")
        self.container.setStyleSheet("""
            #QuickPopup {
                background-color: rgba(10, 12, 16, 244);
                border: 1px solid rgba(59, 130, 246, 170);
                border-radius: 18px;
            }
            QLabel { color: #f1f5f9; font-family: 'Segoe UI'; font-weight: 600; }
        """)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self.container)

        self.layout_box = QVBoxLayout(self.container)
        self.layout_box.setContentsMargins(12, 10, 12, 12)
        self.layout_box.setSpacing(6)

        header = QHBoxLayout()
        self.title_label = QLabel("Also Copied (Ctrl+Alt+2/3)")
        self.title_label.setWordWrap(True)
        self.title_label.setStyleSheet("font-size: 11px; font-weight: 600;")
        self.timer_label = QLabel("8s")
        self.timer_label.setStyleSheet("font-size: 11px;")

        dismiss_btn = QPushButton("×")
        dismiss_btn.setFixedSize(18, 18)
        dismiss_btn.setCursor(Qt.PointingHandCursor)
        dismiss_btn.setObjectName("PopupClose")
        dismiss_btn.setToolTip("Dismiss Quick-Paste")
        dismiss_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 18);
                color: #cbd5e1;
                border: none;
                border-radius: 9px;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton:hover { background: rgba(239, 68, 68, 190); color: white; }
        """)
        dismiss_btn.setStyleSheet("")
        dismiss_btn.clicked.connect(self.dismiss)

        header.addWidget(self.title_label)
        header.addStretch()
        header.addWidget(self.timer_label)
        header.addWidget(dismiss_btn)
        self.layout_box.addLayout(header)
        self.progress = QProgressBar()
        self.progress.setRange(0, 8)
        self.progress.setValue(8)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(3)
        self.layout_box.addWidget(self.progress)

        self.slots_layout = QVBoxLayout()
        self.slots_layout.setSpacing(6)
        self.layout_box.addLayout(self.slots_layout)

        self.countdown = QTimer(self)
        self.countdown.timeout.connect(self.tick)

    def apply_theme(self, colors):
        dark = colors["is_dark"]
        bg = "#18181b" if dark else "#fafafa"
        fg = "#f4f4f5" if dark else "#18181b"
        border = "#3f3f46" if dark else "#d4d4d8"
        surface = "#27272a" if dark else "#f4f4f5"
        r, g, b = colors["accent"]
        self.container.setStyleSheet(f"""
            #QuickPopup {{ background: {bg}; border: 1px solid {border}; border-radius: 16px; }}
            QLabel {{ color: {fg}; font-family: 'Segoe UI'; font-weight: 500; }}
            QPushButton {{ background: {surface}; color: {fg}; border: 1px solid {border};
                           border-radius: 9px; padding: 7px 9px; text-align: left; font-size: 12px; }}
            QPushButton:hover {{ border-color: rgb({r},{g},{b}); }}
            QPushButton#PopupClose {{ padding: 0px; text-align: center; border: none; }}
            QProgressBar {{ background: {border}; border: none; border-radius: 1px; }}
            QProgressBar::chunk {{ background: rgb({r},{g},{b}); border-radius: 1px; }}
        """)

    def showEvent(self, event):
        super().showEvent(event)
        hwnd = int(self.winId())
        ex_style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        ctypes.windll.user32.SetWindowLongW(
            hwnd, GWL_EXSTYLE, ex_style | WS_EX_NOACTIVATE
        )

    def show_slots(self, numbered_items, title_text):
        if not numbered_items:
            return
        self.title_label.setText(title_text)
        self.slot_map = {num: item for num, item in numbered_items}
        self.slots_changed.emit()
        self.render_slots()

        self.seconds_left = 8
        self.timer_label.setText("8s")
        self.progress.setValue(8)
        self.show()
        self.countdown.start(1000)

    def render_slots(self):
        while self.slots_layout.count():
            child = self.slots_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        for num, item in self.slot_map.items():
            btn = QPushButton()
            btn.setCursor(Qt.PointingHandCursor)
            if item["type"] == "image":
                btn.setText(f"[{num}]  🖼️ Screenshot / Image")
            elif item["type"] == "file":
                btn.setText(f"[{num}]  📄 {item['name']}")
            else:
                snippet = item["content"].replace("\n", " ")
                if len(snippet) > 36:
                    snippet = snippet[:33] + "..."
                btn.setText(f"[{num}]  {snippet}")

            btn.clicked.connect(lambda _, n=num: self.pick_number(n))
            self.slots_layout.addWidget(btn)

        self.adjustSize()
        # Place the focus-free popup on the user's current monitor.
        target = (QGuiApplication.screenAt(QCursor.pos()) or self.screen()
                  or QGuiApplication.primaryScreen())
        if target is not None:
            screen = target.availableGeometry()
            self.move(screen.right() - self.width() - 20,
                      screen.bottom() - self.height() - 20)

    def tick(self):
        self.seconds_left -= 1
        self.progress.setValue(max(0, self.seconds_left))
        if self.seconds_left <= 0:
            self.dismiss()
        else:
            self.timer_label.setText(f"{self.seconds_left}s")

    def dismiss(self):
        self.countdown.stop()
        self.slot_map.clear()
        self.slots_changed.emit()
        self.hide()

    def pick_number(self, num):
        item = self.slot_map.pop(num, None)
        if item is None:
            return

        self.slots_changed.emit()
        self.on_pick(item)
        if self.slot_map and self.seconds_left > 0:
            self.render_slots()
        else:
            self.dismiss()


class SettingsPanel(QWidget):
    def __init__(self, settings, on_change_cb, on_side_cb, on_back_cb):
        super().__init__()
        self.settings = settings
        self.on_change = on_change_cb
        self.on_side = on_side_cb

        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 4, 2, 4)
        layout.setSpacing(12)

        top = QHBoxLayout()
        back_btn = QPushButton("← Back")
        back_btn.setObjectName("BackBtn")
        back_btn.setCursor(Qt.PointingHandCursor)
        back_btn.clicked.connect(on_back_cb)
        heading = QLabel("Settings")
        heading.setStyleSheet("font-size: 13px; font-weight: 700;")
        top.addWidget(back_btn)
        top.addStretch()
        top.addWidget(heading)
        layout.addLayout(top)

        mode_lbl = QLabel("Theme Mode")
        mode_lbl.setObjectName("SubLabel")
        layout.addWidget(mode_lbl)

        mode_row = QHBoxLayout()
        mode_row.setSpacing(6)
        self.mode_buttons = {}
        for key, label in [
            ("windows", "Windows"),
            ("dark", "Dark"),
            ("deep_dark", "Deep Dark"),
        ]:
            btn = QPushButton(label)
            btn.setObjectName("ModeBtn")
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda _, k=key: self.set_mode(k))
            self.mode_buttons[key] = btn
            mode_row.addWidget(btn)
        layout.addLayout(mode_row)

        pos_lbl = QLabel("Dock Side (or drag top bar)")
        pos_lbl.setObjectName("SubLabel")
        layout.addWidget(pos_lbl)

        side_row = QHBoxLayout()
        side_row.setSpacing(6)
        self.side_buttons = {}
        for key, label in [("left", "Left Edge"), ("right", "Right Edge")]:
            btn = QPushButton(label)
            btn.setObjectName("ModeBtn")
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda _, k=key: self.set_side(k))
            self.side_buttons[key] = btn
            side_row.addWidget(btn)
        layout.addLayout(side_row)

        layout.addStretch()
        self.sync_buttons()

    def add_capture_control(self, paused, callback):
        button = QPushButton("Pause clipboard capture")
        button.setObjectName("ModeBtn")
        button.setCheckable(True)
        self.capture_button = button
        button.setChecked(paused)
        button.toggled.connect(callback)
        self.layout().insertWidget(self.layout().count() - 1, button)
        note = QLabel("Paused capture skips automatic clipboard monitoring. Manual drops and saved items remain available.")
        note.setObjectName("SubLabel")
        note.setWordWrap(True)
        self.layout().insertWidget(self.layout().count() - 1, note)

    def add_shortcut_controls(self, callback):
        """Expose shortcut state immediately below the capture control."""
        layout = self.layout()
        hint = QLabel("KEYBOARD SHORTCUTS")
        hint.setObjectName("SubLabel")
        layout.insertWidget(layout.count() - 1, hint)
        self.shortcut_toggle = QPushButton("Enable SideDock shortcuts")
        self.shortcut_toggle.setObjectName("ModeBtn")
        self.shortcut_toggle.setCheckable(True)
        self.shortcut_toggle.setToolTip("Enabled by default for new users. Only shows earlier copies after a quick multi-copy sequence; disable SideDock hotkeys if they conflict with another app.")
        self.shortcut_toggle.setChecked(bool(self.settings.get("shortcuts_enabled", True)))
        self.shortcut_toggle.toggled.connect(lambda enabled: callback("enabled", enabled))
        layout.insertWidget(layout.count() - 1, self.shortcut_toggle)
        self.shortcut_preset = QComboBox()
        self.shortcut_preset.addItem("Classic shortcuts", "classic")
        self.shortcut_preset.addItem("Alternative shortcuts", "alternative")
        self.shortcut_preset.setToolTip("Choose keyboard shortcuts for Quick-Paste")
        self.shortcut_preset.currentIndexChanged.connect(lambda _: callback("preset", self.shortcut_preset.currentData()))
        layout.insertWidget(layout.count() - 1, self.shortcut_preset)
        self.shortcut_info = QLabel()
        self.shortcut_info.setObjectName("SubLabel")
        self.shortcut_info.setWordWrap(True)
        layout.insertWidget(layout.count() - 1, self.shortcut_info)
        self.sync_shortcut_controls()

    def add_storage_controls(self, open_callback, cleanup_callback):
        layout = self.layout()
        title = QLabel("LOCAL STORAGE")
        title.setObjectName("SubLabel")
        layout.insertWidget(layout.count() - 1, title)
        self.storage_usage = QLabel()
        self.storage_usage.setObjectName("SubLabel")
        self.storage_usage.setWordWrap(True)
        layout.insertWidget(layout.count() - 1, self.storage_usage)
        actions = QHBoxLayout()
        open_btn = QPushButton("Open Folder")
        open_btn.setObjectName("ModeBtn")
        open_btn.setToolTip("Open SideDockData in File Explorer")
        open_btn.clicked.connect(open_callback)
        clean_btn = QPushButton("Clean Copies")
        clean_btn.setObjectName("ModeBtn")
        clean_btn.setToolTip("Review and remove unused SideDock-managed file copies only")
        clean_btn.clicked.connect(cleanup_callback)
        actions.addWidget(open_btn)
        actions.addWidget(clean_btn)
        layout.insertLayout(layout.count() - 1, actions)

    def set_storage_usage(self, message):
        if hasattr(self, "storage_usage"):
            self.storage_usage.setText(message)

    def sync_shortcut_controls(self):
        if not hasattr(self, "shortcut_toggle"):
            return
        for control in (self.shortcut_toggle, self.shortcut_preset):
            control.blockSignals(True)
        self.shortcut_toggle.setChecked(bool(self.settings.get("shortcuts_enabled", True)))
        preset = self.settings.get("shortcut_preset", "classic")
        self.shortcut_preset.setCurrentIndex(1 if preset == "alternative" else 0)
        for control in (self.shortcut_toggle, self.shortcut_preset):
            control.blockSignals(False)
        binding = "Ctrl+Alt+V · Ctrl+Shift+Alt+1/2/3" if preset == "alternative" else "Ctrl+Shift+V · Ctrl+Alt+1/2/3"
        self.shortcut_info.setText("Open Quick-Paste · Select visible slots\n" + binding + "\nCtrl+V pastes normally. Only when you copy 2+ items close together does it offer the earlier 1–2 copies, once, for 8 seconds. After a single copy, no popup.")

    def sync_buttons(self):
        current_mode = self.settings.get("mode", "deep_dark")
        for k, btn in self.mode_buttons.items():
            btn.setChecked(k == current_mode)

        current_side = self.settings.get("side", "right")
        for k, btn in self.side_buttons.items():
            btn.setChecked(k == current_side)

    def set_mode(self, mode):
        self.settings["mode"] = mode
        self.sync_buttons()
        self.on_change()

    def set_side(self, side):
        self.settings["side"] = side
        self.sync_buttons()
        self.on_side(side)