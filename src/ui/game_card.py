from __future__ import annotations

from typing import Callable, Optional

import customtkinter as ctk

from src.models.game import DownloadState, Game, GameStatus
from src.ui.icon_loader import apply_icon_to_label, load_game_icon
from src.ui.theme import (
    BTN_HEIGHT,
    BTN_WIDTH,
    CARD_HEIGHT,
    CARD_RADIUS,
    COLORS,
    FONT_BODY,
    FONT_CAPTION,
    FONT_HEADING,
    FONT_SMALL,
    ICON_SIZE,
)

class GameCard(ctk.CTkFrame):
    def __init__(
        self,
        master,
        game: Game,
        on_install: Callable[[Game], None],
        on_update: Callable[[Game], None],
        on_play: Callable[[Game], None],
        on_stop: Callable[[Game], None],
        on_uninstall: Callable[[Game], None],
        **kwargs,
    ) -> None:
        super().__init__(
            master,
            fg_color=COLORS["bg_card"],
            corner_radius=CARD_RADIUS,
            height=CARD_HEIGHT,
            border_width=1,
            border_color=COLORS["border"],
            **kwargs,
        )
        self.pack_propagate(False)
        self.game = game
        self._callbacks = (on_install, on_update, on_play, on_stop, on_uninstall)
        self._icon_ref: Optional[ctk.CTkImage] = None

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.icon_frame = ctk.CTkFrame(
            self,
            width=ICON_SIZE + 16,
            height=ICON_SIZE + 16,
            fg_color=COLORS["bg_icon"],
            corner_radius=8,
            border_width=1,
            border_color=COLORS["border"],
        )
        self.icon_frame.grid(row=0, column=0, padx=(14, 12), pady=12, sticky="ns")
        self.icon_frame.grid_propagate(False)

        self.icon_label = ctk.CTkLabel(
            self.icon_frame,
            text="",
            width=ICON_SIZE,
            height=ICON_SIZE,
        )
        self.icon_label.place(relx=0.5, rely=0.5, anchor="center")

        info = ctk.CTkFrame(self, fg_color="transparent")
        info.grid(row=0, column=1, sticky="nsew", pady=12)

        self.name_label = ctk.CTkLabel(
            info,
            text=game.name,
            font=FONT_HEADING,
            text_color=COLORS["text"],
            anchor="w",
        )
        self.name_label.pack(fill="x", anchor="w")

        self.version_label = ctk.CTkLabel(
            info,
            text="",
            font=FONT_CAPTION,
            text_color=COLORS["text_dim"],
            anchor="w",
        )
        self.version_label.pack(fill="x", anchor="w", pady=(4, 0))

        status_row = ctk.CTkFrame(info, fg_color="transparent")
        status_row.pack(fill="x", anchor="w", pady=(8, 0))

        self.status_badge = ctk.CTkLabel(
            status_row,
            text="",
            font=FONT_SMALL,
            corner_radius=6,
            fg_color=COLORS["bg_panel"],
            text_color=COLORS["text_dim"],
            padx=10,
            pady=4,
        )
        self.status_badge.pack(side="left")

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=0, column=2, padx=(0, 14), pady=12, sticky="e")

        btn_kw = dict(
            width=BTN_WIDTH,
            height=BTN_HEIGHT,
            corner_radius=6,
            font=FONT_SMALL,
        )

        self.action_btn = ctk.CTkButton(
            btn_frame,
            text="Instalar",
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            text_color=COLORS["bg_medium"],
            command=self._on_action,
            **btn_kw,
        )
        self.action_btn.pack(pady=3)

        self.secondary_btn = ctk.CTkButton(
            btn_frame,
            text="Atualizar",
            fg_color=COLORS["bg_panel"],
            hover_color=COLORS["bg_card_hover"],
            text_color=COLORS["text"],
            command=lambda: on_update(game),
            **btn_kw,
        )
        self.secondary_btn.pack(pady=3)

        self.uninstall_btn = ctk.CTkButton(
            btn_frame,
            text="Desinstalar",
            fg_color="transparent",
            hover_color=COLORS["danger"],
            border_width=1,
            border_color=COLORS["border"],
            text_color=COLORS["text_dim"],
            command=lambda: on_uninstall(game),
            **btn_kw,
        )
        self.uninstall_btn.pack(pady=3)

        self._load_icon()
        self.refresh()

    def _load_icon(self) -> None:
        def _on_ready(img: Optional[ctk.CTkImage]) -> None:
            def _apply() -> None:
                self._icon_ref = apply_icon_to_label(self.icon_label, img, placeholder="?")

            self.after(0, _apply)

        load_game_icon(self.game.icon, _on_ready)

    def _on_action(self) -> None:
        on_install, _, on_play, on_stop, _ = self._callbacks
        if self.game.status == GameStatus.RUNNING:
            on_stop(self.game)
        elif self.game.status in (GameStatus.INSTALLED, GameStatus.UPDATE_AVAILABLE):
            on_play(self.game)
        else:
            on_install(self.game)

    def refresh(self) -> None:
        g = self.game
        installed = g.installed_version or "—"
        self.version_label.configure(text=f"Versão instalada: {installed}   ·   Remota: {g.version}")

        status_styles = {
            GameStatus.NOT_INSTALLED: (COLORS["text_muted"], COLORS["bg_panel"]),
            GameStatus.INSTALLED: (COLORS["success"], "#1a3320"),
            GameStatus.UPDATE_AVAILABLE: (COLORS["warning"], "#3a3018"),
            GameStatus.RUNNING: (COLORS["running"], "#1a3320"),
        }
        text_color, bg = status_styles.get(g.status, (COLORS["text_dim"], COLORS["bg_panel"]))
        self.status_badge.configure(text=f"  {g.status.value}  ", text_color=text_color, fg_color=bg)

        busy = g.download_state in (DownloadState.DOWNLOADING, DownloadState.EXTRACTING)

        if g.status == GameStatus.RUNNING:
            self.configure(fg_color=COLORS["bg_card_running"], border_color=COLORS["success"])
            self.action_btn.configure(text="Encerrar", fg_color=COLORS["danger"], hover_color=COLORS["danger_hover"])
        elif g.status in (GameStatus.INSTALLED, GameStatus.UPDATE_AVAILABLE):
            self.configure(fg_color=COLORS["bg_card"], border_color=COLORS["border"])
            self.action_btn.configure(text="Iniciar", fg_color=COLORS["success"], hover_color=COLORS["success_hover"])
        else:
            self.configure(fg_color=COLORS["bg_card"], border_color=COLORS["border"])
            self.action_btn.configure(text="Instalar", fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"])

        self.action_btn.configure(state="disabled" if busy else "normal")
        self.secondary_btn.configure(state="normal" if g.status == GameStatus.UPDATE_AVAILABLE and not busy else "disabled")

        can_uninstall = g.status in (GameStatus.INSTALLED, GameStatus.UPDATE_AVAILABLE) and not busy
        self.uninstall_btn.configure(state="normal" if can_uninstall else "disabled")
