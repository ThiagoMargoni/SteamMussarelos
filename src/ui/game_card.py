from __future__ import annotations

import io
import threading
from pathlib import Path
from typing import Callable, Optional

import customtkinter as ctk
import requests
from PIL import Image

from src.models.game import DownloadState, Game, GameStatus
from src.ui.theme import COLORS, FONT_BUTTON, FONT_NORMAL, FONT_SMALL

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
        super().__init__(master, fg_color=COLORS["bg_card"], corner_radius=8, **kwargs)
        self.game = game
        self._on_install = on_install
        self._on_update = on_update
        self._on_play = on_play
        self._on_stop = on_stop
        self._on_uninstall = on_uninstall
        self._icon_image: Optional[ctk.CTkImage] = None

        self.grid_columnconfigure(1, weight=1)

        self.icon_label = ctk.CTkLabel(self, text="", width=80, height=80)
        self.icon_label.grid(row=0, column=0, rowspan=3, padx=12, pady=12)

        self.name_label = ctk.CTkLabel(
            self,
            text=game.name,
            font=FONT_BUTTON,
            text_color=COLORS["text"],
            anchor="w",
        )
        self.name_label.grid(row=0, column=1, sticky="w", padx=(0, 12), pady=(12, 0))

        self.version_label = ctk.CTkLabel(
            self,
            text="",
            font=FONT_SMALL,
            text_color=COLORS["text_dim"],
            anchor="w",
        )
        self.version_label.grid(row=1, column=1, sticky="w", padx=(0, 12))

        self.status_label = ctk.CTkLabel(
            self,
            text="",
            font=FONT_SMALL,
            anchor="w",
        )
        self.status_label.grid(row=2, column=1, sticky="w", padx=(0, 12), pady=(0, 8))

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=0, column=2, rowspan=3, padx=12, pady=12)

        self.action_btn = ctk.CTkButton(
            btn_frame,
            text="Instalar",
            width=110,
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            text_color=COLORS["bg_medium"],
            font=FONT_BUTTON,
            command=self._on_action,
        )
        self.action_btn.pack(pady=2)

        self.secondary_btn = ctk.CTkButton(
            btn_frame,
            text="Atualizar",
            width=110,
            fg_color=COLORS["bg_dark"],
            hover_color=COLORS["bg_card_hover"],
            font=FONT_NORMAL,
            command=lambda: self._on_update(self.game),
        )
        self.secondary_btn.pack(pady=2)

        self.uninstall_btn = ctk.CTkButton(
            btn_frame,
            text="Desinstalar",
            width=110,
            fg_color=COLORS["bg_dark"],
            hover_color=COLORS["danger"],
            text_color=COLORS["text_dim"],
            font=FONT_NORMAL,
            command=lambda: self._on_uninstall(self.game),
        )
        self.uninstall_btn.pack(pady=2)

        self._load_icon()
        self.refresh()

    def _load_icon(self) -> None:
        icon = self.game.icon
        if not icon:
            self.icon_label.configure(text="🎮", font=("Segoe UI", 36))
            return

        def _fetch() -> None:
            try:
                if icon.startswith("http"):
                    resp = requests.get(icon, timeout=10)
                    resp.raise_for_status()
                    img = Image.open(io.BytesIO(resp.content))
                else:
                    path = Path(icon)
                    if not path.is_absolute():
                        path = Path(__file__).resolve().parents[2] / icon
                    if path.exists():
                        img = Image.open(path)
                    else:
                        return
                img = img.resize((80, 80), Image.Resampling.LANCZOS)
                self._icon_image = ctk.CTkImage(light_image=img, dark_image=img, size=(80, 80))
                self.after(0, lambda: self.icon_label.configure(image=self._icon_image, text=""))
            except Exception:
                self.after(0, lambda: self.icon_label.configure(text="🎮", font=("Segoe UI", 36)))

        threading.Thread(target=_fetch, daemon=True).start()

    def _on_action(self) -> None:
        if self.game.status == GameStatus.RUNNING:
            self._on_stop(self.game)
        elif self.game.status in (GameStatus.INSTALLED, GameStatus.UPDATE_AVAILABLE):
            self._on_play(self.game)
        else:
            self._on_install(self.game)

    def refresh(self) -> None:
        g = self.game
        installed = g.installed_version or "—"
        remote = g.version
        self.version_label.configure(text=f"Instalado: {installed}  |  Remoto: {remote}")

        status_colors = {
            GameStatus.NOT_INSTALLED: COLORS["text_dim"],
            GameStatus.INSTALLED: COLORS["success"],
            GameStatus.UPDATE_AVAILABLE: COLORS["warning"],
            GameStatus.RUNNING: COLORS["running"],
        }
        self.status_label.configure(
            text=g.status.value,
            text_color=status_colors.get(g.status, COLORS["text"]),
        )

        if g.status == GameStatus.RUNNING:
            self.configure(fg_color="#1e4d2b")
            self.action_btn.configure(text="Encerrar", fg_color=COLORS["danger"])
        elif g.status == GameStatus.INSTALLED:
            self.configure(fg_color=COLORS["bg_card"])
            self.action_btn.configure(text="Iniciar", fg_color=COLORS["success"])
        elif g.status == GameStatus.UPDATE_AVAILABLE:
            self.configure(fg_color=COLORS["bg_card"])
            self.action_btn.configure(text="Iniciar", fg_color=COLORS["success"])
        else:
            self.configure(fg_color=COLORS["bg_card"])
            self.action_btn.configure(text="Instalar", fg_color=COLORS["accent"])

        busy = g.download_state in (DownloadState.DOWNLOADING, DownloadState.EXTRACTING)
        if busy:
            self.action_btn.configure(state="disabled")
        else:
            self.action_btn.configure(state="normal")

        if g.status == GameStatus.UPDATE_AVAILABLE:
            self.secondary_btn.configure(state="normal")
        else:
            self.secondary_btn.configure(state="disabled")

        installed = g.status in (
            GameStatus.INSTALLED,
            GameStatus.UPDATE_AVAILABLE,
            GameStatus.RUNNING,
        )
        if installed and not busy and g.status != GameStatus.RUNNING:
            self.uninstall_btn.configure(state="normal")
        else:
            self.uninstall_btn.configure(state="disabled")
