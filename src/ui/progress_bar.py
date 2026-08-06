from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath
from PySide6.QtWidgets import QWidget

from src.ui.theme import COLORS

class RoundProgressBar(QWidget):
    def __init__(self, parent=None, *, height: int = 16) -> None:
        super().__init__(parent)
        self._value = 0
        self._minimum = 0
        self._maximum = 100
        self._chunk = QColor(COLORS["accent"])
        self._track = QColor(COLORS["border"])
        self.setFixedHeight(height)
        self.setMinimumWidth(40)

    def setRange(self, minimum: int, maximum: int) -> None:
        self._minimum = minimum
        self._maximum = max(minimum + 1, maximum)
        self.update()

    def setValue(self, value: int) -> None:
        self._value = max(self._minimum, min(self._maximum, int(value)))
        self.update()

    def value(self) -> int:
        return self._value

    def setChunkColor(self, color: str | QColor) -> None:
        self._chunk = QColor(color)
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(Qt.PenStyle.NoPen)

        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        radius = rect.height() / 2.0

        track = QPainterPath()
        track.addRoundedRect(rect, radius, radius)
        painter.fillPath(track, self._track)

        span = self._maximum - self._minimum
        if span <= 0 or self._value <= self._minimum:
            return

        ratio = (self._value - self._minimum) / float(span)
        fill_w = rect.width() * ratio
        if fill_w <= 0:
            return

        painter.setClipPath(track)
        painter.fillRect(QRectF(rect.left(), rect.top(), fill_w, rect.height()), self._chunk)
