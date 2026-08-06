from __future__ import annotations

import threading
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.core.catalog import CatalogService
from src.core.folder_setup import apply_games_folder
from src.core.install_state import sync_game_with_disk
from src.core.installer import Installer
from src.core.process_manager import ProcessManager
from src.core.settings import LAUNCHER_VERSION, Settings
from src.core.steam_launch import ensure_steam_running
from src.core.updater import apply_launcher_update, force_exit_for_update
from src.models.game import DownloadState, Game, GameStatus
from src.ui.action_icons import get_uninstall_icon
from src.ui.dialogs import ask_yes_no, show_error, show_info, show_warning
from src.ui.download_panel import DownloadPanel
from src.ui.game_card import GameCard
from src.ui.progress_bar import RoundProgressBar
from src.ui.qt_bridge import ui_bridge, ui_call
from src.ui.scroll_frame import PlaceScrollFrame
from src.ui.setup_wizard import SetupWizard
from src.ui.theme import (
    COLORS,
    HEADER_HEIGHT,
    app_stylesheet,
    font_body,
    font_button,
    font_caption,
    font_display,
    font_heading,
)
from src.utils.paths import resolve_resource

class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        ui_bridge()
        self.settings = Settings()
        self.catalog_service = CatalogService(self.settings)
        self.installer = Installer(self.settings)
        self.process_manager = ProcessManager()

        self._games: list[Game] = []
        self._search_query = ""
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.timeout.connect(self._apply_search)
        self._monitor_timer = QTimer(self)
        self._monitor_timer.timeout.connect(self._process_tick)
        self._disk_sync_counter = 0
        self._update_prompted = False
        self._updating_launcher = False
        self._uninstall_icon = get_uninstall_icon()

        self.setWindowTitle("Steam dos Mussarelos")
        self.resize(1024, 760)
        self.setMinimumSize(900, 640)
        self.setStyleSheet(app_stylesheet())
        self._set_window_icon()

        central = QWidget()
        central.setObjectName("centralRoot")
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._build_header(root)
        self._build_library(root)
        self._build_downloads(root)

        if not self.settings.first_run_complete or not self.settings.games_folder:
            QTimer.singleShot(200, self._show_setup)
        else:
            QTimer.singleShot(200, self._initial_load)

        QTimer.singleShot(400, self._ensure_steam)
        self._monitor_timer.start(2000)

    def _set_window_icon(self, window=None) -> None:
        icon_path = resolve_resource("assets", "app.ico")
        if not icon_path:
            return
        icon = QIcon(str(icon_path.resolve()))
        (window or self).setWindowIcon(icon)

    def _create_card(self, parent, game: Game) -> GameCard:
        return GameCard(
            parent,
            game,
            on_install=self._on_install,
            on_update=self._on_update,
            on_play=self._on_play,
            on_stop=self._on_stop,
            on_uninstall=self._on_uninstall,
            uninstall_icon=self._uninstall_icon,
        )

    def _filtered_games(self) -> list[Game]:
        if not self._search_query:
            return list(self._games)
        return [g for g in self._games if self._search_query in g.name.casefold()]

    def _card_for(self, name: str) -> GameCard | None:
        return self.library_scroll.card_for(name)

    def _ensure_steam(self) -> None:
        def _run() -> None:
            ok, msg = ensure_steam_running()
            if not ok:
                ui_call(
                    lambda: show_warning(
                        self,
                        "Steam",
                        f"{msg}\n\nAlguns jogos podem precisar da Steam aberta.",
                    )
                )

        threading.Thread(target=_run, daemon=True).start()

    def _build_header(self, root: QVBoxLayout) -> None:
        header = QFrame()
        header.setObjectName("appHeader")
        header.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        header.setFixedHeight(HEADER_HEIGHT)
        layout = QHBoxLayout(header)
        layout.setContentsMargins(20, 0, 16, 0)
        layout.setSpacing(8)

        left = QVBoxLayout()
        left.setContentsMargins(0, 10, 0, 0)
        left.setSpacing(0)
        title = QLabel("STEAM DOS MUSSARELOS")
        title.setFont(font_display())
        title.setStyleSheet(f"color: {COLORS['accent']}; background: transparent;")
        left.addWidget(title)
        subtitle = QLabel("Biblioteca de jogos")
        subtitle.setFont(font_caption())
        subtitle.setStyleSheet(f"color: {COLORS['text_muted']}; background: transparent;")
        left.addWidget(subtitle)
        layout.addLayout(left, 1)

        from src.ui.theme import btn_style

        self.reload_btn = QPushButton("Atualizar")
        self.reload_btn.setFlat(True)
        self.reload_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.reload_btn.setFixedSize(120, 36)
        self.reload_btn.setFont(font_button())
        self.reload_btn.setStyleSheet(
            btn_style(COLORS["bg_card"], COLORS["bg_card_hover"], COLORS["text"])
        )
        self.reload_btn.clicked.connect(self._reload_catalog)
        layout.addWidget(self.reload_btn, 0, Qt.AlignmentFlag.AlignVCenter)

        self.folder_btn = QPushButton("Pasta dos jogos")
        self.folder_btn.setFlat(True)
        self.folder_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.folder_btn.setFixedSize(300, 36)
        self.folder_btn.setFont(font_caption())
        self.folder_btn.setStyleSheet(
            btn_style(
                COLORS["bg_panel"],
                COLORS["bg_card_hover"],
                COLORS["text_dim"],
                align="left",
            )
        )
        self.folder_btn.clicked.connect(self._change_games_folder)
        layout.addWidget(self.folder_btn, 0, Qt.AlignmentFlag.AlignVCenter)
        root.addWidget(header)

    def _build_library(self, root: QVBoxLayout) -> None:
        wrap = QWidget()
        wrap.setObjectName("libraryWrap")
        layout = QVBoxLayout(wrap)
        layout.setContentsMargins(16, 12, 16, 0)
        layout.setSpacing(8)

        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        label = QLabel("Biblioteca")
        label.setFont(font_heading())
        label.setStyleSheet(f"color: {COLORS['text']}; background: transparent;")
        title_row.addWidget(label)
        title_row.addStretch(1)
        self.search_entry = QLineEdit()
        self.search_entry.setPlaceholderText("Pesquisar jogos...")
        self.search_entry.setFixedSize(260, 34)
        self.search_entry.setFont(font_body())
        self.search_entry.textChanged.connect(self._on_search_changed)
        self.search_entry.returnPressed.connect(self._apply_search)
        title_row.addWidget(self.search_entry)
        layout.addLayout(title_row)

        self.library_scroll = PlaceScrollFrame()
        layout.addWidget(self.library_scroll, 1)
        self.library_scroll.show_message("Carregando catálogo...")
        root.addWidget(wrap, 1)

    def _build_downloads(self, root: QVBoxLayout) -> None:
        wrap = QWidget()
        wrap.setObjectName("downloadsWrap")
        layout = QVBoxLayout(wrap)
        layout.setContentsMargins(16, 8, 16, 16)
        self.download_panel = DownloadPanel()
        layout.addWidget(self.download_panel)
        root.addWidget(wrap)

    def _show_setup(self) -> None:
        SetupWizard(self, self.settings, on_complete=self._initial_load).exec()

    def _update_folder_display(self) -> None:
        folder = self.settings.games_folder or "Escolher pasta..."
        self.folder_btn.setText(self._shorten_path(folder, max_len=38))

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
        folder = QFileDialog.getExistingDirectory(
            self,
            "Selecione a pasta dos jogos",
            current if Path(current).exists() else "",
        )
        if not folder:
            return
        folder = str(Path(folder).resolve())
        if folder == self.settings.games_folder:
            return

        msg = f"Usar esta pasta para os jogos?\n\n{folder}"
        if self.settings.installed_games:
            msg += (
                "\n\nOs jogos instalados serão procurados na nova pasta. "
                "Se ainda não estiverem lá, será necessário reinstalá-los."
            )
        if not ask_yes_no(self, "Alterar pasta dos jogos", msg):
            return

        self.folder_btn.setEnabled(False)
        self.folder_btn.setText("Configurando...")

        def _apply() -> None:
            try:
                _, status = apply_games_folder(self.settings, folder)
                ui_call(lambda: self._on_folder_changed(status))
            except Exception as exc:
                ui_call(
                    lambda: show_error(
                        self, "Erro", f"Não foi possível alterar a pasta:\n{exc}"
                    )
                )
                ui_call(self._update_folder_display)
            finally:
                ui_call(lambda: self.folder_btn.setEnabled(True))

        threading.Thread(target=_apply, daemon=True).start()

    def _on_folder_changed(self, status: str) -> None:
        self._update_folder_display()
        self._reload_catalog()
        show_info(self, "Pasta atualizada", status)

    def _initial_load(self) -> None:
        self._update_folder_display()
        self._reload_catalog()

    def _reload_catalog(self) -> None:
        self.reload_btn.setEnabled(False)
        self.reload_btn.setText("Atualizando...")

        def _fetch() -> None:
            try:
                catalog = self.catalog_service.fetch()
                ui_call(lambda: self._render_catalog(catalog.games))
                ui_call(self._check_launcher_update)
            except Exception as exc:
                ui_call(
                    lambda: show_error(self, "Erro", f"Falha ao carregar catálogo:\n{exc}")
                )
            finally:
                ui_call(lambda: (self.reload_btn.setEnabled(True), self.reload_btn.setText("Atualizar")))

        threading.Thread(target=_fetch, daemon=True).start()

    def _on_search_changed(self, _text: str = "") -> None:
        self._search_timer.start(120)

    def _apply_search(self) -> None:
        self._search_query = self.search_entry.text().strip().casefold()
        self._filter_cards()

    def _filter_cards(self) -> None:
        filtered = self._filtered_games()
        if not self._games:
            self.library_scroll.show_message("Nenhum jogo encontrado no catálogo.")
            return
        if not filtered:
            q = self.search_entry.text().strip()
            self.library_scroll.show_message(f'Nenhum jogo encontrado para "{q}".')
            return
        self.library_scroll.set_games(filtered, self._create_card)

    def _render_catalog(self, games: list[Game]) -> None:
        self._games = list(games)
        self.process_manager.refresh_all(games)
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
        if not ask_yes_no(
            self,
            "Atualização do Launcher",
            f"Há uma nova versão do launcher disponível.\n\n"
            f"Instalada: {local}\n"
            f"Disponível: {remote}\n\n"
            f"Deseja baixar e instalar agora?\n"
            f"(O launcher será reiniciado automaticamente.)",
        ):
            return
        if not catalog.launcher.download:
            show_info(self, "Atualização", "Link de download não configurado no catálogo remoto.")
            return
        self._start_launcher_update(catalog.launcher.download, remote or local)

    def _start_launcher_update(self, download_url: str, new_version: str) -> None:
        self._updating_launcher = True
        dialog = QDialog(self)
        dialog.setWindowTitle("Atualizando launcher")
        dialog.setFixedSize(420, 160)
        dialog.setModal(True)
        dialog.setWindowFlag(Qt.WindowType.WindowCloseButtonHint, False)
        dialog.setStyleSheet(f"background-color: {COLORS['bg_dark']};")
        self._set_window_icon(dialog)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(20, 24, 20, 20)
        status = QLabel("Preparando...")
        status.setFont(font_body())
        status.setStyleSheet(f"color: {COLORS['text']};")
        layout.addWidget(status)
        bar = RoundProgressBar()
        bar.setRange(0, 100)
        bar.setValue(0)
        layout.addWidget(bar)
        pct_label = QLabel("0%")
        pct_label.setFont(font_caption())
        pct_label.setStyleSheet(f"color: {COLORS['text_dim']};")
        layout.addWidget(pct_label)

        def on_progress(msg: str, pct: float) -> None:
            ui_call(
                lambda: (
                    status.setText(msg),
                    bar.setValue(int(max(0, min(100, pct)))),
                    pct_label.setText(f"{pct:.0f}%"),
                )
            )

        def _run() -> None:
            try:
                apply_launcher_update(
                    download_url,
                    new_version,
                    self.settings,
                    on_progress=on_progress,
                )
                ui_call(lambda: self._finish_launcher_update(dialog))
            except Exception as exc:
                ui_call(lambda: self._fail_launcher_update(dialog, str(exc)))

        dialog.show()
        threading.Thread(target=_run, daemon=True).start()

    def _finish_launcher_update(self, dialog: QDialog) -> None:
        dialog.accept()
        show_info(
            self,
            "Atualização",
            "Download concluído. O launcher vai fechar e a nova versão vai\n"
            "substituir este executável e abrir de novo.\n"
            "Se o Windows pedir permissão (UAC), aceite.",
        )
        self._monitor_timer.stop()
        self.close()
        force_exit_for_update()

    def _fail_launcher_update(self, dialog: QDialog, error: str) -> None:
        self._updating_launcher = False
        dialog.reject()
        show_error(
            self,
            "Falha na atualização",
            f"{error}\n\n"
            "Se o Defender bloqueou o arquivo, permita o app e tente de novo,\n"
            "ou baixe o release em GitHub → Releases.",
        )

    def _process_tick(self) -> None:
        if self._updating_launcher or not self.catalog_service.catalog:
            return
        games = self.catalog_service.catalog.games
        self._disk_sync_counter += 1
        if self._disk_sync_counter >= 5:
            self._disk_sync_counter = 0
            for game in games:
                if game.status == GameStatus.RUNNING:
                    continue
                if game.download_state in (
                    DownloadState.DOWNLOADING,
                    DownloadState.EXTRACTING,
                ):
                    continue
                before = game.status
                sync_game_with_disk(game, self.settings)
                if game.status != before:
                    card = self._card_for(game.name)
                    if card:
                        card.refresh()

        changed = self.process_manager.refresh_all(games)
        for name, did_change in changed.items():
            if not did_change:
                continue
            card = self._card_for(name)
            if card:
                card.refresh()

    def _on_progress(self, game: Game) -> None:
        def _ui() -> None:
            card = self._card_for(game.name)
            if card:
                card.refresh()
            self.download_panel.update_game(game)
            if game.download_state == DownloadState.ERROR:
                show_error(
                    self,
                    "Erro na instalação",
                    f"{game.name}\n\n{game.download_error}",
                )
            elif game.download_state == DownloadState.FINISHED:
                QTimer.singleShot(4500, lambda g=game: self._reset_download_state(g))

        ui_call(_ui)

    def _reset_download_state(self, game: Game) -> None:
        if game.download_state == DownloadState.FINISHED:
            game.download_state = DownloadState.IDLE
            card = self._card_for(game.name)
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
            show_info(
                self,
                "Jogo não encontrado",
                f"{game.name} não está instalado nesta pasta.\n\n"
                "Use Instalar para baixar novamente.",
            )
            card = self._card_for(game.name)
            if card:
                card.refresh()
            return
        ok, msg = self.process_manager.start(game)
        if not ok:
            show_warning(self, "Aviso", msg)
        game.update_status(is_running=True)
        card = self._card_for(game.name)
        if card:
            card.refresh()

    def _on_uninstall(self, game: Game) -> None:
        if game.status == GameStatus.RUNNING:
            show_warning(self, "Aviso", "Encerre o jogo antes de desinstalar.")
            return
        if not ask_yes_no(
            self,
            "Desinstalar",
            f"Remover {game.name}?\n\nTodos os arquivos da instalação serão apagados.",
        ):
            return
        self.installer.remove_installation(game)
        card = self._card_for(game.name)
        if card:
            card.refresh()

    def _on_stop(self, game: Game) -> None:
        self.process_manager.stop(game)
        game.update_status(is_running=False)
        card = self._card_for(game.name)
        if card:
            card.refresh(force=True)

    def on_closing(self) -> None:
        self._monitor_timer.stop()
        self.close()

    def closeEvent(self, event) -> None:
        self._monitor_timer.stop()
        super().closeEvent(event)
