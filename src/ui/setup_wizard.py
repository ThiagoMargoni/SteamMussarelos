from __future__ import annotations

import threading
from tkinter import filedialog, messagebox

import customtkinter as ctk

from src.core.folder_setup import apply_games_folder
from src.core.settings import Settings
from src.ui.theme import COLORS, FONT_BUTTON, FONT_NORMAL, FONT_TITLE

class SetupWizard(ctk.CTkToplevel):
    def __init__(self, master, settings: Settings, on_complete) -> None:
        super().__init__(master)
        self.settings = settings
        self.on_complete = on_complete
        self.selected_folder: str | None = None

        self.title("Configuração Inicial — Steam dos Mussarelos")
        self.geometry("560x320")
        self.resizable(False, False)
        self.configure(fg_color=COLORS["bg_dark"])
        self.transient(master)
        self.grab_set()

        ctk.CTkLabel(
            self,
            text="Bem-vindo ao Steam dos Mussarelos",
            font=FONT_TITLE,
            text_color=COLORS["text"],
        ).pack(pady=(24, 8))

        ctk.CTkLabel(
            self,
            text="Escolha a pasta onde os jogos serão instalados.",
            font=FONT_NORMAL,
            text_color=COLORS["text_dim"],
        ).pack(pady=(0, 16))

        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=24)

        self.folder_entry = ctk.CTkEntry(row, placeholder_text="C:\\Jogos", width=360)
        self.folder_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))

        ctk.CTkButton(
            row,
            text="Procurar",
            width=90,
            fg_color=COLORS["bg_card"],
            hover_color=COLORS["bg_card_hover"],
            command=self._browse,
        ).pack(side="right")

        self.status_label = ctk.CTkLabel(
            self,
            text="",
            font=FONT_NORMAL,
            text_color=COLORS["text_dim"],
            wraplength=500,
        )
        self.status_label.pack(pady=16)

        self.confirm_btn = ctk.CTkButton(
            self,
            text="Confirmar",
            width=200,
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
        self.status_label.configure(text="Configurando...")

        def _setup() -> None:
            ok, status = apply_games_folder(self.settings, folder)
            self.after(0, lambda: self._finish(status))

        threading.Thread(target=_setup, daemon=True).start()

    def _finish(self, status: str) -> None:
        self.status_label.configure(text=status)
        self.after(1200, self._close)

    def _close(self) -> None:
        self.grab_release()
        self.destroy()
        self.on_complete()
