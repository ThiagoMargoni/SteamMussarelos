from __future__ import annotations

import customtkinter as ctk

from src.models.game import DownloadState, Game
from src.ui.theme import (
    CARD_RADIUS,
    COLORS,
    DOWNLOAD_PANEL_HEIGHT,
    DOWNLOAD_SCROLL_HEIGHT,
    FONT_CAPTION,
    FONT_HEADING,
    FONT_SMALL,
)

class _DownloadRow:
    def __init__(self, master: ctk.CTkFrame, game_name: str) -> None:
        self.game_name = game_name
        self.frame = ctk.CTkFrame(
            master,
            fg_color=COLORS["bg_card"],
            corner_radius=8,
            border_width=1,
            border_color=COLORS["border"],
        )
        self.frame.pack(fill="x", pady=(0, 8))

        top = ctk.CTkFrame(self.frame, fg_color="transparent")
        top.pack(fill="x", padx=16, pady=(12, 6))

        self.name_label = ctk.CTkLabel(
            top,
            text=game_name,
            font=("Segoe UI", 13, "bold"),
            text_color=COLORS["text"],
            anchor="w",
        )
        self.name_label.pack(side="left", fill="x", expand=True)

        self.pct_label = ctk.CTkLabel(
            top,
            text="0%",
            font=("Segoe UI", 13, "bold"),
            text_color=COLORS["accent"],
            width=52,
            anchor="e",
        )
        self.pct_label.pack(side="right")

        self.progress = ctk.CTkProgressBar(
            self.frame,
            height=16,
            corner_radius=8,
            progress_color=COLORS["accent"],
            fg_color=COLORS["border"],
            border_width=0,
        )
        self.progress.pack(fill="x", padx=16, pady=(0, 8))
        self.progress.set(0)

        bottom = ctk.CTkFrame(self.frame, fg_color="transparent")
        bottom.pack(fill="x", padx=16, pady=(0, 12))

        self.state_label = ctk.CTkLabel(
            bottom,
            text="Aguardando...",
            font=FONT_CAPTION,
            text_color=COLORS["text_dim"],
            anchor="w",
        )
        self.state_label.pack(side="left")

        self.detail_label = ctk.CTkLabel(
            bottom,
            text="",
            font=FONT_SMALL,
            text_color=COLORS["text_muted"],
            anchor="e",
        )
        self.detail_label.pack(side="right")

    def update(self, game: Game) -> None:
        progress = max(0.0, min(100.0, game.download_progress))
        self.progress.set(progress / 100.0)
        self.pct_label.configure(text=f"{progress:.0f}%")

        if game.download_state == DownloadState.ERROR:
            self.state_label.configure(text=game.download_error or "Erro", text_color=COLORS["danger"])
            self.progress.configure(progress_color=COLORS["danger"])
        elif game.download_state == DownloadState.FINISHED:
            self.state_label.configure(text="Finalizado", text_color=COLORS["success"])
            self.progress.configure(progress_color=COLORS["success"])
            self.pct_label.configure(text="100%")
            self.progress.set(1.0)
        elif game.download_state == DownloadState.EXTRACTING:
            self.state_label.configure(text="Extraindo arquivos...", text_color=COLORS["warning"])
            self.progress.configure(progress_color=COLORS["warning"])
        else:
            self.state_label.configure(text="Baixando...", text_color=COLORS["accent"])
            self.progress.configure(progress_color=COLORS["accent"])

        parts = [p for p in (game.download_speed, game.download_size) if p]
        self.detail_label.configure(text="  ·  ".join(parts))

    def destroy_row(self) -> None:
        self.frame.destroy()


