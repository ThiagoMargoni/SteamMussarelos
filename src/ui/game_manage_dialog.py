from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QEvent, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.models.game import Game, GameStatus
from src.ui.action_icons import get_settings_icon, get_uninstall_icon
from src.ui.game_style import appearance_for, perform_game_action
from src.ui.theme import (
    COLORS,
    PRIMARY_BTN_HEIGHT,
    PRIMARY_BTN_WIDTH,
    UNINSTALL_BTN,
    UNINSTALL_ICON,
    btn_style,
    font_caption,
    font_heading,
    font_small,
)

def _badge_style(bg: str, fg: str) -> str:
    return f"""
    QLabel {{
        background-color: {bg};
        color: {fg};
        border: none;
        border-radius: 6px;
        padding: 5px 14px;
        margin: 0px;
        min-height: 18px;
    }}
    """

class GameManagePopup(QFrame):
    def __init__(
        self,
        parent: QWidget,
        game: Game,
        callbacks: tuple,
        *,
        cover: QPixmap | None = None,
        on_mods: Callable[[Game], None] | None = None,
        on_configure: Callable[[Game], None] | None = None,
        uninstall_icon=None,
        on_closed: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.Widget)
        self.game = game
        self._callbacks = callbacks
        self._on_mods = on_mods
        self._on_configure = on_configure
        self._on_closed = on_closed
        self._fill = QColor(COLORS["bg_card"])
        self._edge = QColor(COLORS["border_light"])
        self._filter_on = False

        self.setObjectName("gameManagePopup")
        self.setFixedWidth(300)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
        self.setStyleSheet(
            "QFrame#gameManagePopup { background: transparent; border: none; }"
            " QFrame#gameManagePopup QLabel { background: transparent; border: none; }"
        )

        preview_w = 72 if game.is_emulator else 64
        preview_h = 72 if game.is_emulator else 90

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(0)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(12)

        self.cover_label = QLabel(self)
        self.cover_label.setFixedSize(preview_w, preview_h)
        self.cover_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cover_label.setStyleSheet(
            f"background-color: {COLORS['bg_icon']}; border: none; border-radius: 6px;"
        )
        self._set_cover(cover, preview_w, preview_h)
        top.addWidget(self.cover_label, 0, Qt.AlignmentFlag.AlignTop)

        info = QVBoxLayout()
        info.setContentsMargins(0, 0, 0, 0)
        info.setSpacing(0)

        self.name_label = QLabel(game.name, self)
        self.name_label.setFont(font_heading())
        self.name_label.setWordWrap(True)
        self.name_label.setStyleSheet(f"color: {COLORS['text']};")
        info.addWidget(self.name_label)
        info.addSpacing(8)

        meta = QHBoxLayout()
        meta.setSpacing(8)
        look = appearance_for(game)
        self.status_badge = QLabel(f"  {look.status_text}  ", self)
        self.status_badge.setFont(font_small())
        self.status_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_badge.setStyleSheet(_badge_style(look.badge_bg, look.badge_fg))
        meta.addWidget(self.status_badge, 0, Qt.AlignmentFlag.AlignVCenter)

        if game.supports_mods:
            mods_badge = QLabel("  Mods  ", self)
            mods_badge.setFont(font_small())
            mods_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            mods_badge.setStyleSheet(_badge_style(COLORS["bg_panel"], COLORS["accent"]))
            meta.addWidget(mods_badge, 0, Qt.AlignmentFlag.AlignVCenter)
        meta.addStretch(1)
        info.addLayout(meta)
        info.addSpacing(4)

        version = QLabel(
            f"v{game.installed_version}" if game.installed_version else "",
            self,
        )
        version.setFont(font_caption())
        version.setStyleSheet(f"color: {COLORS['text_dim']};")
        info.addWidget(version)
        info.addStretch(1)
        top.addLayout(info, 1)
        root.addLayout(top)
        root.addSpacing(12)

        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(8)

        action_btn = QPushButton(look.action_text, self)
        action_btn.setFlat(True)
        action_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        action_btn.setFixedSize(PRIMARY_BTN_WIDTH, PRIMARY_BTN_HEIGHT)
        action_btn.setFont(font_small())
        action_btn.setStyleSheet(
            btn_style(look.action_bg, look.action_hover, look.action_fg)
        )
        action_btn.setEnabled(not look.busy)
        action_btn.clicked.connect(self._on_action)
        actions.addWidget(action_btn)

        if game.supports_mods:
            mods_btn = QPushButton("Mods", self)
            mods_btn.setFlat(True)
            mods_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            mods_btn.setFixedSize(72, PRIMARY_BTN_HEIGHT)
            mods_btn.setFont(font_small())
            mods_btn.setStyleSheet(
                btn_style(COLORS["bg_panel"], COLORS["bg_card_hover"], COLORS["accent"])
            )
            can_mods = game.status in (
                GameStatus.INSTALLED,
                GameStatus.UPDATE_AVAILABLE,
                GameStatus.RUNNING,
            ) and not look.busy
            mods_btn.setEnabled(can_mods)
            mods_btn.clicked.connect(self._open_mods)
            actions.addWidget(mods_btn)

        if game.is_emulator:
            config_btn = QPushButton(self)
            config_btn.setFlat(True)
            config_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            config_btn.setFixedSize(UNINSTALL_BTN, UNINSTALL_BTN)
            config_btn.setIcon(get_settings_icon())
            config_btn.setIconSize(QSize(UNINSTALL_ICON, UNINSTALL_ICON))
            config_btn.setToolTip("Configurar")
            config_btn.setStyleSheet(
                btn_style(
                    COLORS["bg_panel"],
                    COLORS["bg_card_hover"],
                    COLORS["accent"],
                    COLORS["border"],
                )
            )
            can_config = game.status in (
                GameStatus.INSTALLED,
                GameStatus.UPDATE_AVAILABLE,
            ) and not look.busy
            config_btn.setEnabled(can_config)
            config_btn.clicked.connect(self._open_configure)
            actions.addWidget(config_btn)

        uninstall_btn = QPushButton(self)
        uninstall_btn.setFlat(True)
        uninstall_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        uninstall_btn.setFixedSize(UNINSTALL_BTN, UNINSTALL_BTN)
        uninstall_btn.setIcon(uninstall_icon or get_uninstall_icon())
        uninstall_btn.setIconSize(QSize(UNINSTALL_ICON, UNINSTALL_ICON))
        uninstall_btn.setStyleSheet(
            btn_style(COLORS["danger"], COLORS["danger_hover"], "#ffffff", COLORS["border"])
        )
        uninstall_btn.setEnabled(look.can_uninstall)
        uninstall_btn.clicked.connect(self._uninstall)
        actions.addWidget(uninstall_btn)
        actions.addStretch(1)
        root.addLayout(actions)

    def _set_cover(self, cover: QPixmap | None, w: int, h: int) -> None:
        if cover is None or cover.isNull():
            self.cover_label.setText("?")
            self.cover_label.setStyleSheet(
                f"color: {COLORS['text_muted']}; background-color: {COLORS['bg_icon']};"
                f" border: none; border-radius: 6px; font-weight: 700;"
            )
            return
        scaled = cover.scaled(
            w,
            h,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        if scaled.width() > w or scaled.height() > h:
            x = max(0, (scaled.width() - w) // 2)
            y = max(0, (scaled.height() - h) // 2)
            scaled = scaled.copy(x, y, w, h)
        self.cover_label.setText("")
        self.cover_label.setPixmap(scaled)

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

    def _on_action(self) -> None:
        game = self.game
        callbacks = self._callbacks
        self.close()
        QTimer.singleShot(0, lambda: perform_game_action(game, callbacks))

    def _open_mods(self) -> None:
        if self._on_mods is None:
            return
        cb = self._on_mods
        game = self.game
        self.close()
        QTimer.singleShot(0, lambda: cb(game))

    def _open_configure(self) -> None:
        if self._on_configure is None:
            return
        cb = self._on_configure
        game = self.game
        self.close()
        QTimer.singleShot(0, lambda: cb(game))

    def _uninstall(self) -> None:
        cb = self._callbacks[4]
        game = self.game
        self.close()
        QTimer.singleShot(0, lambda: cb(game))

GameManageDialog = GameManagePopup
