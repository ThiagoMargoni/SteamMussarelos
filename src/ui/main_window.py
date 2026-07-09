from __future__ import annotations

import threading
from tkinter import messagebox

import customtkinter as ctk

from src.core.catalog import CatalogService
from src.core.installer import Installer
from src.core.process_manager import ProcessManager
from src.core.settings import LAUNCHER_VERSION, Settings
from src.models.game import DownloadState, Game, GameStatus
from src.ui.download_panel import DownloadPanel
from src.ui.game_card import GameCard
from src.ui.setup_wizard import SetupWizard
from src.ui.theme import COLORS, FONT_BUTTON, FONT_NORMAL, FONT_TITLE

class MainWindow(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()

        self.settings = Settings()
        self.catalog_service = CatalogService(self.settings)
        self.installer = Installer(self.settings)
        self.process_manager = ProcessManager()

        self._cards: dict[str, GameCard] = {}
        self._refresh_job: str | None = None

        self.title("Steam dos Mussarelos")
        self.geometry("960x700")
        self.minsize(800, 600)
        self.configure(fg_color=COLORS["bg_dark"])

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")

        self._build_header()
        self._build_library()
        self._build_downloads()

        if not self.settings.first_run_complete or not self.settings.games_folder:
            self.after(200, self._show_setup)
        else:
            self.after(200, self._initial_load)

        self._start_process_monitor()

    def _build_header(self) -> None:
        header = ctk.CTkFrame(self, fg_color=COLORS["bg_medium"], height=56, corner_radius=0)
        header.pack(fill="x")
        header.pack_propagate(False)

        ctk.CTkLabel(
            header,
            text="STEAM DOS MUSSARELOS",
            font=FONT_TITLE,
            text_color=COLORS["accent"],
        ).pack(side="left", padx=20, pady=12)

        self.reload_btn = ctk.CTkButton(
            header,
            text="↻ Atualizar",
            width=120,
            fg_color=COLORS["bg_card"],
            hover_color=COLORS["bg_card_hover"],
            font=FONT_BUTTON,
            command=self._reload_catalog,
        )
        self.reload_btn.pack(side="right", padx=8, pady=12)

        self.folder_label = ctk.CTkLabel(
            header,
            text="",
            font=FONT_NORMAL,
            text_color=COLORS["text_dim"],
        )
        self.folder_label.pack(side="right", padx=12)

    def _build_library(self) -> None:
        self.library_frame = ctk.CTkScrollableFrame(
            self,
            fg_color=COLORS["bg_dark"],
            label_text="Biblioteca",
            label_font=FONT_BUTTON,
            label_text_color=COLORS["text_dim"],
        )
        self.library_frame.pack(fill="both", expand=True, padx=12, pady=(8, 0))
        self.library_frame.grid_columnconfigure(0, weight=1)

        self.loading_label = ctk.CTkLabel(
            self.library_frame,
            text="Carregando catálogo...",
            font=FONT_NORMAL,
            text_color=COLORS["text_dim"],
        )
        self.loading_label.grid(row=0, column=0, pady=40)

    def _build_downloads(self) -> None:
        self.download_panel = DownloadPanel(self)
        self.download_panel.pack(fill="x", side="bottom")

    def _show_setup(self) -> None:
        SetupWizard(self, self.settings, on_complete=self._initial_load)

    def _initial_load(self) -> None:
        folder = self.settings.games_folder or "—"
        self.folder_label.configure(text=f"📁 {folder}")
        self._reload_catalog()

    def _reload_catalog(self) -> None:
        self.reload_btn.configure(state="disabled", text="Atualizando...")

        def _fetch() -> None:
            try:
                catalog = self.catalog_service.fetch()
                self.after(0, lambda: self._render_catalog(catalog.games))
                self.after(0, self._check_launcher_update)
            except Exception as exc:
                self.after(
                    0,
                    lambda: messagebox.showerror("Erro", f"Falha ao carregar catálogo:\n{exc}"),
                )
            finally:
                self.after(0, lambda: self.reload_btn.configure(state="normal", text="↻ Atualizar"))

        threading.Thread(target=_fetch, daemon=True).start()

    def _render_catalog(self, games: list[Game]) -> None:
        self.loading_label.grid_forget()

        for card in self._cards.values():
            card.destroy()
        self._cards.clear()

        self.process_manager.refresh_all(games)

        for i, game in enumerate(games):
            card = GameCard(
                self.library_frame,
                game,
                on_install=self._on_install,
                on_update=self._on_update,
                on_play=self._on_play,
                on_stop=self._on_stop,
            )
            card.grid(row=i, column=0, sticky="ew", pady=6)
            self._cards[game.name] = card

    def _check_launcher_update(self) -> None:
        if not self.catalog_service.launcher_update_available():
            return

        catalog = self.catalog_service.catalog
        if not catalog:
            return

        remote = catalog.launcher.latest_version
        local = self.settings.launcher_version

        if messagebox.askyesno(
            "Atualização do Launcher",
            f"Há uma nova versão do launcher disponível.\n\n"
            f"Instalada: {local}\n"
            f"Disponível: {remote}\n\n"
            f"Deseja baixar a atualização?",
        ):
            if catalog.launcher.download:
                import webbrowser

                webbrowser.open(catalog.launcher.download)
            else:
                messagebox.showinfo(
                    "Atualização",
                    "Link de download não configurado no catálogo remoto.",
                )

    def _on_progress(self, game: Game) -> None:
        def _ui() -> None:
            card = self._cards.get(game.name)
            if card:
                card.refresh()
            self.download_panel.update_game(game)
            if game.download_state == DownloadState.FINISHED:
                game.download_state = DownloadState.IDLE
                if card:
                    card.refresh()

        self.after(0, _ui)

    def _on_install(self, game: Game) -> None:
        self.installer.install(game, on_progress=self._on_progress)

    def _on_update(self, game: Game) -> None:
        if game.status == GameStatus.RUNNING:
            self.process_manager.stop(game)
        self.installer.install(game, on_progress=self._on_progress, is_update=True)

    def _on_play(self, game: Game) -> None:
        ok, msg = self.process_manager.start(game)
        if not ok:
            messagebox.showwarning("Aviso", msg)
        game.update_status(is_running=True)
        card = self._cards.get(game.name)
        if card:
            card.refresh()

    def _on_stop(self, game: Game) -> None:
        self.process_manager.stop(game)
        game.update_status(is_running=False)
        card = self._cards.get(game.name)
        if card:
            card.refresh()

    def _start_process_monitor(self) -> None:
        def _tick() -> None:
            if self.catalog_service.catalog:
                changed = False
                for game in self.catalog_service.catalog.games:
                    was_running = game.status == GameStatus.RUNNING
                    self.process_manager.refresh_all([game])
                    if was_running != (game.status == GameStatus.RUNNING):
                        changed = True
                    card = self._cards.get(game.name)
                    if card:
                        card.refresh()
            self._refresh_job = self.after(2000, _tick)

        self._refresh_job = self.after(2000, _tick)

    def on_closing(self) -> None:
        if self._refresh_job:
            self.after_cancel(self._refresh_job)
        self.destroy()
