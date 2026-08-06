from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QRect, QRectF, Qt
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QScrollBar,
    QSizePolicy,
    QStyle,
    QStyleOptionSlider,
    QVBoxLayout,
    QWidget,
)

from src.models.game import Game
from src.ui.speed_scroll import SpeedScrollArea
from src.ui.theme import CARD_RADIUS, COLORS, font_body

_HANDLE_W = 8
_PAD_RIGHT = 18
_PAD_LEFT = 2
_BAR_W = _HANDLE_W + _PAD_LEFT + _PAD_RIGHT

class PillScrollBar(QScrollBar):
    def __init__(self, parent=None) -> None:
        super().__init__(Qt.Orientation.Vertical, parent)
        self.setFixedWidth(_BAR_W)
        self.setStyleSheet(
            "QScrollBar { background: transparent; border: none; margin: 0; }"
        )
        self._hovered = False
        self._pressed = False
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, False)

    def enterEvent(self, event) -> None:
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        self._pressed = True
        self.update()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._pressed = False
        self.update()
        super().mouseReleaseEvent(event)

    def _handle_rect(self) -> QRect:
        opt = QStyleOptionSlider()
        self.initStyleOption(opt)
        return self.style().subControlRect(
            QStyle.ComplexControl.CC_ScrollBar,
            opt,
            QStyle.SubControl.SC_ScrollBarSlider,
            self,
        )

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.fillRect(self.rect(), Qt.GlobalColor.transparent)

        handle = self._handle_rect()
        if handle.isEmpty() or self.maximum() <= self.minimum():
            return

        pad_y = 12
        handle_w = float(_HANDLE_W)
        x = float(_PAD_LEFT)
        rect = QRectF(
            x,
            max(pad_y, handle.y()),
            handle_w,
            max(24, handle.height()),
        )
        bottom_limit = self.height() - pad_y
        if rect.bottom() > bottom_limit:
            rect.setBottom(bottom_limit)
        if rect.height() < 20:
            return

        if self._pressed or self._hovered:
            color = QColor(COLORS["border_light"])
        else:
            color = QColor(COLORS["border"])

        radius = handle_w / 2.0
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        painter.drawRoundedRect(rect, radius, radius)

class _RoundStroke(QWidget):
    def __init__(self, parent: QWidget, radius: float, color: QColor) -> None:
        super().__init__(parent)
        self._radius = radius
        self._color = color
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setBrush(Qt.BrushStyle.NoBrush)
        pen = QPen(self._color, 1.0)
        pen.setCosmetic(True)
        p.setPen(pen)
        p.drawRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), self._radius, self._radius)

class PlaceScrollFrame(QFrame):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("libraryPanel")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
        self.setAutoFillBackground(False)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.clearMask()

        self._fill = QColor(COLORS["bg_panel"])
        self._edge = QColor(COLORS["border"])
        self._radius = float(CARD_RADIUS)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._scroll = SpeedScrollArea()
        self._scroll.setObjectName("libraryScroll")
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self._scroll.setStyleSheet(
            "QScrollArea#libraryScroll { border: none; background: transparent; }"
        )
        self._scroll.setVerticalScrollBar(PillScrollBar(self._scroll))

        self._container = QWidget()
        self._container.setObjectName("libraryScrollInner")
        self._container.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self._container.setStyleSheet(
            "QWidget#libraryScrollInner { background: transparent; border: none; }"
        )
        self._layout = QVBoxLayout(self._container)
        pad = 12
        self._layout.setContentsMargins(pad, pad, pad, pad)
        self._layout.setSpacing(12)
        self._layout.addStretch(1)
        self._scroll.setWidget(self._container)

        viewport = self._scroll.viewport()
        if viewport is not None:
            viewport.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
            viewport.setAutoFillBackground(False)
            viewport.setStyleSheet("background: transparent; border: none;")

        outer.addWidget(self._scroll)

        self._stroke = _RoundStroke(self, self._radius, self._edge)
        self._stroke.raise_()

        self._items: list[Game] = []
        self._factory: Callable | None = None
        self._cards: list = []
        self._empty: QLabel | None = None

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.clearMask()
        self._stroke.setGeometry(self.rect())
        self._stroke.raise_()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        path = QPainterPath()
        path.addRoundedRect(
            QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5),
            self._radius,
            self._radius,
        )
        painter.setPen(Qt.PenStyle.NoPen)
        painter.fillPath(path, self._fill)

    def set_games(self, games: list[Game], factory: Callable) -> None:
        self.clear_cards()
        self._items = list(games)
        self._factory = factory
        if not games or not factory:
            return
        for game in games:
            card = factory(self._container, game)
            card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            self._layout.insertWidget(self._layout.count() - 1, card)
            self._cards.append(card)

    def clear_cards(self) -> None:
        for card in self._cards:
            self._layout.removeWidget(card)
            card.deleteLater()
        self._cards.clear()
        self._items = []
        self._factory = None
        if self._empty is not None:
            self._layout.removeWidget(self._empty)
            self._empty.deleteLater()
            self._empty = None

    def show_message(self, text: str) -> None:
        self.clear_cards()
        self._empty = QLabel(text)
        self._empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty.setFont(font_body())
        self._empty.setStyleSheet(
            f"color: {COLORS['text_muted']}; background: transparent; padding: 48px;"
        )
        self._layout.insertWidget(0, self._empty)

    def card_for(self, name: str):
        for card in self._cards:
            if getattr(card, "game", None) and card.game.name == name:
                return card
        return None

    def iter_cards(self):
        return list(self._cards)

    def scroll_to_top(self) -> None:
        self._scroll.verticalScrollBar().setValue(0)

    def set_scroll_speed(self, speed: float) -> None:
        self._scroll.set_scroll_speed(speed)
