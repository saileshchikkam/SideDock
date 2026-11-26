"""Regression checks for the real on-screen OCR selection at Windows DPI scales."""
import unittest
from PySide6.QtCore import QRect, QSize
from PySide6.QtGui import QColor, QImage, QPainter, QPixmap

from sidedock.region_capture import crop_pixmap_region, image_source_rect, draw_selection_overlay


class PixelAccurateRegionTests(unittest.TestCase):
    def test_150_percent_scale_uses_physical_screen_pixels(self):
        original = QImage(450, 300, QImage.Format_RGB32)
        original.fill(QColor("#ffffff"))
        for y in range(300):
            for x in range(450):
                original.setPixelColor(x, y, QColor(x % 256, y % 256, 70))
        original.setDevicePixelRatio(1.5)
        selected = QRect(52, 36, 71, 40)
        expected = QRect(78, 54, 107, 60)  # floor at start, ceil at end
        self.assertEqual(image_source_rect(original, selected, QSize(300, 200)), expected)
        result = crop_pixmap_region(original, selected, QSize(300, 200))
        self.assertEqual(result.size(), expected.size())
        self.assertEqual(result.pixelColor(0, 0), original.pixelColor(expected.x(), expected.y()))
        self.assertEqual(result.pixelColor(result.width()-1, result.height()-1),
                         original.pixelColor(expected.right(), expected.bottom()))
        self.assertEqual(result.devicePixelRatio(), 1.0)

    def test_highlight_reveals_exact_same_screenshot_not_zoomed_slice(self):
        source = QImage(400, 200, QImage.Format_RGB32)
        source.fill(QColor("#ff0000"))
        # Right side is blue. The highlighted selection is entirely on the
        # blue side, where a wrong 1:1 pixel source would show red.
        for x in range(200, 400):
            for y in range(200):
                source.setPixelColor(x, y, QColor("#0044ff"))
        source.setDevicePixelRatio(2)
        selection = QRect(140, 20, 40, 35)
        display = QImage(200, 100, QImage.Format_RGB32)
        painter = QPainter(display)
        draw_selection_overlay(painter, source, QRect(0, 0, 200, 100), selection)
        painter.end()
        self.assertEqual(display.pixelColor(150, 30), QColor("#0044ff"))
        self.assertNotEqual(display.pixelColor(150, 15), QColor("#0044ff"))
        crop = crop_pixmap_region(source, selection, QSize(200, 100))
        self.assertEqual(crop.pixelColor(0, 0), QColor("#0044ff"))

    def test_origin_and_clamping_on_fractional_scaling(self):
        screenshot = QImage(375, 225, QImage.Format_RGB32)
        screenshot.fill(QColor("white"))
        self.assertEqual(image_source_rect(screenshot, QRect(0, 0, 250, 150), QSize(250, 150)),
                         QRect(0, 0, 375, 225))
        self.assertEqual(image_source_rect(screenshot, QRect(-8, -4, 22, 15), QSize(250, 150)),
                         QRect(0, 0, 21, 17))
        self.assertIsNone(crop_pixmap_region(screenshot, QRect(), QSize(250, 150)))


if __name__ == "__main__":
    unittest.main()
