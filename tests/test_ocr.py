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
        paths = []
        commands = []
        def run(args, **kwargs):
            commands.append(args)
            paths.append(args[1])
            with open(args[1], "rb") as image:
                inspected.append(image.read())
            return Mock(stdout="  Sample text  ")
        with patch("sidedock.ocr.subprocess.run", side_effect=run):
            self.assertEqual(extract_text_from_png(png, executable="tesseract"), "Sample text")
        self.assertEqual(inspected, [png])
        self.assertIn('--psm', commands[0])
        self.assertEqual(commands[0][commands[0].index('--psm') + 1], '6')
        self.assertTrue(paths[0].endswith(".png"))
        from pathlib import Path
        self.assertFalse(Path(paths[0]).exists())

if __name__ == "__main__":
    unittest.main()