class DownloadPanel(ctk.CTkFrame):
    def __init__(self, master, **kwargs) -> None:
        super().__init__(
            master,
            fg_color=COLORS["bg_panel"],
            height=DOWNLOAD_PANEL_HEIGHT,
            corner_radius=CARD_RADIUS,
            border_width=1,
            border_color=COLORS["border"],
            **kwargs,
        )
        self.pack_propagate(False)

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=14, pady=(12, 0))

        ctk.CTkLabel(
            header,
            text="Downloads",
            font=FONT_HEADING,
            text_color=COLORS["text"],
            anchor="w",
        ).pack(side="left")

        self.count_label = ctk.CTkLabel(
            header,
            text="",
            font=FONT_SMALL,
            text_color=COLORS["text_muted"],
            anchor="e",
        )
        self.count_label.pack(side="right")

        self.body = ctk.CTkFrame(self, fg_color="transparent")
        self.body.pack(fill="both", expand=True, padx=10, pady=(6, 12))

        self.empty_label = ctk.CTkLabel(
            self.body,
            text="Nenhum download em andamento",
            font=FONT_CAPTION,
            text_color=COLORS["text_muted"],
        )

        self.single_view = ctk.CTkFrame(self.body, fg_color="transparent")
        self.single_inner = ctk.CTkFrame(self.single_view, fg_color="transparent")

        self.multi_view = ctk.CTkScrollableFrame(
            self.body,
            fg_color="transparent",
            height=DOWNLOAD_SCROLL_HEIGHT,
            scrollbar_button_color=COLORS["border"],
            scrollbar_button_hover_color=COLORS["border_light"],
        )

        self._rows: dict[str, _DownloadRow] = {}
        self._game_refs: dict[str, Game] = {}
        self._pending_remove: dict[str, str] = {}
        self._layout_mode: str | None = None

        self._show_empty()

    def update_game(self, game: Game) -> None:
        state = game.download_state

        if state == DownloadState.IDLE:
            if game.name in self._game_refs:
                self._schedule_remove(game.name)
            return

        if game.name in self._pending_remove:
            self.after_cancel(self._pending_remove[game.name])
            del self._pending_remove[game.name]

        prev_count = len(self._game_refs)
        self._game_refs[game.name] = game

        if prev_count != len(self._game_refs) or self._layout_mode != self._mode_for_count(len(self._game_refs)):
            self._rebuild_rows()
        else:
            row = self._rows.get(game.name)
            if row:
                row.update(game)

        if state == DownloadState.FINISHED:
            self._schedule_remove(game.name, delay_ms=4000)
        elif state == DownloadState.ERROR:
            self._schedule_remove(game.name, delay_ms=8000)

    def _mode_for_count(self, count: int) -> str:
        if count == 0:
            return "empty"
        if count == 1:
            return "single"
        return "multi"

    def _show_empty(self) -> None:
        self._layout_mode = "empty"
        self.single_inner.pack_forget()
        self.single_view.pack_forget()
        self.multi_view.pack_forget()
        self.empty_label.pack(expand=True)

    def _show_single(self) -> None:
        self._layout_mode = "single"
        self.empty_label.pack_forget()
        self.multi_view.pack_forget()
        self.single_inner.place_forget()
        self.single_view.pack(fill="both", expand=True)
        self.single_inner.pack(fill="x", expand=True)

    def _show_multi(self) -> None:
        self._layout_mode = "multi"
        self.empty_label.pack_forget()
        self.single_inner.pack_forget()
        self.single_view.pack_forget()
        self.multi_view.pack(fill="both", expand=True)

    def _rebuild_rows(self) -> None:
        for row in self._rows.values():
            row.destroy_row()
        self._rows.clear()

        count = len(self._game_refs)
        mode = self._mode_for_count(count)

        if mode == "empty":
            self._show_empty()
            self._update_count()
            return

        if mode == "single":
            self._show_single()
            parent = self.single_inner
        else:
            self._show_multi()
            parent = self.multi_view

        for name, game in self._game_refs.items():
            row = _DownloadRow(parent, name)
            row.update(game)
            self._rows[name] = row

        self._update_count()

    def _schedule_remove(self, name: str, delay_ms: int = 3000) -> None:
        if name in self._pending_remove:
            self.after_cancel(self._pending_remove[name])

        def _remove() -> None:
            self._pending_remove.pop(name, None)
            self._game_refs.pop(name, None)
            self._rebuild_rows()

        self._pending_remove[name] = self.after(delay_ms, _remove)

    def _update_count(self) -> None:
        n = len(self._game_refs)
        self.count_label.configure(text=f"{n} ativo{'s' if n != 1 else ''}" if n else "")
