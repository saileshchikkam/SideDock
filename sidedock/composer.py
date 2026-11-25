"""Inline SideDock workspaces. No secondary dialog windows."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QVBoxLayout, QWidget,
)


class NoteComposer(QWidget):
    """Edit notes and OCR output inside the existing dock stack."""

    def __init__(self, on_save, on_cancel):
        super().__init__()
        self.source = "note"
        self.on_save = on_save
        self.on_cancel = on_cancel

        layout = QVBoxLayout(self)
        layout.setContentsMargins(3, 6, 3, 6)
        layout.setSpacing(10)
        header = QHBoxLayout()
        self.back_button = QPushButton("← Back")
        self.back_button.setObjectName("BackBtn")
        self.back_button.setToolTip("Return to saved SideDock cards")
        self.back_button.clicked.connect(self.on_cancel)
        self.title = QLabel("Add Note")
        self.title.setObjectName("EmptyTitle")
        header.addWidget(self.back_button)
        header.addStretch()
        header.addWidget(self.title)
        layout.addLayout(header)

        self.description = QLabel("Write a note and save it among your cards.")
        self.description.setObjectName("SubLabel")
        self.description.setWordWrap(True)
        layout.addWidget(self.description)
        self.editor = QPlainTextEdit()
        self.editor.setAccessibleName("Note content")
        self.editor.setPlaceholderText("Write a note or reusable snippet…")
        self.editor.setTabChangesFocus(True)
        layout.addWidget(self.editor, stretch=1)

        bottom = QHBoxLayout()
        bottom.addStretch()
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setObjectName("HeaderBtn")
        self.cancel_button.clicked.connect(self.on_cancel)
        self.save_button = QPushButton("Save to SideDock")
        self.save_button.setObjectName("CaptureBtn")
        self.save_button.setToolTip("Save as a searchable local SideDock card")
        self.save_button.clicked.connect(self._save)
        bottom.addWidget(self.cancel_button)
        bottom.addWidget(self.save_button)
        layout.addLayout(bottom)
        self.error = QLabel("")
        self.error.setObjectName("SubLabel")
        self.error.setWordWrap(True)
        layout.addWidget(self.error)

    def set_content(self, text="", source="note"):
        self.source = source
        self.editor.setPlainText(text)
        self.error.clear()
        is_ocr = source == "ocr"
        self.title.setText("Review OCR Text" if is_ocr else "Add Note")
        self.description.setText(
            "Correct extracted text before saving it inside SideDock."
            if is_ocr else "Write a note and save it among your cards."
        )

    def _save(self):
        self.on_save(self.editor.toPlainText(), self.source)

    def show_error(self, message):
        self.error.setText(message)


class OCRWorkspace(QWidget):
    """Internal OCR controls; screenshot selection is provided by SideDock's own overlay."""

    def __init__(self, select_region, from_clipboard, from_recent, on_back):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(3, 6, 3, 6)
        layout.setSpacing(10)
        header = QHBoxLayout()
        back = QPushButton("← Back")
        back.setObjectName("BackBtn")
        back.clicked.connect(on_back)
        title = QLabel("Extract Text")
        title.setObjectName("EmptyTitle")
        header.addWidget(back)
        header.addStretch()
        header.addWidget(title)
        layout.addLayout(header)

        description = QLabel(
            "Recognize text locally. Choose a screen region or a saved screenshot; "
            "the result will open here for editing."
        )
        description.setObjectName("SubLabel")
        description.setWordWrap(True)
        layout.addWidget(description)

        for title, callback, tooltip in (
            ("Select Screen Region", select_region, "Drag over part of your screen to extract text"),
            ("Use Clipboard Image", from_clipboard, "Recognize the current screenshot on the clipboard"),
            ("Use Latest Saved Image", from_recent, "Recognize the newest saved image card"),
        ):
            button = QPushButton(title)
            button.setObjectName("CaptureBtn" if title.startswith("Select") else "HeaderBtn")
            button.setCursor(Qt.PointingHandCursor)
            button.setToolTip(tooltip)
            button.clicked.connect(callback)
            layout.addWidget(button)
        self.status = QLabel("No screenshot selected.")
        self.status.setObjectName("SubLabel")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        layout.addStretch()

    def set_status(self, message):
        self.status.setText(message)
