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

from src.models.game import DownloadState, Game, GameStatus
from src.ui.action_icons import get_uninstall_icon
from src.ui.icon_loader import get_cached_icon, load_game_icon
from src.ui.theme import (
    CARD_HEIGHT,
    CARD_RADIUS,
    COLORS,
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
        uninstall_icon=None,
    ) -> None:
        super().__init__(parent)
        self.game = game
        self._callbacks = (on_install, on_update, on_play, on_stop, on_uninstall)
        self._icon_token = 0
        self._last_signature: tuple | None = None
        self._fill = QColor(COLORS["bg_card"])
        self._edge = QColor(COLORS["border"])

        self.setObjectName("gameCard")
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, False)
        self.setFixedHeight(CARD_HEIGHT)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setAutoFillBackground(False)

        root = QHBoxLayout(self)
        root.setContentsMargins(2, 0, 16, 0)
        root.setSpacing(0)

        self.icon_label = QLabel()
        self.icon_label.setFixedSize(ICON_SIZE, ICON_SIZE)
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label.setStyleSheet("background: transparent; border: none;")
        root.addWidget(self.icon_label, 0, Qt.AlignmentFlag.AlignVCenter)
        root.addSpacing(4)

        info = QWidget()
        info.setStyleSheet("background: transparent;")
        info_layout = QVBoxLayout(info)
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(0)
        info_layout.addStretch(1)

        self.name_label = QLabel(game.name)
        self.name_label.setFont(font_heading())
        self.name_label.setStyleSheet(f"color: {COLORS['text']}; background: transparent;")
        info_layout.addWidget(self.name_label)

        meta = QHBoxLayout()
        meta.setContentsMargins(0, 6, 0, 0)
        meta.setSpacing(10)

        self.status_badge = QLabel()
        self.status_badge.setObjectName("statusBadge")
        self.status_badge.setFont(font_small())
        self.status_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_badge.setMinimumHeight(18)
        meta.addWidget(self.status_badge, 0, Qt.AlignmentFlag.AlignVCenter)

        self.version_label = QLabel()
        self.version_label.setFont(font_caption())
        self.version_label.setStyleSheet(f"color: {COLORS['text_dim']}; background: transparent;")
        meta.addWidget(self.version_label, 0, Qt.AlignmentFlag.AlignVCenter)
        meta.addStretch(1)
        info_layout.addLayout(meta)
        info_layout.addStretch(1)
        root.addWidget(info, 1)

        root.addSpacing(8)

        actions = QWidget()
        actions.setStyleSheet("background: transparent;")
        actions_layout = QHBoxLayout(actions)
        actions_layout.setContentsMargins(0, 0, 0, 0)
        actions_layout.setSpacing(8)

        self.action_btn = QPushButton("Instalar")
        self.action_btn.setFlat(True)
        self.action_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.action_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.action_btn.setFixedSize(PRIMARY_BTN_WIDTH, PRIMARY_BTN_HEIGHT)
        self.action_btn.setFont(font_small())
        self.action_btn.clicked.connect(self._on_action)
        actions_layout.addWidget(self.action_btn)

        self.uninstall_btn = QPushButton()
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
        self.name_label.setText(game.name)
        self._last_signature = None
        self._load_icon()
        self.refresh(force=True)

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

        cached = get_cached_icon(icon_name, ICON_SIZE)
        if cached is not None:
            _on_ready(cached)
            return
        load_game_icon(icon_name, _on_ready, size=ICON_SIZE)

    def _on_action(self) -> None:
        if self.game.download_state in (DownloadState.DOWNLOADING, DownloadState.EXTRACTING):
            return
        on_install, on_update, on_play, on_stop, _ = self._callbacks
        if self.game.status == GameStatus.RUNNING:
            on_stop(self.game)
        elif self.game.status == GameStatus.UPDATE_AVAILABLE:
            on_update(self.game)
        elif self.game.status == GameStatus.INSTALLED:
            on_play(self.game)
        else:
            on_install(self.game)

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

        self.version_label.setText(f"v{g.installed_version}" if g.installed_version else "")

        busy = g.download_state in (DownloadState.DOWNLOADING, DownloadState.EXTRACTING)
        is_updating = busy and g.active_operation == "update"
        is_installing = busy and not is_updating

        if is_updating:
            status_text = "Atualizando"
            text_color, bg = COLORS["warning"], "#3a3018"
        elif is_installing:
            status_text = "Instalando"
            text_color, bg = COLORS["accent"], COLORS["bg_panel"]
        else:
            status_styles = {
                GameStatus.NOT_INSTALLED: (COLORS["text_muted"], COLORS["bg_panel"]),
                GameStatus.INSTALLED: (COLORS["success"], "#1a3320"),
                GameStatus.UPDATE_AVAILABLE: (COLORS["warning"], "#3a3018"),
                GameStatus.RUNNING: (COLORS["running"], "#1a3320"),
            }
            text_color, bg = status_styles.get(g.status, (COLORS["text_dim"], COLORS["bg_panel"]))
            status_text = g.status.value

        self.status_badge.setText(f"  {status_text}  ")
        self.status_badge.setStyleSheet(
            f"""
            QLabel#statusBadge {{
                background-color: {bg};
                color: {text_color};
                border: none;
                border-radius: 6px;
                padding: 5px 14px;
                margin: 0px;
                min-height: 18px;
            }}
            """
        )

        if busy:
            self._set_card_colors(COLORS["bg_card"], COLORS["border"])
            if is_updating:
                self._style_action("Atualizando...", COLORS["warning"], "#f0c93d", COLORS["bg_medium"])
            else:
                self._style_action("Instalando...", COLORS["accent"], COLORS["accent_hover"], COLORS["bg_medium"])
        elif g.status == GameStatus.RUNNING:
            self._set_card_colors(COLORS["bg_card_running"], COLORS["success"])
            self._style_action("Encerrar", COLORS["danger"], COLORS["danger_hover"], "#ffffff")
        elif g.status == GameStatus.UPDATE_AVAILABLE:
            self._set_card_colors(COLORS["bg_card"], COLORS["border"])
            self._style_action("Atualizar", COLORS["warning"], "#f0c93d", COLORS["bg_medium"])
        elif g.status == GameStatus.INSTALLED:
            self._set_card_colors(COLORS["bg_card"], COLORS["border"])
            self._style_action("Iniciar", COLORS["success"], COLORS["success_hover"], COLORS["bg_medium"])
        else:
            self._set_card_colors(COLORS["bg_card"], COLORS["border"])
            self._style_action("Instalar", COLORS["accent"], COLORS["accent_hover"], COLORS["bg_medium"])

        self.action_btn.setEnabled(not busy)
        can_uninstall = g.status in (GameStatus.INSTALLED, GameStatus.UPDATE_AVAILABLE) and not busy
        self.uninstall_btn.setEnabled(can_uninstall)

    def _style_action(self, text: str, bg: str, hover: str, fg: str) -> None:
        self.action_btn.setText(text)
        self.action_btn.setStyleSheet(btn_style(bg, hover, fg))
