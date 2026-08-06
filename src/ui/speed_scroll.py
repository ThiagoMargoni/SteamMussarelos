from __future__ import annotations

from PySide6.QtCore import QPoint
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import QScrollArea

class SpeedScrollArea(QScrollArea):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._speed = 1.0

    def set_scroll_speed(self, speed: float) -> None:
        self._speed = max(0.5, min(3.0, float(speed)))

    def scroll_speed(self) -> float:
        return self._speed

    def wheelEvent(self, event: QWheelEvent) -> None:
        if abs(self._speed - 1.0) < 0.01:
            super().wheelEvent(event)
            return

        angle = event.angleDelta()
        pixel = event.pixelDelta()
        scaled = QWheelEvent(
            event.position(),
            event.globalPosition(),
            QPoint(int(pixel.x() * self._speed), int(pixel.y() * self._speed)),
            QPoint(int(angle.x() * self._speed), int(angle.y() * self._speed)),
            event.buttons(),
            event.modifiers(),
            event.phase(),
            event.inverted(),
            event.source(),
        )
        super().wheelEvent(scaled)
        event.accept()
