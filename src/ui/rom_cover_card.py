from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import QEvent, QPoint, QRect, QRectF, QSize, Qt, QTimer
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
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from src.core.emulators import has_battery_save
from src.models.game import RomEntry
from src.ui.action_icons import get_uninstall_icon
from src.ui.icon_loader import get_cached_cover, load_game_cover
from src.ui.theme import (
    COLORS,
    COVER_BORDER,
    COVER_FRAME,
    COVER_RADIUS,
    EMU_COVER_OUTER,
    EMU_COVER_SIZE,
    UNINSTALL_ICON,
    btn_style,
    font_caption,
    font_heading,
    font_small,
)

def _grayscale_pixmap(src: QPixmap) -> QPixmap:
    if src.isNull():
        return src
    gray = src.toImage().convertToFormat(QImage.Format.Format_Grayscale8)
    return QPixmap.fromImage(gray.convertToFormat(QImage.Format.Format_ARGB32))

class RomManagePopup(QFrame):
    def __init__(
        self,
        parent: QWidget,
        rom: RomEntry,
        *,
        on_play: Callable[[RomEntry], None] | None,
        on_download: Callable[[RomEntry], None] | None,
        on_save: Callable[[RomEntry, QPushButton], None] | None,
        on_remove: Callable[[RomEntry], None] | None,
        cover: QPixmap | None = None,
        on_closed: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.Widget)
        self.rom = rom
        self._on_closed = on_closed
        self._fill = QColor(COLORS["bg_card"])
        self._edge = QColor(COLORS["border_light"])
        self._filter_on = False

        self.setObjectName("romManagePopup")
        self.setFixedWidth(280)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
        self.setStyleSheet(
            "QFrame#romManagePopup { background: transparent; border: none; }"
            " QFrame#romManagePopup QLabel { background: transparent; border: none; }"
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(0)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(12)

        self.cover_label = QLabel(self)
        self.cover_label.setFixedSize(64, 64)
        self.cover_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cover_label.setStyleSheet(
            f"background-color: {COLORS['bg_icon']}; border: none; border-radius: 6px;"
        )
        if cover is not None and not cover.isNull():
            scaled = cover.scaled(
                64,
                64,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            if scaled.width() > 64 or scaled.height() > 64:
                x = max(0, (scaled.width() - 64) // 2)
                y = max(0, (scaled.height() - 64) // 2)
                scaled = scaled.copy(x, y, 64, 64)
            self.cover_label.setPixmap(scaled)
        top.addWidget(self.cover_label, 0, Qt.AlignmentFlag.AlignTop)

        info = QVBoxLayout()
        info.setContentsMargins(0, 0, 0, 0)
        info.setSpacing(2)
        name = QLabel(rom.name, self)
        name.setFont(font_heading())
        name.setWordWrap(True)
        name.setStyleSheet(f"color: {COLORS['text']}; background: transparent;")
        info.addWidget(name)
        if rom.installed:
            status = "Com save" if has_battery_save(rom) else "Sem save"
        else:
            status = "Disponível para baixar"
        detail = QLabel(status, self)
        detail.setFont(font_caption())
        detail.setStyleSheet(f"color: {COLORS['text_dim']}; background: transparent;")
        info.addWidget(detail)
        info.addStretch(1)
        top.addLayout(info, 1)
        root.addLayout(top)
        root.addSpacing(12)

        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(8)

        if rom.installed:
            play_btn = QPushButton("Jogar", self)
            play_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            play_btn.setFixedHeight(32)
            play_btn.setFont(font_small())
            play_btn.setStyleSheet(
                btn_style(COLORS["success"], COLORS["success_hover"], COLORS["bg_medium"])
            )
            if on_play is not None:
                play_btn.clicked.connect(lambda: on_play(rom))
            actions.addWidget(play_btn)

            save_btn = QPushButton("Save", self)
            save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            save_btn.setFixedSize(56, 32)
            save_btn.setFont(font_small())
            save_btn.setStyleSheet(
                btn_style(COLORS["bg_panel"], COLORS["bg_card_hover"], COLORS["accent"])
            )
            if on_save is not None:
                save_btn.clicked.connect(lambda: on_save(rom, save_btn))
            actions.addWidget(save_btn)

            remove_btn = QPushButton(self)
            remove_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            remove_btn.setFixedSize(30, 30)
            remove_btn.setIcon(get_uninstall_icon())
            remove_btn.setIconSize(QSize(UNINSTALL_ICON, UNINSTALL_ICON))
            remove_btn.setStyleSheet(
                btn_style(COLORS["danger"], COLORS["danger_hover"], "#ffffff", COLORS["border"])
            )
            remove_btn.setToolTip("Remover")
            if on_remove is not None:
                remove_btn.clicked.connect(lambda: on_remove(rom))
            actions.addWidget(remove_btn)
        else:
            dl_btn = QPushButton("Baixar", self)
            dl_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            dl_btn.setFixedHeight(32)
            dl_btn.setFont(font_small())
            dl_btn.setStyleSheet(
                btn_style(COLORS["accent"], COLORS["accent_hover"], COLORS["bg_medium"])
            )
            dl_btn.setEnabled(bool(rom.download))
            if on_download is not None:
                dl_btn.clicked.connect(lambda: on_download(rom))
            actions.addWidget(dl_btn)

        actions.addStretch(1)
        root.addLayout(actions)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = self.rect().adjusted(0, 0, -1, -1)
        painter.setPen(QPen(self._edge, 1))
        painter.setBrush(self._fill)
        painter.drawRoundedRect(rect, 10, 10)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        app = QApplication.instance()
        if app is not None and not self._filter_on:
            app.installEventFilter(self)
            self._filter_on = True
        self.raise_()
        self.setFocus(Qt.FocusReason.PopupFocusReason)

    def eventFilter(self, obj, event) -> bool:
        try:
            et = event.type()
            if et == QEvent.Type.MouseButtonPress:
                gp = (
                    event.globalPosition().toPoint()
                    if hasattr(event, "globalPosition")
                    else event.globalPos()
                )
                local = self.mapFromGlobal(gp)
                if not self.rect().contains(local):
                    QTimer.singleShot(0, self.close)
                    return False
            elif et == QEvent.Type.Wheel:
                QTimer.singleShot(0, self.close)
            elif et == QEvent.Type.KeyPress and event.key() == Qt.Key.Key_Escape:
                QTimer.singleShot(0, self.close)
                return True
        except Exception:
            QTimer.singleShot(0, self.close)
        return super().eventFilter(obj, event)

    def closeEvent(self, event) -> None:
        app = QApplication.instance()
        if app is not None and self._filter_on:
            app.removeEventFilter(self)
            self._filter_on = False
        if self._on_closed is not None:
            cb = self._on_closed
            self._on_closed = None
            cb()
        super().closeEvent(event)

class RomCoverCard(QFrame):
    def __init__(
        self,
        parent,
        rom: RomEntry,
        *,
        on_play: Callable[[RomEntry], None],
        on_download: Callable[[RomEntry], None],
        on_save: Callable[[RomEntry, QPushButton], None],
        on_remove: Callable[[RomEntry], None],
        can_play: bool = True,
        busy: bool = False,
    ) -> None:
        super().__init__(parent)
        self.rom = rom
        self._on_play = on_play
        self._on_download = on_download
        self._on_save = on_save
        self._on_remove = on_remove
        self._can_play = can_play
        self._busy = busy
        self._icon_token = 0
        self._color_pix = QPixmap()
        self._gray_pix = QPixmap()
        self._hovered = False
        self._popup: RomManagePopup | None = None
        self._edge = QColor(COLORS["border"])
        self._art_w = EMU_COVER_SIZE
        self._art_h = EMU_COVER_SIZE
        self._outer_w = EMU_COVER_OUTER
        self._outer_h = EMU_COVER_OUTER

        self.setObjectName("romCoverCard")
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(self._outer_w, self._outer_h)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setAutoFillBackground(False)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._on_context_menu)

        self._load_cover()
        self.update()

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
            if self._busy:
                return
            if self.rom.installed:
                if self._can_play:
                    self._on_play(self.rom)
            elif self.rom.download:
                self._on_download(self.rom)
        super().mouseReleaseEvent(event)

    def _on_context_menu(self, local_pos: QPoint) -> None:
        self._show_manage_popup(self.mapToGlobal(local_pos))

    def _close_popup(self) -> None:
        if self._popup is not None:
            self._popup.close()
            self._popup = None

    def _show_manage_popup(self, global_pos: QPoint) -> None:
        self._close_popup()
        host = self.window()
        if host is None:
            return
        can_play = self._can_play and not self._busy and self.rom.installed
        can_download = not self._busy and not self.rom.installed and bool(self.rom.download)
        popup = RomManagePopup(
            host,
            self.rom,
            on_play=self._run_play if can_play else None,
            on_download=self._run_download if can_download else None,
            on_save=self._on_save if self.rom.installed and not self._busy else None,
            on_remove=self._run_remove if self.rom.installed and not self._busy else None,
            cover=self._color_pix if not self._color_pix.isNull() else None,
            on_closed=lambda: setattr(self, "_popup", None),
        )
        popup.adjustSize()
        local = host.mapFromGlobal(global_pos)
        x = min(max(8, local.x()), max(8, host.width() - popup.width() - 8))
        y = min(max(8, local.y()), max(8, host.height() - popup.height() - 8))
        popup.move(x, y)
        popup.show()
        self._popup = popup

    def _run_play(self, rom: RomEntry) -> None:
        self._close_popup()
        if self._can_play and not self._busy:
            play = self._on_play
            QTimer.singleShot(0, lambda: play(rom))

    def _run_download(self, rom: RomEntry) -> None:
        self._close_popup()
        if not self._busy and rom.download:
            download = self._on_download
            QTimer.singleShot(0, lambda: download(rom))

    def _run_remove(self, rom: RomEntry) -> None:
        self._close_popup()
        if not self._busy:
            remove = self._on_remove
            QTimer.singleShot(0, lambda: remove(rom))

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        img = self._image_rect()
        path = QPainterPath()
        path.addRoundedRect(img, COVER_RADIUS, COVER_RADIUS)
        painter.setClipPath(path)

        grayscale = not self.rom.installed
        pix = self._gray_pix if grayscale and not self._gray_pix.isNull() else self._color_pix
        if pix.isNull():
            painter.fillRect(img, QColor(COLORS["bg_icon"]))
            painter.setPen(QColor(COLORS["text_muted"]))
            painter.setFont(font_heading())
            painter.drawText(img.toRect(), Qt.AlignmentFlag.AlignCenter, "?")
        else:
            painter.drawPixmap(img.toRect(), pix)

        if grayscale:
            painter.fillRect(img, QColor(20, 24, 28, 70))

        if self.rom.installed and has_battery_save(self.rom):
            self._paint_badge(painter, img, "Save", COLORS["success"])
        elif not self.rom.installed:
            self._paint_badge(painter, img, "Baixar", COLORS["accent"])

        if self._hovered:
            grad = QLinearGradient(img.left(), img.top() + img.height() * 0.4, img.left(), img.bottom())
            grad.setColorAt(0.0, QColor(0, 0, 0, 0))
            grad.setColorAt(1.0, QColor(0, 0, 0, 220))
            painter.fillRect(img, QBrush(grad))

            text_rect = QRect(
                int(img.left()) + 10,
                int(img.bottom()) - 58,
                int(img.width()) - 20,
                48,
            )
            painter.setPen(QColor(COLORS["text"]))
            painter.setFont(font_heading())
            painter.drawText(
                text_rect,
                Qt.AlignmentFlag.AlignLeft
                | Qt.AlignmentFlag.AlignBottom
                | Qt.TextFlag.TextWordWrap,
                self.rom.name,
            )

        painter.setClipping(False)
        edge = QColor(COLORS["success"] if self.rom.installed else COLORS["border"])
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(edge, COVER_BORDER, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        ring = img.adjusted(-COVER_BORDER / 2.0, -COVER_BORDER / 2.0, COVER_BORDER / 2.0, COVER_BORDER / 2.0)
        painter.drawRoundedRect(ring, COVER_RADIUS + COVER_BORDER / 2.0, COVER_RADIUS + COVER_BORDER / 2.0)

    def _paint_badge(self, painter: QPainter, img: QRectF, label: str, color: str) -> None:
        painter.setFont(font_small())
        metrics = painter.fontMetrics()
        text_w = metrics.horizontalAdvance(label)
        badge = QRectF(img.left() + 8, img.top() + 8, text_w + 16, 22)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(27, 40, 56, 220))
        painter.drawRoundedRect(badge, 6, 6)
        painter.setPen(QColor(color))
        painter.drawText(badge, Qt.AlignmentFlag.AlignCenter, label)

    def _load_cover(self) -> None:
        self._icon_token += 1
        token = self._icon_token
        icon_name = self.rom.icon

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
