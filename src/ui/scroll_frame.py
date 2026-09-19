from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QRect, QRectF, QSize, Qt, QTimer
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

from src.core.settings import LAYOUT_COVERS, LAYOUT_LIST
from src.models.game import Game
from src.ui.flow_layout import FlowLayout
from src.ui.speed_scroll import SpeedScrollArea
from src.ui.theme import (
    CARD_RADIUS,
    COLORS,
    COVER_OUTER_HEIGHT,
    COVER_OUTER_WIDTH,
    font_body,
)

_HANDLE_W = 8
_PAD_RIGHT = 10
_PAD_LEFT = 2
_BAR_W = _HANDLE_W + _PAD_LEFT + _PAD_RIGHT
_CONTENT_PAD = 16
_COVER_GAP = 14

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
        p.drawRoundedRect(
            QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), self._radius, self._radius
        )

class _LibraryInner(QWidget):
    def hasHeightForWidth(self) -> bool:
        layout = self.layout()
        return bool(layout is not None and layout.hasHeightForWidth())

    def heightForWidth(self, width: int) -> int:
        layout = self.layout()
        if layout is not None and layout.hasHeightForWidth():
            return max(1, layout.heightForWidth(width))
        return super().heightForWidth(width)

    def sizeHint(self) -> QSize:
        layout = self.layout()
        if layout is not None and layout.hasHeightForWidth():
            width = self.width()
            if width <= 0 and self.parentWidget() is not None:
                width = self.parentWidget().width()
            if width <= 0:
                width = COVER_OUTER_WIDTH * 3 + _COVER_GAP * 2 + _CONTENT_PAD * 2
            return QSize(width, self.heightForWidth(width))
        if layout is not None:
            return layout.sizeHint()
        return super().sizeHint()

    def minimumSizeHint(self) -> QSize:
        layout = self.layout()
        if layout is not None and layout.hasHeightForWidth():
            return QSize(
                COVER_OUTER_WIDTH + _CONTENT_PAD * 2,
                COVER_OUTER_HEIGHT + _CONTENT_PAD * 2,
            )
        if layout is not None:
            return layout.minimumSize()
        return super().minimumSizeHint()

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

        viewport = self._scroll.viewport()
        if viewport is not None:
            viewport.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
            viewport.setAutoFillBackground(False)
            viewport.setStyleSheet("background: transparent; border: none;")

        outer.addWidget(self._scroll)

        self._stroke = _RoundStroke(self, self._radius, self._edge)
        self._stroke.raise_()

        self._graveyard = QWidget(self)
        self._graveyard.hide()
        self._graveyard.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
        self._graveyard.resize(0, 0)

        self._items: list[Game] = []
        self._factory: Callable | None = None
        self._cards: list = []
        self._empty: QLabel | None = None
        self._layout_mode = LAYOUT_LIST
        self._container: QWidget | None = None
        self._layout = None
        self._recreate_container(LAYOUT_LIST)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.clearMask()
        self._stroke.setGeometry(self.rect())
        self._stroke.raise_()
        if self._layout_mode == LAYOUT_COVERS:
            self._sync_cover_height()

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

    def _bin_widget(self, w: QWidget | None) -> None:
        if w is None:
            return
        w.hide()
        w.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
        w.setParent(self._graveyard)
        w.deleteLater()

    def _dispose_widget(self, old: QWidget | None) -> None:
        self._bin_widget(old)

    def _take_scroll_widget(self) -> None:
        current = self._scroll.widget()
        if current is None:
            return
        self._bin_widget(current)

    def _clear_container_contents(self) -> None:
        if self._container is None or self._layout is None:
            return
        while self._layout.count():
            item = self._layout.takeAt(0)
            w = item.widget()
            if w is not None:
                self._bin_widget(w)
        self._cards = []
        self._empty = None
        if self._layout_mode == LAYOUT_LIST or isinstance(self._layout, QVBoxLayout):
            self._layout.addStretch(1)

    def _recreate_container(self, mode: str) -> None:
        self._take_scroll_widget()

        self._cards = []
        self._items = []
        self._factory = None
        self._empty = None
        self._layout_mode = mode if mode in (LAYOUT_LIST, LAYOUT_COVERS) else LAYOUT_LIST

        self._container = _LibraryInner()
        self._container.setObjectName("libraryScrollInner")
        self._container.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self._container.setStyleSheet(
            "QWidget#libraryScrollInner { background: transparent; border: none; }"
        )
        pad = _CONTENT_PAD
        if self._layout_mode == LAYOUT_COVERS:
            self._scroll.setWidgetResizable(False)
            self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
            self._container.setSizePolicy(
                QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
            )
            self._layout = FlowLayout(
                self._container,
                margin_left=pad,
                margin_top=pad,
                margin_right=pad,
                margin_bottom=pad,
                hspacing=_COVER_GAP,
                vspacing=_COVER_GAP,
            )
        else:
            self._scroll.setWidgetResizable(True)
            self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            self._container.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
            )
            self._layout = QVBoxLayout(self._container)
            self._layout.setContentsMargins(pad, pad, pad, pad)
            self._layout.setSpacing(12)
            self._layout.addStretch(1)
        self._scroll.setWidget(self._container)

    def _sync_cover_height(self) -> None:
        if self._layout_mode != LAYOUT_COVERS or self._container is None:
            return
        viewport = self._scroll.viewport()
        if viewport is None:
            return
        width = max(1, viewport.width())
        content_h = max(1, self._container.heightForWidth(width))
        height = max(content_h, viewport.height())
        if self._container.size() != QSize(width, height):
            self._container.setFixedSize(width, height)
        self._layout.setGeometry(self._container.rect())
        self._scroll.updateGeometry()

    def set_games(
        self, games: list[Game], factory: Callable, layout_mode: str = LAYOUT_LIST
    ) -> None:
        self.set_library(games, factory, layout_mode=layout_mode)

    def set_library(
        self,
        games: list[Game],
        factory: Callable,
        layout_mode: str = LAYOUT_LIST,
        append_sections: Callable | None = None,
    ) -> None:
        has_sections = append_sections is not None
        mode = layout_mode if layout_mode in (LAYOUT_LIST, LAYOUT_COVERS) else LAYOUT_LIST
        want_mixed = has_sections and mode == LAYOUT_COVERS
        same_mode = (
            self._container is not None
            and self._layout is not None
            and (
                (want_mixed and self._layout_mode == LAYOUT_COVERS and isinstance(self._layout, QVBoxLayout))
                or (
                    not want_mixed
                    and self._layout_mode == mode
                    and (
                        (mode == LAYOUT_COVERS and isinstance(self._layout, FlowLayout))
                        or (mode == LAYOUT_LIST and isinstance(self._layout, QVBoxLayout))
                    )
                )
            )
        )

        self._scroll.setUpdatesEnabled(False)
        viewport = self._scroll.viewport()
        if viewport is not None:
            viewport.setUpdatesEnabled(False)
        try:
            list_reuse = (
                mode == LAYOUT_LIST
                and not has_sections
                and same_mode
                and isinstance(self._layout, QVBoxLayout)
            )

            if self._container is not None:
                self._container.hide()

            if list_reuse:
                self._fill_list_games(games, factory)
            else:
                if same_mode:
                    self._clear_container_contents()
                elif want_mixed:
                    self._recreate_mixed_container()
                else:
                    self._recreate_container(mode)

                self._items = list(games)
                self._factory = factory

                if mode == LAYOUT_COVERS and not has_sections:
                    for game in games:
                        card = factory(self._container, game)
                        card.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
                        self._layout.addWidget(card)
                        self._cards.append(card)
                    self._layout.invalidate()
                    self._container.updateGeometry()
                    QTimer.singleShot(0, self._sync_cover_height)
                elif mode == LAYOUT_COVERS and has_sections:
                    flow_host = QWidget(self._container)
                    flow_host.setStyleSheet("background: transparent;")
                    flow = FlowLayout(
                        flow_host,
                        margin_left=0,
                        margin_top=0,
                        margin_right=0,
                        margin_bottom=0,
                        hspacing=_COVER_GAP,
                        vspacing=_COVER_GAP,
                    )
                    for game in games:
                        card = factory(flow_host, game)
                        card.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
                        flow.addWidget(card)
                        self._cards.append(card)
                    self._layout.insertWidget(self._layout.count() - 1, flow_host)
                    if append_sections is not None:
                        append_sections(self._container, self._layout, self._cards)
                    self._layout.invalidate()
                    self._container.updateGeometry()
                    QTimer.singleShot(0, self._sync_cover_height)
                else:
                    self._fill_list_games(games, factory)
                    if append_sections is not None:
                        append_sections(self._container, self._layout, self._cards)
        finally:
            if self._container is not None:
                self._container.show()
            if viewport is not None:
                viewport.setUpdatesEnabled(True)
            self._scroll.setUpdatesEnabled(True)

    def _fill_list_games(self, games: list[Game], factory: Callable) -> None:
        if self._container is None or self._layout is None:
            return
        if self._empty is not None:
            self._layout.removeWidget(self._empty)
            self._bin_widget(self._empty)
            self._empty = None

        stretch_idx = self._layout.count() - 1
        if stretch_idx < 0:
            self._layout.addStretch(1)
            stretch_idx = 0

        while len(self._cards) > len(games):
            card = self._cards.pop()
            self._layout.removeWidget(card)
            self._bin_widget(card)

        for i, game in enumerate(games):
            if i < len(self._cards):
                card = self._cards[i]
                binder = getattr(card, "bind_game", None)
                if callable(binder):
                    binder(game)
                else:
                    self._layout.removeWidget(card)
                    self._bin_widget(card)
                    card = factory(self._container, game)
                    card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
                    self._layout.insertWidget(i, card)
                    self._cards[i] = card
            else:
                card = factory(self._container, game)
                card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
                self._layout.insertWidget(self._layout.count() - 1, card)
                self._cards.append(card)

        self._items = list(games)
        self._factory = factory

    def _recreate_mixed_container(self) -> None:
        self._take_scroll_widget()

        self._cards = []
        self._items = []
        self._factory = None
        self._empty = None
        self._layout_mode = LAYOUT_COVERS

        self._container = _LibraryInner()
        self._container.setObjectName("libraryScrollInner")
        self._container.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self._container.setStyleSheet(
            "QWidget#libraryScrollInner { background: transparent; border: none; }"
        )
        pad = _CONTENT_PAD
        self._scroll.setWidgetResizable(True)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._container.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum
        )
        self._layout = QVBoxLayout(self._container)
        self._layout.setContentsMargins(pad, pad, pad, pad)
        self._layout.setSpacing(12)
        self._layout.addStretch(1)
        self._scroll.setWidget(self._container)

    def clear_cards(self) -> None:
        self._scroll.setUpdatesEnabled(False)
        try:
            self._recreate_container(self._layout_mode)
        finally:
            self._scroll.setUpdatesEnabled(True)

    def show_message(self, text: str) -> None:
        self._scroll.setUpdatesEnabled(False)
        try:
            if (
                self._container is not None
                and self._layout is not None
                and self._layout_mode == LAYOUT_LIST
                and isinstance(self._layout, QVBoxLayout)
            ):
                self._clear_container_contents()
            else:
                self._recreate_container(LAYOUT_LIST)
            self._empty = QLabel(text)
            self._empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._empty.setFont(font_body())
            self._empty.setStyleSheet(
                f"color: {COLORS['text_muted']}; background: transparent; padding: 48px;"
            )
            self._layout.insertWidget(0, self._empty)
        finally:
            if self._container is not None:
                self._container.show()
            self._scroll.setUpdatesEnabled(True)

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
