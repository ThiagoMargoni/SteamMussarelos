from __future__ import annotations

from typing import Callable

import customtkinter as ctk

from src.models.game import Game
from src.ui.theme import CARD_RADIUS, COLORS

class PlaceScrollFrame(ctk.CTkScrollableFrame):
    def __init__(
        self,
        master,
        fg_color=COLORS["bg_panel"],
        corner_radius: int = CARD_RADIUS,
        border_width: int = 1,
        border_color=COLORS["border"],
        scrollbar_button_color=COLORS["border"],
        scrollbar_button_hover_color=COLORS["border_light"],
        **kwargs,
    ) -> None:
        super().__init__(
            master,
            fg_color=fg_color,
            corner_radius=corner_radius,
            border_width=border_width,
            border_color=border_color,
            scrollbar_button_color=scrollbar_button_color,
            scrollbar_button_hover_color=scrollbar_button_hover_color,
            **kwargs,
        )
        self.grid_columnconfigure(0, weight=1)
        self.inner = self
        self._items: list[Game] = []
        self._factory: Callable | None = None
        self._cards: list = []

    def set_games(self, games: list[Game], factory: Callable) -> None:
        self.clear_cards()
        self._items = list(games)
        self._factory = factory
        if not games or not factory:
            return
        for i, game in enumerate(games):
            card = factory(self, game)
            card.grid(row=i, column=0, sticky="ew", padx=10, pady=6)
            self._cards.append(card)

    def clear_cards(self) -> None:
        for card in self._cards:
            try:
                card.destroy()
            except Exception:
                pass
        self._cards.clear()
        self._items = []
        self._factory = None

    def card_for(self, name: str):
        for card in self._cards:
            try:
                if card.winfo_exists() and card.game.name == name:
                    return card
            except Exception:
                continue
        return None

    def iter_cards(self):
        return [c for c in self._cards if c.winfo_exists()]

    def refresh(self) -> None:
        pass

    def scroll_to_top(self) -> None:
        try:
            self._parent_canvas.yview_moveto(0)
        except Exception:
            pass
