"""Pixel-accurate, SideDock-owned screen region capture.

The visible selection and extracted OCR pixels share one logical-to-physical
coordinate mapping. Never use a logical screen rectangle directly as a
physical image source rectangle: that produces magnification / offset on DPI
scaled monitors.
"""
import math
from PySide6.QtCore import QRect, Qt, Signal
from PySide6.QtGui import QColor, QCursor, QImage, QPainter, QPen
from PySide6.QtWidgets import QWidget


def image_source_rect(image, selected, logical_size):
    """Map overlay-local logical coordinates into screenshot pixel coordinates."""
    if selected.isEmpty() or logical_size.width() <= 0 or logical_size.height() <= 0:
        return QRect()
    width = image.width()
    height = image.height()
    if width <= 0 or height <= 0:
        return QRect()
    x_scale = width / logical_size.width()
    y_scale = height / logical_size.height()
    x0 = max(0, min(width, math.floor(selected.x() * x_scale)))
    y0 = max(0, min(height, math.floor(selected.y() * y_scale)))
    x1 = max(0, min(width, math.ceil((selected.x() + selected.width()) * x_scale)))
    y1 = max(0, min(height, math.ceil((selected.y() + selected.height()) * y_scale)))
    return QRect(x0, y0, max(0, x1 - x0), max(0, y1 - y0))


def crop_pixmap_region(pixmap, selected, logical_size):
    """Return precisely the original screenshot pixels inside the visible drag."""
    image = pixmap.toImage() if hasattr(pixmap, "toImage") else pixmap
    source = image_source_rect(image, selected, logical_size)
    if source.isEmpty():
        return None
    cropped = image.copy(source)
    cropped.setDevicePixelRatio(1.0)
    return cropped


def draw_selection_overlay(painter, screenshot, frame, selection):
    """Render full screenshot at one fixed mapping, then reveal the same mapping.

    Do NOT draw the selection with source=selection. Source and target units
    differ on high-DPI screens, which was the cause of zoomed/wrong previews.
    """
    painter.setRenderHint(QPainter.SmoothPixmapTransform, False)
    source = screenshot.rect()
    painter.drawImage(frame, screenshot, source)
    painter.fillRect(frame, QColor(0, 0, 0, 115))
    if not selection.isEmpty():
        painter.save()
        painter.setClipRect(selection.intersected(frame))
        painter.drawImage(frame, screenshot, source)
        painter.restore()
        painter.setPen(QPen(QColor("#f4f4f5"), 2))
        painter.drawRect(selection)


class RegionCaptureOverlay(QWidget):
    captured = Signal(object)
    cancelled = Signal()

    def __init__(self, screen):
        super().__init__(None)
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint | Qt.Tool)
        self.setGeometry(screen.geometry())
        # Image pixel dimensions can be larger than Qt logical screen dimensions.
        # Normalize DPR so QPainter uses physical pixels as its source units.
        self.screenshot = screen.grabWindow(0).toImage()
        self.screenshot.setDevicePixelRatio(1.0)
        self.setMouseTracking(True)
        self.setCursor(Qt.CrossCursor)
        self.setFocusPolicy(Qt.StrongFocus)
        self.origin = None
        self.cursor = None

    def selection(self):
        if self.origin is None or self.cursor is None:
            return QRect()
        return QRect(self.origin, self.cursor).normalized().intersected(self.rect())

    def paintEvent(self, event):
        painter = QPainter(self)
        draw_selection_overlay(painter, self.screenshot, self.rect(), self.selection())
        painter.end()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.origin = event.position().toPoint()
            self.cursor = self.origin
            self.update()

    def mouseMoveEvent(self, event):
        if self.origin is not None:
            self.cursor = event.position().toPoint()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.LeftButton or self.origin is None:
            return
        self.cursor = event.position().toPoint()
        rect = self.selection()
        if rect.width() < 8 or rect.height() < 8:
            self.update()
            return
        image = crop_pixmap_region(self.screenshot, rect, self.size())
        self.hide()
        self.close()
        if image is None or image.isNull():
            self.cancelled.emit()
        else:
            self.captured.emit(image)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.hide()
            self.close()
            self.cancelled.emit()
        else:
            super().keyPressEvent(event)
