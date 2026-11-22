import ctypes
from PySide6.QtCore import QMimeData, Qt, QTimer, QUrl
from PySide6.QtGui import QDrag, QImage
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

GWL_EXSTYLE = -20
WS_EX_NOACTIVATE = 0x08000000


class DraggableCard(QFrame):
    def __init__(self, item, is_dark, on_click_cb, on_drag_state_cb):
        super().__init__()
        self.item = item
        self.is_dark = is_dark
        self.on_click_cb = on_click_cb
        self.on_drag_state_cb = on_drag_state_cb
        self._drag_start = None
        self._did_drag = False
        self.copied_badge = None
        self.apply_default_style()

    def apply_default_style(self):
        is_fav = self.item.get("pinned", False)
        if self.is_dark:
            bg = "rgba(255, 255, 255, 18)"
            border = "rgba(250, 204, 21, 145)" if is_fav else "rgba(255, 255, 255, 24)"
        else:
            bg = "rgba(15, 23, 42, 10)"
            border = "rgba(202, 138, 4, 170)" if is_fav else "rgba(15, 23, 42, 26)"

        self.setStyleSheet(f"""
            QFrame {{
                background-color: {bg};
                border: 1px solid {border};
                border-radius: 14px;
            }}
            QFrame:hover {{
                background-color: rgba(37, 99, 235, 55);
                border-color: rgba(96, 165, 250, 170);
            }}
        """)

    def flash_copied(self):
        self.setStyleSheet("""
            QFrame {
                background-color: rgba(16, 185, 129, 55);
                border: 1px solid rgba(52, 211, 153, 210);
                border-radius: 14px;
            }
        """)
        if self.copied_badge:
            self.copied_badge.show()
        QTimer.singleShot(850, self._reset_flash)

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
        drag.exec(Qt.CopyAction)
        self.on_drag_state_cb(False)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and not self._did_drag:
            self.flash_copied()
            self.on_click_cb(self.item)
        self._drag_start = None
        super().mouseReleaseEvent(event)


class QuickPastePopup(QWidget):
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
        self.title_label.setStyleSheet("font-size: 11px; font-weight: 600; color: #93c5fd;")
        self.timer_label = QLabel("8s")
        self.timer_label.setStyleSheet("font-size: 11px; color: #cbd5e1;")

        dismiss_btn = QPushButton("×")
        dismiss_btn.setFixedSize(18, 18)
        dismiss_btn.setCursor(Qt.PointingHandCursor)
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
        dismiss_btn.clicked.connect(self.dismiss)

        header.addWidget(self.title_label)
        header.addStretch()
        header.addWidget(self.timer_label)
        header.addWidget(dismiss_btn)
        self.layout_box.addLayout(header)

        self.slots_layout = QVBoxLayout()
        self.slots_layout.setSpacing(6)
        self.layout_box.addLayout(self.slots_layout)

        self.countdown = QTimer(self)
        self.countdown.timeout.connect(self.tick)

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
        self.render_slots()

        self.seconds_left = 8
        self.timer_label.setText("8s")
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
            btn.setStyleSheet("""
                QPushButton {
                    background: rgba(255, 255, 255, 16);
                    color: #e2e8f0;
                    border: 1px solid rgba(255, 255, 255, 25);
                    border-radius: 12px;
                    padding: 7px 10px;
                    text-align: left;
                    font-size: 12px;
                }
                QPushButton:hover {
                    background: rgba(37, 99, 235, 120);
                    border-color: rgba(96, 165, 250, 200);
                }
            """)
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
        screen = self.screen().availableGeometry()
        self.move(screen.right() - self.width() - 20, screen.bottom() - self.height() - 20)

    def tick(self):
        self.seconds_left -= 1
        if self.seconds_left <= 0:
            self.dismiss()
        else:
            self.timer_label.setText(f"{self.seconds_left}s")

    def dismiss(self):
        self.countdown.stop()
        self.slot_map.clear()
        self.hide()

    def pick_number(self, num):
        item = self.slot_map.pop(num, None)
        if item is None:
            return

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
        heading = QLabel("Appearance")
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
        button.setChecked(paused)
        button.toggled.connect(callback)
        self.layout().insertWidget(self.layout().count() - 1, button)
        note = QLabel("Paused capture skips automatic clipboard monitoring. Manual drops and saved items remain available.")
        note.setObjectName("SubLabel")
        note.setWordWrap(True)
        self.layout().insertWidget(self.layout().count() - 1, note)

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