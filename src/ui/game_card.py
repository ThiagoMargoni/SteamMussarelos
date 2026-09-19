from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from src.models.game import Game, GameStatus
from src.ui.action_icons import get_settings_icon, get_uninstall_icon
from src.ui.game_style import appearance_for, perform_game_action
from src.ui.icon_loader import get_cached_icon, load_game_icon
from src.ui.theme import (
    CARD_HEIGHT,
    CARD_RADIUS,
    COLORS,
    EMU_ICON_SIZE,
    ICON_SIZE,
    PRIMARY_BTN_HEIGHT,
    PRIMARY_BTN_WIDTH,
    UNINSTALL_BTN,
    UNINSTALL_ICON,
    btn_style,
    font_caption,
    font_heading,
    font_small,
)

class GameCard(QFrame):
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
        self._fill = QColor(COLORS["bg_card"])
        self._edge = QColor(COLORS["border"])
        self._draw_size = EMU_ICON_SIZE if game.is_emulator else ICON_SIZE

        self.setObjectName("gameCard")
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, False)
        self.setFixedHeight(CARD_HEIGHT)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setAutoFillBackground(False)

        root = QHBoxLayout(self)
        root.setContentsMargins(2, 0, 16, 0)
        root.setSpacing(0)

        self.icon_slot = QWidget(self)
        self.icon_slot.setFixedSize(ICON_SIZE, ICON_SIZE)
        self.icon_slot.setStyleSheet("background: transparent; border: none;")
        slot_layout = QHBoxLayout(self.icon_slot)
        slot_layout.setContentsMargins(0, 0, 0, 0)
        slot_layout.setSpacing(0)

        self.icon_label = QLabel(self.icon_slot)
        self.icon_label.setFixedSize(self._draw_size, self._draw_size)
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label.setStyleSheet("background: transparent; border: none;")
        slot_layout.addWidget(self.icon_label, 0, Qt.AlignmentFlag.AlignCenter)
        root.addWidget(self.icon_slot, 0, Qt.AlignmentFlag.AlignVCenter)
        root.addSpacing(4)

        info = QWidget(self)
        info.setStyleSheet("background: transparent;")
        info_layout = QVBoxLayout(info)
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(0)
        info_layout.addStretch(1)

        self.name_label = QLabel(game.name, info)
        self.name_label.setFont(font_heading())
        self.name_label.setStyleSheet(f"color: {COLORS['text']}; background: transparent;")
        info_layout.addWidget(self.name_label)

        meta = QHBoxLayout()
        meta.setContentsMargins(0, 6, 0, 0)
        meta.setSpacing(10)

        self.status_badge = QLabel(info)
        self.status_badge.setObjectName("statusBadge")
        self.status_badge.setFont(font_small())
        self.status_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_badge.setMinimumHeight(18)
        meta.addWidget(self.status_badge, 0, Qt.AlignmentFlag.AlignVCenter)

        self.mods_badge = QLabel("  Mods  ", info)
        self.mods_badge.setObjectName("modsBadge")
        self.mods_badge.setFont(font_small())
        self.mods_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.mods_badge.setMinimumHeight(18)
        self.mods_badge.setStyleSheet(
            f"""
            QLabel#modsBadge {{
                background-color: {COLORS['bg_panel']};
                color: {COLORS['accent']};
                border: none;
                border-radius: 6px;
                padding: 5px 14px;
                margin: 0px;
                min-height: 18px;
            }}
            """
        )
        self.mods_badge.setVisible(game.supports_mods)
        meta.addWidget(self.mods_badge, 0, Qt.AlignmentFlag.AlignVCenter)

        self.version_label = QLabel(info)
        self.version_label.setFont(font_caption())
        self.version_label.setStyleSheet(f"color: {COLORS['text_dim']}; background: transparent;")
        meta.addWidget(self.version_label, 0, Qt.AlignmentFlag.AlignVCenter)
        meta.addStretch(1)
        info_layout.addLayout(meta)
        info_layout.addStretch(1)
        root.addWidget(info, 1)

        root.addSpacing(8)

        actions = QWidget(self)
        actions.setStyleSheet("background: transparent;")
        actions_layout = QHBoxLayout(actions)
        actions_layout.setContentsMargins(0, 0, 0, 0)
        actions_layout.setSpacing(8)

        self.action_btn = QPushButton("Instalar", actions)
        self.action_btn.setFlat(True)
        self.action_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.action_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.action_btn.setFixedSize(PRIMARY_BTN_WIDTH, PRIMARY_BTN_HEIGHT)
        self.action_btn.setFont(font_small())
        self.action_btn.clicked.connect(self._on_action)
        actions_layout.addWidget(self.action_btn)

        self.mods_btn = QPushButton("Mods", actions)
        self.mods_btn.setFlat(True)
        self.mods_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.mods_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.mods_btn.setFixedSize(72, PRIMARY_BTN_HEIGHT)
        self.mods_btn.setFont(font_small())
        self.mods_btn.setStyleSheet(
            btn_style(COLORS["bg_panel"], COLORS["bg_card_hover"], COLORS["accent"])
        )
        self.mods_btn.clicked.connect(self._open_mods)
        self.mods_btn.setVisible(game.supports_mods)
        actions_layout.addWidget(self.mods_btn)

        self.config_btn = QPushButton(actions)
        self.config_btn.setFlat(True)
        self.config_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.config_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.config_btn.setFixedSize(UNINSTALL_BTN, UNINSTALL_BTN)
        self.config_btn.setIcon(get_settings_icon())
        self.config_btn.setIconSize(QSize(UNINSTALL_ICON, UNINSTALL_ICON))
        self.config_btn.setToolTip("Configurar")
        self.config_btn.setStyleSheet(
            btn_style(COLORS["bg_panel"], COLORS["bg_card_hover"], COLORS["accent"], COLORS["border"])
        )
        self.config_btn.clicked.connect(self._open_configure)
        self.config_btn.setVisible(game.is_emulator)
        actions_layout.addWidget(self.config_btn)

        self.uninstall_btn = QPushButton(actions)
        self.uninstall_btn.setFlat(True)
        self.uninstall_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.uninstall_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.uninstall_btn.setFixedSize(UNINSTALL_BTN, UNINSTALL_BTN)
        self.uninstall_btn.setIcon(uninstall_icon or get_uninstall_icon())
        self.uninstall_btn.setIconSize(QSize(UNINSTALL_ICON, UNINSTALL_ICON))
        self.uninstall_btn.setStyleSheet(
            btn_style(COLORS["danger"], COLORS["danger_hover"], "#ffffff", COLORS["border"])
        )
        self.uninstall_btn.clicked.connect(lambda: on_uninstall(self.game))
        actions_layout.addWidget(self.uninstall_btn)
        root.addWidget(actions, 0, Qt.AlignmentFlag.AlignVCenter)

        self._load_icon()
        self.refresh(force=True)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = self.rect().adjusted(0, 0, -1, -1)
        painter.setPen(QPen(self._edge, 1))
        painter.setBrush(self._fill)
        painter.drawRoundedRect(rect, CARD_RADIUS, CARD_RADIUS)

    def bind_game(self, game: Game) -> None:
        if self.game is game:
            self.refresh()
            return
        self.game = game
        self._draw_size = EMU_ICON_SIZE if game.is_emulator else ICON_SIZE
        self.icon_label.setFixedSize(self._draw_size, self._draw_size)
        self.name_label.setText(game.name)
        self.mods_badge.setVisible(game.supports_mods)
        self.mods_btn.setVisible(game.supports_mods)
        self.config_btn.setVisible(game.is_emulator)
        self._last_signature = None
        self._load_icon()
        self.refresh(force=True)

    def _open_mods(self) -> None:
        if self._on_mods is not None:
            self._on_mods(self.game)

    def _open_configure(self) -> None:
        if self._on_configure is not None:
            self._on_configure(self.game)

    def _set_card_colors(self, bg: str, border: str) -> None:
        fill = QColor(bg)
        edge = QColor(border)
        if fill != self._fill or edge != self._edge:
            self._fill = fill
            self._edge = edge
            self.update()

    def _load_icon(self) -> None:
        self._icon_token += 1
        token = self._icon_token
        icon_name = self.game.icon

        def _on_ready(pix: Optional[QPixmap]) -> None:
            if token != self._icon_token:
                return
            if pix is None or pix.isNull():
                self.icon_label.setPixmap(QPixmap())
                self.icon_label.setText("?")
                self.icon_label.setStyleSheet(
                    f"color: {COLORS['text_muted']}; background: transparent; "
                    f"font-size: 28px; font-weight: 700; border: none;"
                )
                return
            self.icon_label.setText("")
            self.icon_label.setPixmap(pix)
            self.icon_label.setStyleSheet("background: transparent; border: none;")

        size = self._draw_size
        cached = get_cached_icon(icon_name, size)
        if cached is not None:
            _on_ready(cached)
            return
        load_game_icon(icon_name, _on_ready, size=size)

    def _on_action(self) -> None:
        perform_game_action(self.game, self._callbacks)

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
        g = self.game
        look = appearance_for(g)

        self.version_label.setText(f"v{g.installed_version}" if g.installed_version else "")

        self.status_badge.setText(f"  {look.status_text}  ")
        self.status_badge.setStyleSheet(
            f"""
            QLabel#statusBadge {{
                background-color: {look.badge_bg};
                color: {look.badge_fg};
                border: none;
                border-radius: 6px;
                padding: 5px 14px;
                margin: 0px;
                min-height: 18px;
            }}
            """
        )

        if look.busy:
            self._set_card_colors(COLORS["bg_card"], COLORS["border"])
        elif g.status == GameStatus.RUNNING:
            self._set_card_colors(COLORS["bg_card_running"], COLORS["success"])
        else:
            self._set_card_colors(COLORS["bg_card"], COLORS["border"])

        self._style_action(look.action_text, look.action_bg, look.action_hover, look.action_fg)
        self.action_btn.setEnabled(not look.busy)
        self.uninstall_btn.setEnabled(look.can_uninstall)
        can_mods = g.supports_mods and g.status in (
            GameStatus.INSTALLED,
            GameStatus.UPDATE_AVAILABLE,
            GameStatus.RUNNING,
        ) and not look.busy
        self.mods_btn.setEnabled(can_mods)
        self.mods_badge.setVisible(g.supports_mods)
        self.mods_btn.setVisible(g.supports_mods)
        can_config = (
            g.is_emulator
            and g.status in (GameStatus.INSTALLED, GameStatus.UPDATE_AVAILABLE)
            and not look.busy
        )
        self.config_btn.setVisible(g.is_emulator)
        self.config_btn.setEnabled(can_config)

    def _style_action(self, text: str, bg: str, hover: str, fg: str) -> None:
        self.action_btn.setText(text)
        self.action_btn.setStyleSheet(btn_style(bg, hover, fg))
