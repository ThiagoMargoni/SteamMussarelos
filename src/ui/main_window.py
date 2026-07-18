from __future__ import annotations

import threading
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

from src.core.catalog import CatalogService
from src.core.folder_setup import apply_games_folder
from src.core.install_state import sync_game_with_disk
from src.core.installer import Installer
from src.core.process_manager import ProcessManager
from src.core.settings import LAUNCHER_VERSION, Settings
from src.core.steam_launch import ensure_steam_running
from src.core.updater import apply_launcher_update
from src.models.game import DownloadState, Game, GameStatus
from src.ui.download_panel import DownloadPanel
from src.ui.game_card import GameCard
from src.ui.setup_wizard import SetupWizard
from src.ui.theme import (
    CARD_RADIUS,
    COLORS,
    FONT_BODY,
    FONT_BUTTON,
    FONT_CAPTION,
    FONT_DISPLAY,
    FONT_HEADING,
    HEADER_HEIGHT,
)
from src.utils.paths import resolve_resource

class MainWindow(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()

        self.settings = Settings()
        self.catalog_service = CatalogService(self.settings)
        self.installer = Installer(self.settings)
        self.process_manager = ProcessManager()

        self._cards: dict[str, GameCard] = {}
        self._games: list[Game] = []
        self._search_query = ""
        self._search_job: str | None = None
        self._refresh_job: str | None = None
        self._disk_sync_counter = 0
        self._update_prompted = False
        self._updating_launcher = False
        self._focus_job: str | None = None
        self._scroll_job: str | None = None
        self._scrolling = False

        self.title("Steam dos Mussarelos")
        self.geometry("1024x760")
        self.minsize(900, 640)
        self.configure(fg_color=COLORS["bg_dark"])
        self._set_window_icon()

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")

        self._build_header()
        self._build_library()
        self._build_downloads()

        self.bind("<FocusIn>", self._on_window_focus, add="+")

        if not self.settings.first_run_complete or not self.settings.games_folder:
            self.after(200, self._show_setup)
        else:
            self.after(200, self._initial_load)

        self.after(400, self._ensure_steam)
        self._start_process_monitor()

    def _set_window_icon(self) -> None:
        icon = resolve_resource("assets", "app.ico")
        if not icon:
            return
        path = str(icon.resolve())
        try:
            self.iconbitmap(path)
            self.wm_iconbitmap(path)
        except Exception:
            try:
                self.iconbitmap(default=path)
            except Exception:
                pass

    def _on_window_focus(self, _event=None) -> None:
        if self._scrolling:
            return
        if self._focus_job:
            try:
                self.after_cancel(self._focus_job)
            except Exception:
                pass
        self._focus_job = self.after(150, self._reapply_all_icons)

    def _reapply_all_icons(self) -> None:
        if self._scrolling:
            return
        for card in self._cards.values():
            try:
                if card.winfo_exists() and card.winfo_ismapped():
                    card._reapply_icon()
            except Exception:
                continue

    def _on_scroll_activity(self, _event=None) -> None:
        self._scrolling = True
        if self._scroll_job:
            try:
                self.after_cancel(self._scroll_job)
            except Exception:
                pass
        self._scroll_job = self.after(120, self._on_scroll_settled)

    def _on_scroll_settled(self) -> None:
        self._scrolling = False
        self._reapply_all_icons()

    def _bind_scroll_events(self) -> None:
        try:
            canvas = self.library_frame._parent_canvas
            scrollbar = self.library_frame._scrollbar
        except Exception:
            return

        for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>", "<B1-Motion>", "<ButtonPress-1>"):
            canvas.bind(seq, self._on_scroll_activity, add="+")
            try:
                scrollbar.bind(seq, self._on_scroll_activity, add="+")
            except Exception:
                pass
        canvas.bind("<ButtonRelease-1>", self._on_scroll_activity, add="+")
        try:
            scrollbar.bind("<ButtonRelease-1>", self._on_scroll_activity, add="+")
            scrollbar.bind("<B1-Motion>", self._on_scroll_activity, add="+")
        except Exception:
            pass

    def _ensure_steam(self) -> None:
        def _run() -> None:
            ok, msg = ensure_steam_running()
            if not ok:
                self.after(
                    0,
                    lambda: messagebox.showwarning(
                        "Steam",
                        f"{msg}\n\nAlguns jogos podem precisar da Steam aberta.",
                    ),
                )

        threading.Thread(target=_run, daemon=True).start()

    def _build_header(self) -> None:
        header = ctk.CTkFrame(
            self,
            fg_color=COLORS["bg_medium"],
            height=HEADER_HEIGHT,
            corner_radius=0,
            border_width=0,
        )
        header.pack(fill="x")
        header.pack_propagate(False)

        left = ctk.CTkFrame(header, fg_color="transparent")
        left.pack(side="left", fill="y", padx=20)

        ctk.CTkLabel(
            left,
            text="STEAM DOS MUSSARELOS",
            font=FONT_DISPLAY,
            text_color=COLORS["accent"],
        ).pack(anchor="w", pady=(10, 0))

        ctk.CTkLabel(
            left,
            text="Biblioteca de jogos",
            font=FONT_CAPTION,
            text_color=COLORS["text_muted"],
        ).pack(anchor="w")

        right = ctk.CTkFrame(header, fg_color="transparent")
        right.pack(side="right", fill="y", padx=16)

        self.folder_btn = ctk.CTkButton(
            right,
            text="Pasta dos jogos",
            font=FONT_CAPTION,
            fg_color=COLORS["bg_panel"],
            hover_color=COLORS["bg_card_hover"],
            text_color=COLORS["text_dim"],
            anchor="center",
            height=36,
            width=300,
            corner_radius=8,
            command=self._change_games_folder,
        )
        self.folder_btn.pack(side="right", padx=(8, 0), pady=14)

        self.reload_btn = ctk.CTkButton(
            right,
            text="Atualizar",
            width=120,
            height=36,
            corner_radius=8,
            fg_color=COLORS["bg_card"],
            hover_color=COLORS["bg_card_hover"],
            font=FONT_BUTTON,
            command=self._reload_catalog,
        )
        self.reload_btn.pack(side="right", pady=14)

    def _build_library(self) -> None:
        wrapper = ctk.CTkFrame(self, fg_color="transparent")
        wrapper.pack(fill="both", expand=True, padx=16, pady=(12, 0))
        self._library_wrapper = wrapper

        title_row = ctk.CTkFrame(wrapper, fg_color="transparent")
        title_row.pack(fill="x", pady=(0, 8))

        ctk.CTkLabel(
            title_row,
            text="Biblioteca",
            font=FONT_HEADING,
            text_color=COLORS["text"],
            anchor="w",
        ).pack(side="left")

        self.search_entry = ctk.CTkEntry(
            title_row,
            placeholder_text="Pesquisar jogos...",
            height=34,
            width=260,
            corner_radius=8,
            border_width=1,
            border_color=COLORS["border"],
            fg_color=COLORS["bg_panel"],
            text_color=COLORS["text"],
            placeholder_text_color=COLORS["text_muted"],
            font=FONT_BODY,
        )
        self.search_entry.pack(side="right")
        self.search_entry.bind("<KeyRelease>", self._on_search_changed)
        self.search_entry.bind("<Return>", self._on_search_changed)

        self.library_frame = ctk.CTkScrollableFrame(
            wrapper,
            fg_color=COLORS["bg_panel"],
            corner_radius=CARD_RADIUS,
            border_width=1,
            border_color=COLORS["border"],
            scrollbar_button_color=COLORS["border"],
            scrollbar_button_hover_color=COLORS["border_light"],
        )
        self.library_frame.pack(fill="both", expand=True)
        self.library_frame.grid_columnconfigure(0, weight=1)
        self._bind_scroll_events()

        self.loading_label = ctk.CTkLabel(
            self.library_frame,
            text="Carregando catálogo...",
            font=FONT_BODY,
            text_color=COLORS["text_muted"],
        )
        self.loading_label.grid(row=0, column=0, pady=60)

        self._empty_label = ctk.CTkLabel(
            self.library_frame,
            text="",
            font=FONT_BODY,
            text_color=COLORS["text_muted"],
        )


    def _build_downloads(self) -> None:
        wrapper = ctk.CTkFrame(self, fg_color="transparent")
        wrapper.pack(fill="x", padx=16, pady=(8, 16))

        self.download_panel = DownloadPanel(wrapper)
        self.download_panel.pack(fill="x")

    def _show_setup(self) -> None:
        SetupWizard(self, self.settings, on_complete=self._initial_load)

    def _update_folder_display(self) -> None:
        folder = self.settings.games_folder or "Escolher pasta..."
        display = self._shorten_path(folder, max_len=38)
        self.folder_btn.configure(text=display)

    @staticmethod
    def _shorten_path(path: str, max_len: int = 38) -> str:
        if len(path) <= max_len:
            return path
        parts = Path(path).parts
        if len(parts) <= 2:
            return path[: max_len - 3] + "..."
        return str(Path(parts[0]) / "..." / Path(*parts[-2:]))

    def _change_games_folder(self) -> None:
        current = self.settings.games_folder or str(Path.home())
        folder = filedialog.askdirectory(
            title="Selecione a pasta dos jogos",
            initialdir=current if Path(current).exists() else None,
        )
        if not folder:
            return

        folder = str(Path(folder).resolve())
        if folder == self.settings.games_folder:
            return

        has_games = bool(self.settings.installed_games)
        msg = f"Usar esta pasta para os jogos?\n\n{folder}"
        if has_games:
            msg += (
                "\n\nOs jogos instalados serão procurados na nova pasta. "
                "Se ainda não estiverem lá, será necessário reinstalá-los."
            )

        if not messagebox.askyesno("Alterar pasta dos jogos", msg):
            return

        self.folder_btn.configure(state="disabled", text="Configurando...")

        def _apply() -> None:
            try:
                _, status = apply_games_folder(self.settings, folder)
                self.after(0, lambda: self._on_folder_changed(status))
            except Exception as exc:
                self.after(
                    0,
                    lambda: messagebox.showerror("Erro", f"Não foi possível alterar a pasta:\n{exc}"),
                )
                self.after(0, self._update_folder_display)
            finally:
                self.after(0, lambda: self.folder_btn.configure(state="normal"))

        threading.Thread(target=_apply, daemon=True).start()

    def _on_folder_changed(self, status: str) -> None:
        self._update_folder_display()
        self._reload_catalog()
        messagebox.showinfo("Pasta atualizada", status)

    def _initial_load(self) -> None:
        self._update_folder_display()
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
                self.after(0, lambda: self.reload_btn.configure(state="normal", text="Atualizar"))

        threading.Thread(target=_fetch, daemon=True).start()

    def _on_search_changed(self, _event=None) -> None:
        if self._search_job:
            try:
                self.after_cancel(self._search_job)
            except Exception:
                pass
        self._search_job = self.after(120, self._apply_search)

    def _apply_search(self) -> None:
        query = self.search_entry.get().strip().casefold()
        self._search_query = query
        self._filter_cards()

    def _filter_cards(self) -> None:
        query = self._search_query
        visible = 0

        self._empty_label.grid_forget()

        for i, game in enumerate(self._games):
            card = self._cards.get(game.name)
            if not card:
                continue
            match = (not query) or (query in game.name.casefold())
            if match:
                card.grid(row=i, column=0, sticky="ew", padx=10, pady=6)
                visible += 1
            else:
                card.grid_remove()

        if self._games and visible == 0:
            self._empty_label.configure(text=f'Nenhum jogo encontrado para "{self.search_entry.get().strip()}".')
            self._empty_label.grid(row=0, column=0, pady=60)
        elif not self._games:
            self._empty_label.configure(text="Nenhum jogo encontrado no catálogo.")
            self._empty_label.grid(row=0, column=0, pady=60)

    def _render_catalog(self, games: list[Game]) -> None:
        self.loading_label.grid_forget()
        self._empty_label.grid_forget()

        for card in self._cards.values():
            card.destroy()
        self._cards.clear()
        self._games = list(games)

        self.process_manager.refresh_all(games)

        if not games:
            self._empty_label.configure(text="Nenhum jogo encontrado no catálogo.")
            self._empty_label.grid(row=0, column=0, pady=60)
            return

        for i, game in enumerate(games):
            card = GameCard(
                self.library_frame,
                game,
                on_install=self._on_install,
                on_update=self._on_update,
                on_play=self._on_play,
                on_stop=self._on_stop,
                on_uninstall=self._on_uninstall,
            )
            card.grid(row=i, column=0, sticky="ew", padx=10, pady=6)
            self._cards[game.name] = card

        self._filter_cards()

    def _check_launcher_update(self) -> None:
        if self._update_prompted or self._updating_launcher:
            return
        if not self.catalog_service.launcher_update_available():
            return

        catalog = self.catalog_service.catalog
        if not catalog:
            return

        remote = catalog.launcher.latest_version
        local = LAUNCHER_VERSION
        self._update_prompted = True

        if not messagebox.askyesno(
            "Atualização do Launcher",
            f"Há uma nova versão do launcher disponível.\n\n"
            f"Instalada: {local}\n"
            f"Disponível: {remote}\n\n"
            f"Deseja baixar e instalar agora?\n"
            f"(O launcher será reiniciado automaticamente.)",
        ):
            return

        if not catalog.launcher.download:
            messagebox.showinfo(
                "Atualização",
                "Link de download não configurado no catálogo remoto.",
            )
            return

        self._start_launcher_update(catalog.launcher.download, remote or local)

    def _start_launcher_update(self, download_url: str, new_version: str) -> None:
        self._updating_launcher = True

        progress = ctk.CTkToplevel(self)
        progress.title("Atualizando launcher")
        progress.geometry("420x160")
        progress.resizable(False, False)
        progress.configure(fg_color=COLORS["bg_dark"])
        progress.transient(self)
        progress.grab_set()
        progress.protocol("WM_DELETE_WINDOW", lambda: None)

        status = ctk.CTkLabel(
            progress,
            text="Preparando...",
            font=FONT_BODY,
            text_color=COLORS["text"],
        )
        status.pack(pady=(24, 8), padx=20)

        bar = ctk.CTkProgressBar(progress, width=360, progress_color=COLORS["accent"])
        bar.pack(pady=8)
        bar.set(0)

        pct_label = ctk.CTkLabel(progress, text="0%", font=FONT_CAPTION, text_color=COLORS["text_dim"])
        pct_label.pack()

        def on_progress(msg: str, pct: float) -> None:
            def _ui() -> None:
                if not progress.winfo_exists():
                    return
                status.configure(text=msg)
                bar.set(max(0.0, min(1.0, pct / 100.0)))
                pct_label.configure(text=f"{pct:.0f}%")

            self.after(0, _ui)

        def _run() -> None:
            try:
                apply_launcher_update(
                    download_url,
                    new_version,
                    self.settings,
                    on_progress=on_progress,
                )
                self.after(0, lambda: self._finish_launcher_update(progress))
            except Exception as exc:
                self.after(0, lambda: self._fail_launcher_update(progress, str(exc)))

        threading.Thread(target=_run, daemon=True).start()

    def _finish_launcher_update(self, dialog: ctk.CTkToplevel) -> None:
        try:
            dialog.grab_release()
            dialog.destroy()
        except Exception:
            pass
        messagebox.showinfo(
            "Atualização",
            "Download concluído. O launcher será fechado e reiniciado com a nova versão.",
        )
        self.on_closing()

    def _fail_launcher_update(self, dialog: ctk.CTkToplevel, error: str) -> None:
        self._updating_launcher = False
        try:
            dialog.grab_release()
            dialog.destroy()
        except Exception:
            pass
        messagebox.showerror("Falha na atualização", error)

    def _start_process_monitor(self) -> None:
        def _tick() -> None:
            if self._updating_launcher:
                self._refresh_job = self.after(2000, _tick)
                return

            if self.catalog_service.catalog:
                games = self.catalog_service.catalog.games
                self._disk_sync_counter += 1

                if self._disk_sync_counter >= 5:
                    self._disk_sync_counter = 0
                    for game in games:
                        if game.status == GameStatus.RUNNING:
                            continue
                        before = game.status
                        sync_game_with_disk(game, self.settings)
                        if game.status != before:
                            card = self._cards.get(game.name)
                            if card:
                                card.refresh()

                changed = self.process_manager.refresh_all(games)
                for name, did_change in changed.items():
                    if not did_change:
                        continue
                    card = self._cards.get(name)
                    if card:
                        card.refresh()

            self._refresh_job = self.after(2000, _tick)

        self._refresh_job = self.after(2000, _tick)

    def _on_progress(self, game: Game) -> None:
        def _ui() -> None:
            card = self._cards.get(game.name)
            if card:
                card.refresh()
            self.download_panel.update_game(game)

            if game.download_state == DownloadState.ERROR:
                messagebox.showerror(
                    "Erro na instalação",
                    f"{game.name}\n\n{game.download_error}",
                )
            elif game.download_state == DownloadState.FINISHED:
                self.after(4500, lambda g=game: self._reset_download_state(g))

        self.after(0, _ui)

    def _reset_download_state(self, game: Game) -> None:
        if game.download_state == DownloadState.FINISHED:
            game.download_state = DownloadState.IDLE
            card = self._cards.get(game.name)
            if card:
                card.refresh()

    def _on_install(self, game: Game) -> None:
        self.installer.install(game, on_progress=self._on_progress)

    def _on_update(self, game: Game) -> None:
        if game.status == GameStatus.RUNNING:
            self.process_manager.stop(game)
        self.installer.install(game, on_progress=self._on_progress, is_update=True)

    def _on_play(self, game: Game) -> None:
        if not sync_game_with_disk(game, self.settings):
            messagebox.showinfo(
                "Jogo não encontrado",
                f"{game.name} não está instalado nesta pasta.\n\n"
                "Use Instalar para baixar novamente.",
            )
            card = self._cards.get(game.name)
            if card:
                card.refresh()
            return

        ok, msg = self.process_manager.start(game)
        if not ok:
            messagebox.showwarning("Aviso", msg)
        game.update_status(is_running=True)
        card = self._cards.get(game.name)
        if card:
            card.refresh()

    def _on_uninstall(self, game: Game) -> None:
        if game.status == GameStatus.RUNNING:
            messagebox.showwarning("Aviso", "Encerre o jogo antes de desinstalar.")
            return

        if not messagebox.askyesno(
            "Desinstalar",
            f"Remover {game.name}?\n\nTodos os arquivos da instalação serão apagados.",
        ):
            return

        self.installer.remove_installation(game)
        card = self._cards.get(game.name)
        if card:
            card.refresh()

    def _on_stop(self, game: Game) -> None:
        self.process_manager.stop(game)
        game.update_status(is_running=False)
        card = self._cards.get(game.name)
        if card:
            card.refresh(force=True)

    def on_closing(self) -> None:
        if self._refresh_job:
            self.after_cancel(self._refresh_job)
        self.destroy()
