"""Verify the note and OCR editors are embedded SideDock widgets."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import QRect, QSize
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import QApplication, QStackedWidget

from sidedock.composer import NoteComposer, OCRWorkspace
from sidedock.region_capture import crop_pixmap_region
from sidedock.ocr import find_tesseract


class EmbeddedWorkspaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_note_entry_stays_in_dock_and_saves_text(self):
        saved = []
        note = NoteComposer(lambda text, source: saved.append((text, source)), lambda: None)
        pages = QStackedWidget()
        pages.addWidget(note)
        self.assertFalse(note.isWindow())
        note.set_content("Note inside SideDock", "note")
        note.save_button.click()
        self.assertEqual(saved, [("Note inside SideDock", "note")])

    def test_ocr_review_uses_same_embedded_editor(self):
        composer = NoteComposer(lambda *_: None, lambda: None)
        composer.set_content("recognized text", "ocr")
        pages = QStackedWidget()
        pages.addWidget(composer)
        self.assertFalse(composer.isWindow())
        self.assertEqual(composer.source, "ocr")
        self.assertEqual(composer.editor.toPlainText(), "recognized text")
        self.assertIn("OCR", composer.title.text())

    def test_ocr_workspace_has_internal_controls(self):
        panel = OCRWorkspace(lambda: None, lambda: None, lambda: None, lambda: None)
        pages = QStackedWidget()
        pages.addWidget(panel)
        self.assertFalse(panel.isWindow())
        panel.set_status("Recognizing text locally")
        self.assertIn("locally", panel.status.text())

    def test_crop_maps_logical_rectangle_to_screenshot(self):
        source = QPixmap(400, 200)
        source.fill(QColor("white"))
        result = crop_pixmap_region(source, QRect(10, 20, 60, 40), QSize(200, 100))
        self.assertEqual(result.width(), 120)
        self.assertEqual(result.height(), 80)

    def test_packaged_engine_takes_precedence(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime = Path(tmp) / "ocr"
            runtime.mkdir()
            engine = runtime / "tesseract.exe"
            engine.write_bytes(b"mock")
            import sys
            with patch.object(sys, "_MEIPASS", tmp, create=True):
                self.assertEqual(find_tesseract(), str(engine))


if __name__ == "__main__":
    unittest.main()
