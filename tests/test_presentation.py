import unittest

from sidedock.presentation import card_kind, preview_text


class PresentationTests(unittest.TestCase):
    def test_kind_labels(self):
        self.assertEqual(card_kind({"type": "image"}), "IMAGE")
        self.assertEqual(card_kind({"type": "file", "name": "report.pdf"}), "PDF")
        self.assertEqual(card_kind({"type": "file", "name": "folder"}), "FILE")
        self.assertEqual(card_kind({"type": "text", "content": "https://example.com/a"}), "LINK")
        self.assertEqual(card_kind({"type": "text", "content": "https://example.com a"}), "TEXT")
        self.assertEqual(card_kind({"type": "text", "content": "http://["}), "TEXT")

    def test_preview_does_not_change_source(self):
        payload = "  code\n" + "x" * 200
        self.assertEqual(len(preview_text(payload)), 160)
        self.assertTrue(preview_text(payload).endswith("…"))
        self.assertTrue(payload.startswith("  code\n"))
        self.assertEqual(preview_text("short"), "short")
