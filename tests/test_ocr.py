import subprocess
import unittest
from unittest.mock import patch, Mock

from sidedock.ocr import extract_text_from_png


class OcrTests(unittest.TestCase):
    def test_rejects_invalid_image(self):
        with self.assertRaises(ValueError):
            extract_text_from_png(b"not an image", executable="tesseract")

    def test_reads_locally_and_deletes_temporary_image(self):
        png = b"\x89PNG\r\n\x1a\n" + b"fake"
        inspected = []
        def run(args, **kwargs):
            with open(args[1], "rb") as image:
                inspected.append(image.read())
            return Mock(stdout="  Sample text  ")
        with patch("sidedock.ocr.subprocess.run", side_effect=run):
            self.assertEqual(extract_text_from_png(png, executable="tesseract"), "Sample text")
        self.assertEqual(inspected, [png])

if __name__ == "__main__":
    unittest.main()
