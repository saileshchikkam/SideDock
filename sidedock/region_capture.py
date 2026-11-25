"""SideDock-owned full-screen region selector. Does not use Windows Snipping Tool."""
from PySide6.QtCore import QRect, Qt, Signal
from PySide6.QtGui import QColor, QCursor, QPainter, QPen
from PySide6.QtWidgets import QWidget


def crop_pixmap_region(pixmap, selected, logical_size):
    """Map selection in logical screen coordinates into screenshot pixels."""
    if selected.isEmpty() or logical_size.width() <= 0 or logical_size.height() <= 0:
        return None
    image = pixmap.toImage()
    x_ratio = image.width() / logical_size.width()
    y_ratio = image.height() / logical_size.height()
    x0 = max(0, round(selected.left() * x_ratio))
    y0 = max(0, round(selected.top() * y_ratio))
    x1 = min(image.width(), round((selected.x() + selected.width()) * x_ratio))
    y1 = min(image.height(), round((selected.y() + selected.height()) * y_ratio))
    if x1 <= x0 or y1 <= y0:
        return None
    return image.copy(QRect(x0, y0, x1 - x0, y1 - y0))


class RegionCaptureOverlay(QWidget):
    captured = Signal(object)
    cancelled = Signal()

    def __init__(self, screen):
        super().__init__(None)
        self.screenshot = screen.grabWindow(0)
        self.setGeometry(screen.geometry())
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint | Qt.Tool)
        self.setMouseTracking(True)
        self.setCursor(Qt.CrossCursor)
        self.setFocusPolicy(Qt.StrongFocus)
        self.origin = None
        self.cursor = None

    def selection(self):
        if self.origin is None or self.cursor is None:
            return QRect()
        return QRect(self.origin, self.cursor).normalized()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.drawPixmap(self.rect(), self.screenshot, self.screenshot.rect())
        painter.fillRect(self.rect(), QColor(0, 0, 0, 115))
        selection = self.selection()
        if not selection.isEmpty():
            painter.drawPixmap(selection, self.screenshot, selection)
            painter.setPen(QPen(QColor("#f4f4f5"), 2))
            painter.drawRect(selection)
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
