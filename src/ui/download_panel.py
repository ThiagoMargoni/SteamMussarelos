from __future__ import annotations

import customtkinter as ctk

from src.models.game import DownloadState, Game
from src.ui.theme import COLORS, FONT_NORMAL, FONT_SMALL

class DownloadPanel(ctk.CTkFrame):
    def __init__(self, master, **kwargs) -> None:
        super().__init__(master, fg_color=COLORS["bg_medium"], height=120, **kwargs)
        self.pack_propagate(False)

        self.title_label = ctk.CTkLabel(
            self,
            text="Downloads",
            font=FONT_NORMAL,
            text_color=COLORS["text_dim"],
            anchor="w",
        )
        self.title_label.pack(fill="x", padx=16, pady=(8, 0))

        self.content = ctk.CTkFrame(self, fg_color="transparent")
        self.content.pack(fill="both", expand=True, padx=16, pady=8)

        self.empty_label = ctk.CTkLabel(
            self.content,
            text="Nenhum download em andamento",
            font=FONT_SMALL,
            text_color=COLORS["text_dim"],
        )
        self.empty_label.pack(expand=True)

        self._active_frame: ctk.CTkFrame | None = None
        self._progress_bar: ctk.CTkProgressBar | None = None
        self._pct_label: ctk.CTkLabel | None = None
        self._state_label: ctk.CTkLabel | None = None
        self._detail_label: ctk.CTkLabel | None = None
        self._current_game: Game | None = None

    def update_game(self, game: Game) -> None:
        if game.download_state == DownloadState.IDLE:
            if self._current_game and self._current_game.name == game.name:
                self._clear()
            return

        if game.download_state == DownloadState.FINISHED:
            self._show_active(game)
            if self._state_label:
                self._state_label.configure(text="Finalizado", text_color=COLORS["success"])
            if self._progress_bar:
                self._progress_bar.set(1.0)
            if self._pct_label:
                self._pct_label.configure(text="100%")
            self.after(3000, self._clear)
            return

        self._show_active(game)

    def _show_active(self, game: Game) -> None:
        if not self._current_game or self._current_game.name != game.name:
            self._clear()
            self._current_game = game

            self.empty_label.pack_forget()

            self._active_frame = ctk.CTkFrame(self.content, fg_color=COLORS["bg_dark"], corner_radius=6)
            self._active_frame.pack(fill="both", expand=True)

            name_lbl = ctk.CTkLabel(
                self._active_frame,
                text=game.name,
                font=FONT_NORMAL,
                text_color=COLORS["text"],
                anchor="w",
            )
            name_lbl.pack(fill="x", padx=12, pady=(8, 4))

            self._progress_bar = ctk.CTkProgressBar(
                self._active_frame,
                progress_color=COLORS["accent"],
                fg_color=COLORS["border"],
            )
            self._progress_bar.pack(fill="x", padx=12, pady=4)
            self._progress_bar.set(0)

            row = ctk.CTkFrame(self._active_frame, fg_color="transparent")
            row.pack(fill="x", padx=12, pady=(0, 8))

            self._pct_label = ctk.CTkLabel(row, text="0%", font=FONT_SMALL, text_color=COLORS["accent"])
            self._pct_label.pack(side="left")

            self._state_label = ctk.CTkLabel(row, text="", font=FONT_SMALL, text_color=COLORS["text_dim"])
            self._state_label.pack(side="left", padx=12)

            self._detail_label = ctk.CTkLabel(row, text="", font=FONT_SMALL, text_color=COLORS["text_dim"])
            self._detail_label.pack(side="right")

        if self._progress_bar:
            self._progress_bar.set(game.download_progress / 100.0)
        if self._pct_label:
            self._pct_label.configure(text=f"{game.download_progress:.0f}%")
        if self._state_label:
            color = COLORS["text_dim"]
            if game.download_state == DownloadState.ERROR:
                color = COLORS["danger"]
            self._state_label.configure(
                text=game.download_error or game.download_state.value,
                text_color=color,
            )
        if self._detail_label:
            parts = [p for p in (game.download_speed, game.download_size) if p]
            self._detail_label.configure(text="  ·  ".join(parts))

    def _clear(self) -> None:
        if self._active_frame:
            self._active_frame.destroy()
            self._active_frame = None
        self._progress_bar = None
        self._pct_label = None
        self._state_label = None
        self._detail_label = None
        self._current_game = None
        self.empty_label.pack(expand=True)
