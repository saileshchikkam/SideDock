"""SideDock's vector mark, independent of installed resource paths."""
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap


def app_icon():
    icon = QIcon()
    for size in (16, 24, 32, 48, 64, 128, 256):
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.scale(size / 100, size / 100)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#18181b"))
        painter.drawRoundedRect(QRectF(3, 3, 94, 94), 23, 23)
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(QColor("#f4f4f5"), 3))
        painter.drawRoundedRect(QRectF(19, 23, 62, 54), 8, 8)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#f4f4f5"))
        painter.drawRoundedRect(QRectF(66, 28, 10, 44), 4, 4)
        painter.setBrush(QColor("#71717a"))
        for y, width in ((35, 25), (46, 19), (57, 23)):
            painter.drawRoundedRect(QRectF(27, y, width, 3), 1.5, 1.5)
        painter.end()
        icon.addPixmap(pixmap)
    return icon
