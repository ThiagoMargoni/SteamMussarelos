from __future__ import annotations

import threading
from tkinter import filedialog, messagebox

import customtkinter as ctk

from src.core.folder_setup import apply_games_folder
from src.core.settings import Settings
from src.ui.theme import (
    COLORS,
    FONT_BODY,
    FONT_BUTTON,
    FONT_CAPTION,
    FONT_DISPLAY,
    FONT_HEADING,
)

class SetupWizard(ctk.CTkToplevel):
    def __init__(self, master, settings: Settings, on_complete) -> None:
        super().__init__(master)
        self.settings = settings
        self.on_complete = on_complete

        self.title("Configuração Inicial")
        self.geometry("600x380")
        self.resizable(False, False)
        self.configure(fg_color=COLORS["bg_dark"])
        self.transient(master)
        self.grab_set()

        ctk.CTkLabel(
            self,
            text="Bem-vindo",
            font=FONT_DISPLAY,
            text_color=COLORS["accent"],
        ).pack(pady=(28, 4))

        ctk.CTkLabel(
            self,
            text="Steam dos Mussarelos",
            font=FONT_HEADING,
            text_color=COLORS["text"],
        ).pack()

        ctk.CTkLabel(
            self,
            text="Escolha onde os jogos serão instalados no seu computador.",
            font=FONT_BODY,
            text_color=COLORS["text_dim"],
        ).pack(pady=(12, 20))

        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=28)

        self.folder_entry = ctk.CTkEntry(
            row,
            placeholder_text="C:\\Jogos",
            height=40,
            font=FONT_BODY,
            corner_radius=8,
        )
        self.folder_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))

        ctk.CTkButton(
            row,
            text="Procurar",
            width=100,
            height=40,
            corner_radius=8,
            fg_color=COLORS["bg_card"],
            hover_color=COLORS["bg_card_hover"],
            font=FONT_BUTTON,
            command=self._browse,
        ).pack(side="right")

        self.status_label = ctk.CTkLabel(
            self,
            text="",
            font=FONT_CAPTION,
            text_color=COLORS["text_muted"],
            wraplength=520,
            justify="left",
        )
        self.status_label.pack(pady=20, padx=28, anchor="w")

        self.confirm_btn = ctk.CTkButton(
            self,
            text="Confirmar e continuar",
            width=240,
            height=42,
            corner_radius=8,
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            text_color=COLORS["bg_medium"],
            font=FONT_BUTTON,
            command=self._confirm,
        )
        self.confirm_btn.pack(pady=8)

        self.protocol("WM_DELETE_WINDOW", lambda: None)

    def _browse(self) -> None:
        folder = filedialog.askdirectory(title="Selecione a pasta dos jogos")
        if folder:
            self.folder_entry.delete(0, "end")
            self.folder_entry.insert(0, folder)

    def _confirm(self) -> None:
        folder = self.folder_entry.get().strip()
        if not folder:
            messagebox.showwarning("Atenção", "Selecione uma pasta válida.")
            return

        self.confirm_btn.configure(state="disabled")
        self.status_label.configure(text="Configurando pasta e verificando antivírus...")

        def _setup() -> None:
            _, status = apply_games_folder(self.settings, folder)
            self.after(0, lambda: self._finish(status))

        threading.Thread(target=_setup, daemon=True).start()

    def _finish(self, status: str) -> None:
        self.status_label.configure(text=status)
        self.after(1400, self._close)

    def _close(self) -> None:
        self.grab_release()
        self.destroy()
        self.on_complete()
