from __future__ import annotations

from dataclasses import dataclass

from src.models.game import DownloadState, Game, GameStatus
from src.ui.theme import COLORS

@dataclass(frozen=True)
class GameAppearance:
    status_text: str
    badge_fg: str
    badge_bg: str
    busy: bool
    is_updating: bool
    is_installing: bool
    action_text: str
    action_bg: str
    action_hover: str
    action_fg: str
    can_uninstall: bool
    cover_border: str
    grayscale: bool

def appearance_for(game: Game) -> GameAppearance:
    busy = game.download_state in (DownloadState.DOWNLOADING, DownloadState.EXTRACTING)
    is_updating = busy and game.active_operation == "update"
    is_installing = busy and not is_updating

    if is_updating:
        status_text = "Atualizando"
        badge_fg, badge_bg = COLORS["warning"], "#3a3018"
    elif is_installing:
        status_text = "Instalando"
        badge_fg, badge_bg = COLORS["accent"], COLORS["bg_panel"]
    else:
        status_styles = {
            GameStatus.NOT_INSTALLED: (COLORS["text_muted"], COLORS["bg_panel"]),
            GameStatus.INSTALLED: (COLORS["success"], "#1a3320"),
            GameStatus.UPDATE_AVAILABLE: (COLORS["warning"], "#3a3018"),
            GameStatus.RUNNING: (COLORS["running"], "#1a3320"),
        }
        badge_fg, badge_bg = status_styles.get(
            game.status, (COLORS["text_dim"], COLORS["bg_panel"])
        )
        status_text = game.status.value

    if is_updating:
        action_text, action_bg, action_hover, action_fg = (
            "Atualizando...",
            COLORS["warning"],
            "#f0c93d",
            COLORS["bg_medium"],
        )
        cover_border = COLORS["warning"]
    elif is_installing:
        action_text, action_bg, action_hover, action_fg = (
            "Instalando...",
            COLORS["accent"],
            COLORS["accent_hover"],
            COLORS["bg_medium"],
        )
        cover_border = COLORS["accent"]
    elif game.status == GameStatus.RUNNING:
        action_text, action_bg, action_hover, action_fg = (
            "Encerrar",
            COLORS["danger"],
            COLORS["danger_hover"],
            "#ffffff",
        )
        cover_border = COLORS["success_hover"]
    elif game.status == GameStatus.UPDATE_AVAILABLE:
        action_text, action_bg, action_hover, action_fg = (
            "Atualizar",
            COLORS["warning"],
            "#f0c93d",
            COLORS["bg_medium"],
        )
        cover_border = COLORS["warning"]
    elif game.status == GameStatus.INSTALLED:
        if game.is_emulator:
            action_text, action_bg, action_hover, action_fg = (
                "Jogar",
                COLORS["success"],
                COLORS["success_hover"],
                COLORS["bg_medium"],
            )
        else:
            action_text, action_bg, action_hover, action_fg = (
                "Iniciar",
                COLORS["success"],
                COLORS["success_hover"],
                COLORS["bg_medium"],
            )
        cover_border = COLORS["success"]
    else:
        action_text, action_bg, action_hover, action_fg = (
            "Baixar" if game.is_emulator else "Instalar",
            COLORS["accent"],
            COLORS["accent_hover"],
            COLORS["bg_medium"],
        )
        cover_border = COLORS["text_muted"]

    grayscale = game.status == GameStatus.NOT_INSTALLED or is_installing
    can_uninstall = (
        game.status in (GameStatus.INSTALLED, GameStatus.UPDATE_AVAILABLE) and not busy
    )
    return GameAppearance(
        status_text=status_text,
        badge_fg=badge_fg,
        badge_bg=badge_bg,
        busy=busy,
        is_updating=is_updating,
        is_installing=is_installing,
        action_text=action_text,
        action_bg=action_bg,
        action_hover=action_hover,
        action_fg=action_fg,
        can_uninstall=can_uninstall,
        cover_border=cover_border,
        grayscale=grayscale,
    )

def perform_game_action(game: Game, callbacks: tuple) -> None:
    if game.download_state in (DownloadState.DOWNLOADING, DownloadState.EXTRACTING):
        return
    on_install, on_update, on_play, on_stop, _ = callbacks
    if game.status == GameStatus.RUNNING:
        on_stop(game)
    elif game.status == GameStatus.UPDATE_AVAILABLE:
        on_update(game)
    elif game.status == GameStatus.INSTALLED:
        on_play(game)
    else:
        on_install(game)
