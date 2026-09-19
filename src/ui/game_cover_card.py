from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import QPoint, QRect, QRectF, QSize, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QImage,
    QLinearGradient,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import QFrame, QSizePolicy, QWidget

from src.models.game import Game, GameStatus
from src.ui.game_manage_dialog import GameManagePopup
from src.ui.game_style import appearance_for, perform_game_action
from src.ui.icon_loader import get_cached_cover, load_game_cover
from src.ui.theme import (
    COLORS,
    COVER_BORDER,
    COVER_FRAME,
    COVER_HEIGHT,
    COVER_OUTER_HEIGHT,
    COVER_OUTER_WIDTH,
    COVER_RADIUS,
    COVER_WIDTH,
    EMU_COVER_OUTER,
    EMU_COVER_SIZE,
    font_caption,
    font_heading,
    font_small,
)

def _grayscale_pixmap(src: QPixmap) -> QPixmap:
    if src.isNull():
        return src
    gray = src.toImage().convertToFormat(QImage.Format.Format_Grayscale8)
    return QPixmap.fromImage(gray.convertToFormat(QImage.Format.Format_ARGB32))

class GameCoverCard(QFrame):
    def __init__(
        self,
        parent,
        game: Game,
        on_install: Callable[[Game], None],
        on_update: Callable[[Game], None],
        on_play: Callable[[Game], None],
        on_stop: Callable[[Game], None],
        on_uninstall: Callable[[Game], None],
        on_mods: Callable[[Game], None] | None = None,
        on_configure: Callable[[Game], None] | None = None,
        uninstall_icon=None,
    ) -> None:
        super().__init__(parent)
        self.game = game
        self._callbacks = (on_install, on_update, on_play, on_stop, on_uninstall)
        self._on_mods = on_mods
        self._on_configure = on_configure
        self._icon_token = 0
        self._last_signature: tuple | None = None
        self._color_pix = QPixmap()
        self._gray_pix = QPixmap()
        self._hovered = False
        self._popup: GameManagePopup | None = None
        self._edge = QColor(COLORS["border"])
        self._grayscale = True
        self._running = False
        self._supports_mods = game.supports_mods
        self._square = game.is_emulator
        self._art_w = EMU_COVER_SIZE if self._square else COVER_WIDTH
        self._art_h = EMU_COVER_SIZE if self._square else COVER_HEIGHT
        self._outer_w = EMU_COVER_OUTER if self._square else COVER_OUTER_WIDTH
        self._outer_h = EMU_COVER_OUTER if self._square else COVER_OUTER_HEIGHT

        self.setObjectName("gameCoverCard")
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(self._outer_w, self._outer_h)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setAutoFillBackground(False)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._on_context_menu)

        self._load_cover()
        self.refresh(force=True)

    def sizeHint(self) -> QSize:
        return QSize(self._outer_w, self._outer_h)

    def _image_rect(self) -> QRectF:
        return QRectF(COVER_FRAME, COVER_FRAME, self._art_w, self._art_h)

    def enterEvent(self, event) -> None:
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        pos = event.position() if hasattr(event, "position") else event.pos()
        if event.button() == Qt.MouseButton.LeftButton and self._image_rect().contains(pos):
            perform_game_action(self.game, self._callbacks)
        super().mouseReleaseEvent(event)

    def _on_context_menu(self, local_pos: QPoint) -> None:
        self._show_manage_popup(self.mapToGlobal(local_pos))

    def close_manage_popup(self) -> None:
        self._close_popup()

    def _close_popup(self) -> None:
        if self._popup is not None:
            self._popup.close()
            self._popup = None

    def _show_manage_popup(self, global_pos: QPoint) -> None:
        self._close_popup()
        host = self.window()
        if host is None:
            return
        popup = GameManagePopup(
            host,
            self.game,
            self._callbacks,
            cover=self._color_pix if not self._color_pix.isNull() else None,
            on_mods=self._on_mods,
            on_configure=self._on_configure,
            on_closed=lambda: setattr(self, "_popup", None),
        )
        popup.adjustSize()
        local = host.mapFromGlobal(global_pos)
        x = min(max(8, local.x()), max(8, host.width() - popup.width() - 8))
        y = min(max(8, local.y()), max(8, host.height() - popup.height() - 8))
        popup.move(x, y)
        popup.show()
        self._popup = popup

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        img = self._image_rect()
        path = QPainterPath()
        path.addRoundedRect(img, COVER_RADIUS, COVER_RADIUS)
        painter.setClipPath(path)

        pix = self._gray_pix if self._grayscale and not self._gray_pix.isNull() else self._color_pix
        if pix.isNull():
            painter.fillRect(img, QColor(COLORS["bg_icon"]))
            painter.setPen(QColor(COLORS["text_muted"]))
            painter.setFont(font_heading())
            painter.drawText(img.toRect(), Qt.AlignmentFlag.AlignCenter, "?")
        else:
            painter.drawPixmap(img.toRect(), pix)

        if self._grayscale:
            painter.fillRect(img, QColor(20, 24, 28, 70))

        if self._running:
            painter.fillRect(img, QColor(89, 191, 64, 48))
            self._paint_running_badge(painter, img)
        elif self._supports_mods:
            self._paint_mods_badge(painter, img)

        if self._hovered:
            grad = QLinearGradient(img.left(), img.top() + img.height() * 0.4, img.left(), img.bottom())
            grad.setColorAt(0.0, QColor(0, 0, 0, 0))
            grad.setColorAt(1.0, QColor(0, 0, 0, 220))
            painter.fillRect(img, QBrush(grad))

            if self._running:
                hint = "Clique para encerrar"
                name_color = QColor(COLORS["danger_hover"])
            else:
                hint = ""
                name_color = QColor(COLORS["text"])

            text_rect = QRect(
                int(img.left()) + 10,
                int(img.bottom()) - (72 if hint else 58),
                int(img.width()) - 20,
                48,
            )
            painter.setPen(name_color if self._running else QColor(COLORS["text"]))
            painter.setFont(font_heading())
            painter.drawText(
                text_rect,
                Qt.AlignmentFlag.AlignLeft
                | Qt.AlignmentFlag.AlignBottom
                | Qt.TextFlag.TextWordWrap,
                self.game.name,
            )
            if hint:
                painter.setPen(QColor(COLORS["text"]))
                painter.setFont(font_caption())
                painter.drawText(
                    QRect(int(img.left()) + 10, int(img.bottom()) - 24, int(img.width()) - 20, 16),
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                    hint,
                )

        painter.setClipping(False)
        border_w = COVER_BORDER + (1 if self._running else 0)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(
            QPen(
                self._edge,
                border_w,
                Qt.PenStyle.SolidLine,
                Qt.PenCapStyle.RoundCap,
                Qt.PenJoinStyle.RoundJoin,
            )
        )
        ring = img.adjusted(-border_w / 2.0, -border_w / 2.0, border_w / 2.0, border_w / 2.0)
        painter.drawRoundedRect(ring, COVER_RADIUS + border_w / 2.0, COVER_RADIUS + border_w / 2.0)

    def _paint_running_badge(self, painter: QPainter, img: QRectF) -> None:
        label = "Em execução"
        painter.setFont(font_small())
        metrics = painter.fontMetrics()
        text_w = metrics.horizontalAdvance(label)
        badge = QRectF(img.left() + 8, img.top() + 8, text_w + 22, 22)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(26, 51, 32, 230))
        painter.drawRoundedRect(badge, 6, 6)
        painter.setBrush(QColor(COLORS["success"]))
        painter.drawEllipse(QRectF(badge.left() + 7, badge.center().y() - 3.5, 7, 7))
        painter.setPen(QColor(COLORS["success"]))
        painter.drawText(
            QRectF(badge.left() + 16, badge.top(), badge.width() - 18, badge.height()),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            label,
        )

    def _paint_mods_badge(self, painter: QPainter, img: QRectF) -> None:
        label = "Mods"
        painter.setFont(font_small())
        metrics = painter.fontMetrics()
        text_w = metrics.horizontalAdvance(label)
        badge = QRectF(img.left() + 8, img.top() + 8, text_w + 16, 22)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(27, 40, 56, 220))
        painter.drawRoundedRect(badge, 6, 6)
        painter.setPen(QColor(COLORS["accent"]))
        painter.drawText(badge, Qt.AlignmentFlag.AlignCenter, label)

    def bind_game(self, game: Game) -> None:
        if self.game is game:
            self.refresh()
            return
        self.game = game
        self._supports_mods = game.supports_mods
        self._square = game.is_emulator
        self._art_w = EMU_COVER_SIZE if self._square else COVER_WIDTH
        self._art_h = EMU_COVER_SIZE if self._square else COVER_HEIGHT
        self._outer_w = EMU_COVER_OUTER if self._square else COVER_OUTER_WIDTH
        self._outer_h = EMU_COVER_OUTER if self._square else COVER_OUTER_HEIGHT
        self.setFixedSize(self._outer_w, self._outer_h)
        self._last_signature = None
        self._load_cover()
        self.refresh(force=True)

    def _load_cover(self) -> None:
        self._icon_token += 1
        token = self._icon_token
        icon_name = self.game.icon

        def _on_ready(pix: Optional[QPixmap]) -> None:
            if token != self._icon_token:
                return
            if pix is None or pix.isNull():
                self._color_pix = QPixmap()
                self._gray_pix = QPixmap()
                self.update()
                return
            self._color_pix = pix
            self._gray_pix = _grayscale_pixmap(pix)
            self.update()

        cached = get_cached_cover(icon_name, self._art_w, self._art_h)
        if cached is not None:
            _on_ready(cached)
            return
        load_game_cover(icon_name, _on_ready, self._art_w, self._art_h)

    def _signature(self) -> tuple:
        g = self.game
        return (
            g.status,
            g.installed_version,
            g.version,
            g.download_state,
            g.active_operation,
            round(g.download_progress),
        )

    def refresh(self, force: bool = False) -> None:
        sig = self._signature()
        if not force and sig == self._last_signature:
            return
        self._last_signature = sig
        look = appearance_for(self.game)
        self._grayscale = look.grayscale
        self._running = self.game.status == GameStatus.RUNNING
        self._supports_mods = self.game.supports_mods
        if self._running:
            self._edge = QColor(COLORS["success_hover"])
        else:
            self._edge = QColor(look.cover_border)
        self.update()
