from __future__ import annotations

import tkinter as tk
from typing import Callable, Optional

import customtkinter as ctk
from PIL import Image, ImageTk

from src.models.game import DownloadState, Game, GameStatus
from src.ui.action_icons import get_uninstall_icon
from src.ui.icon_loader import apply_icon_to_label, get_cached_icon, icon_cache_key, load_game_icon
from src.ui.theme import (
    CARD_HEIGHT,
    CARD_RADIUS,
    COLORS,
    FONT_CAPTION,
    FONT_HEADING,
    FONT_SMALL,
    ICON_SIZE,
    PRIMARY_BTN_HEIGHT,
    PRIMARY_BTN_WIDTH,
    UNINSTALL_BTN,
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
        uninstall_image: Optional[ctk.CTkImage] = None,
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
        self._icon_ref: Optional[ImageTk.PhotoImage] = None
        self._icon_token = 0
        self._frame_fg = COLORS["bg_card"]
        self._frame_border = COLORS["border"]
        self._last_signature: tuple | None = None
        self._icon_px = max(1, int(self._apply_widget_scaling(ICON_SIZE)))

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        pad_y = max(0, (CARD_HEIGHT - ICON_SIZE) // 2)
        self.icon_frame = tk.Frame(
            self,
            width=self._icon_px,
            height=self._icon_px,
            bg=COLORS["bg_card"],
            highlightthickness=0,
            bd=0,
        )
        self.icon_frame.grid(row=0, column=0, padx=(16, 14), pady=pad_y, sticky="w")
        self.icon_frame.grid_propagate(False)
        self.icon_frame.pack_propagate(False)

        self.icon_label = tk.Label(
            self.icon_frame,
            bg=COLORS["bg_card"],
            bd=0,
            highlightthickness=0,
            text="",
        )
        self.icon_label.place(x=0, y=0, relwidth=1, relheight=1)

        info = ctk.CTkFrame(self, fg_color="transparent")
        info.grid(row=0, column=1, sticky="w")

        self.name_label = ctk.CTkLabel(
            info,
            text=game.name,
            font=FONT_HEADING,
            text_color=COLORS["text"],
            anchor="w",
        )
        self.name_label.pack(anchor="w")

        meta = ctk.CTkFrame(info, fg_color="transparent")
        meta.pack(anchor="w", pady=(6, 0))

        self.status_badge = ctk.CTkLabel(
            meta,
            text="",
            font=FONT_SMALL,
            corner_radius=6,
            fg_color=COLORS["bg_panel"],
            text_color=COLORS["text_dim"],
            padx=8,
            pady=2,
        )
        self.status_badge.pack(side="left", padx=(0, 10))

        self.version_label = ctk.CTkLabel(
            meta,
            text="",
            font=FONT_CAPTION,
            text_color=COLORS["text_dim"],
            anchor="w",
        )
        self.version_label.pack(side="left")

        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.grid(row=0, column=2, padx=(8, 16), sticky="e")

        self.action_btn = ctk.CTkButton(
            actions,
            text="Instalar",
            width=PRIMARY_BTN_WIDTH,
            height=PRIMARY_BTN_HEIGHT,
            corner_radius=8,
            font=FONT_SMALL,
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            text_color=COLORS["bg_medium"],
            command=self._on_action,
        )
        self.action_btn.pack(side="left", padx=(0, 8))

        self._uninstall_img = uninstall_image or get_uninstall_icon()
        self.uninstall_btn = ctk.CTkButton(
            actions,
            text="",
            image=self._uninstall_img,
            width=UNINSTALL_BTN,
            height=UNINSTALL_BTN,
            corner_radius=8,
            fg_color=COLORS["danger"],
            hover_color=COLORS["danger_hover"],
            border_width=0,
            command=lambda: on_uninstall(self.game),
        )
        self.uninstall_btn.pack(side="left")

        self._load_icon()
        self.refresh(force=True)

    def set_uninstall_image(self, image: ctk.CTkImage) -> None:
        self._uninstall_img = image
        self.uninstall_btn.configure(image=image)

    def bind_game(self, game: Game) -> None:
        if self.game is game:
            self.refresh()
            return
        self.game = game
        self.name_label.configure(text=game.name)
        _, _, _, _, on_uninstall = self._callbacks
        self.uninstall_btn.configure(command=lambda: on_uninstall(self.game))
        self._icon_ref = None
        self._last_signature = None
        self._load_icon()
        self.refresh(force=True)

    def _reapply_icon(self) -> None:
        if not self.winfo_exists():
            return
        img = self._icon_ref or get_cached_icon(self.game.icon, self._icon_px)
        if img is not None:
            self._icon_ref = apply_icon_to_label(self.icon_label, img)
            self._resize_icon_frame(self._icon_ref)

    def _resize_icon_frame(self, photo: Optional[ImageTk.PhotoImage]) -> None:
        if photo is None:
            self.icon_frame.configure(width=self._icon_px, height=self._icon_px)
            pad_y = max(0, (int(self._apply_widget_scaling(CARD_HEIGHT)) - self._icon_px) // 2)
            self.icon_frame.grid_configure(pady=pad_y)
            return
        self.icon_frame.configure(width=photo.width(), height=photo.height())
        card_h = int(self._apply_widget_scaling(CARD_HEIGHT))
        pad_y = max(0, (card_h - photo.height()) // 2)
        self.icon_frame.grid_configure(pady=pad_y)

    def _load_icon(self) -> None:
        self._icon_token += 1
        token = self._icon_token
        icon_name = self.game.icon
        size = self._icon_px
        cache_key = icon_cache_key(icon_name, size)

        def _on_ready(img: Image.Image | ImageTk.PhotoImage | None) -> None:
            def _apply() -> None:
                if not self.winfo_exists() or token != self._icon_token:
                    return
                if isinstance(img, Image.Image):
                    self._icon_ref = apply_icon_to_label(
                        self.icon_label, img, placeholder="?", cache_key=cache_key
                    )
                else:
                    self._icon_ref = apply_icon_to_label(self.icon_label, img, placeholder="?")
                self._resize_icon_frame(self._icon_ref)

            self.after(0, _apply)

        cached = get_cached_icon(icon_name, size)
        if cached is not None:
            _on_ready(cached)
            return
        load_game_icon(icon_name, _on_ready, size=size)

    def _on_action(self) -> None:
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
            round(g.download_progress),
        )

    def _set_frame_style(self, fg: str, border: str) -> None:
        if fg == self._frame_fg and border == self._frame_border:
            return
        self._frame_fg = fg
        self._frame_border = border
        self.configure(fg_color=fg, border_color=border)
        try:
            self.icon_frame.configure(bg=fg)
            self.icon_label.configure(bg=fg)
        except Exception:
            pass

    def refresh(self, force: bool = False) -> None:
        sig = self._signature()
        if not force and sig == self._last_signature:
            return
        self._last_signature = sig

        g = self.game
        if g.installed_version:
            self.version_label.configure(text=f"v{g.installed_version}")
        else:
            self.version_label.configure(text="")

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
            self._set_frame_style(COLORS["bg_card_running"], COLORS["success"])
            self.action_btn.configure(text="Encerrar", fg_color=COLORS["danger"], hover_color=COLORS["danger_hover"])
        elif g.status == GameStatus.UPDATE_AVAILABLE:
            self._set_frame_style(COLORS["bg_card"], COLORS["border"])
            self.action_btn.configure(text="Atualizar", fg_color=COLORS["warning"], hover_color="#f0c93d", text_color=COLORS["bg_medium"])
        elif g.status == GameStatus.INSTALLED:
            self._set_frame_style(COLORS["bg_card"], COLORS["border"])
            self.action_btn.configure(text="Iniciar", fg_color=COLORS["success"], hover_color=COLORS["success_hover"], text_color=COLORS["bg_medium"])
        else:
            self._set_frame_style(COLORS["bg_card"], COLORS["border"])
            self.action_btn.configure(text="Instalar", fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"], text_color=COLORS["bg_medium"])

        self.action_btn.configure(state="disabled" if busy else "normal")

        can_uninstall = g.status in (GameStatus.INSTALLED, GameStatus.UPDATE_AVAILABLE) and not busy
        if can_uninstall:
            self.uninstall_btn.configure(
                state="normal",
                fg_color=COLORS["danger"],
                hover_color=COLORS["danger_hover"],
            )
        else:
            self.uninstall_btn.configure(
                state="disabled",
                fg_color=COLORS["border"],
                hover_color=COLORS["border"],
            )
