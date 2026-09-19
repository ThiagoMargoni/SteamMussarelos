from __future__ import annotations

import threading

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QPushButton,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

from src.core.catalog import CatalogService
from src.core.debug_mode import log, log_exception
from src.core.emulators import (
    ensure_roms_dir,
    launch_args_for,
    mgba_dir,
    prepare_mgba_config,
    sync_emulator_with_disk,
)
from src.core.folder_setup import apply_games_folder
from src.core.install_state import sync_game_with_disk
from src.core.installer import Installer
from src.core.process_manager import ProcessManager
from src.core.settings import LAUNCHER_VERSION, LAYOUT_COVERS, Settings
from src.core.steam_launch import ensure_steam_running
from src.core.updater import apply_launcher_update, force_exit_for_update
from src.models.game import DownloadState, Game, GameStatus, RomEntry
from src.ui.action_icons import get_uninstall_icon
from src.ui.dialogs import ask_yes_no, show_error, show_info, show_warning
from src.ui.download_panel import DownloadPanel
from src.ui.emulator_settings_dialog import EmulatorSettingsDialog
from src.ui.game_card import GameCard
from src.ui.game_cover_card import GameCoverCard
from src.ui.mods_dialog import ModsDialog
from src.ui.progress_bar import RoundProgressBar
from src.ui.qt_bridge import ui_bridge, ui_call
from src.ui.roms_dialog import RomsDialog
from src.ui.scroll_frame import PlaceScrollFrame
from src.ui.settings_dialog import SettingsDialog
from src.ui.setup_wizard import SetupWizard
from src.ui.theme import (
    COLORS,
    HEADER_HEIGHT,
    app_stylesheet,
    btn_style,
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
        self._emulators: list[Game] = []
        self._library_section = "games"
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
        self._force_quit = False
        self._tray: QSystemTrayIcon | None = None
        self._tray_hint_shown = False
        self._settings_dialog: SettingsDialog | None = None

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
        self._apply_scroll_speed(self.settings.scroll_speed)
        app = QApplication.instance()
        if app is not None:
            app.setQuitOnLastWindowClosed(False)
        if self.settings.close_to_tray:
            self._setup_tray()

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

    def _create_card(self, parent, game: Game):
        kwargs = dict(
            parent=parent,
            game=game,
            on_install=self._on_install,
            on_update=self._on_update,
            on_play=self._on_play,
            on_stop=self._on_stop,
            on_uninstall=self._on_uninstall,
            on_mods=self._on_mods,
            on_configure=self._on_configure_emulator,
            uninstall_icon=self._uninstall_icon,
        )
        if self.settings.library_layout == LAYOUT_COVERS:
            return GameCoverCard(**kwargs)
        return GameCard(**kwargs)

    def _filtered_games(self) -> list[Game]:
        if not self._search_query:
            return list(self._games)
        return [g for g in self._games if self._search_query in g.name.casefold()]

    def _filtered_emulators(self) -> list[Game]:
        if not self._search_query:
            return list(self._emulators)
        q = self._search_query
        return [
            emu
            for emu in self._emulators
            if q in emu.name.casefold() or q in (emu.platform_name or "").casefold()
        ]

    def _card_for(self, name: str):
        return self.library_scroll.card_for(name)

    def _set_library_section(self, section: str) -> None:
        if section not in ("games", "emulators"):
            return
        if section == self._library_section:
            return
        self._library_section = section
        self._refresh_section_tabs()
        self._filter_cards()

    def _refresh_section_tabs(self) -> None:
        games_on = self._library_section == "games"
        self.games_tab_btn.setStyleSheet(
            btn_style(
                COLORS["accent"] if games_on else COLORS["bg_panel"],
                COLORS["accent_hover"] if games_on else COLORS["bg_card_hover"],
                COLORS["bg_medium"] if games_on else COLORS["text_dim"],
            )
        )
        emu_on = self._library_section == "emulators"
        self.emu_tab_btn.setStyleSheet(
            btn_style(
                COLORS["accent"] if emu_on else COLORS["bg_panel"],
                COLORS["accent_hover"] if emu_on else COLORS["bg_card_hover"],
                COLORS["bg_medium"] if emu_on else COLORS["text_dim"],
            )
        )
        if self._library_section == "games":
            self.search_entry.setPlaceholderText("Pesquisar jogos...")
        else:
            self.search_entry.setPlaceholderText("Pesquisar emuladores...")

    def _filter_cards(self) -> None:
        self._close_cover_popups()
        if self._library_section == "emulators":
            items = self._filtered_emulators()
            if not self._emulators:
                self.library_scroll.show_message("Nenhum emulador no catálogo.")
                return
            if not items:
                q = self.search_entry.text().strip()
                self.library_scroll.show_message(f'Nenhum emulador encontrado para "{q}".')
                return
            self.library_scroll.set_games(
                items, self._create_card, layout_mode=self.settings.library_layout
            )
            return

        filtered = self._filtered_games()
        if not self._games:
            self.library_scroll.show_message("Nenhum jogo encontrado no catálogo.")
            return
        if not filtered:
            q = self.search_entry.text().strip()
            self.library_scroll.show_message(f'Nenhum jogo encontrado para "{q}".')
            return
        self.library_scroll.set_games(
            filtered, self._create_card, layout_mode=self.settings.library_layout
        )

    def _close_cover_popups(self) -> None:
        for card in self.library_scroll.iter_cards():
            closer = getattr(card, "close_manage_popup", None)
            if callable(closer):
                closer()

    def _render_catalog(self, games: list[Game], emulators: list[Game] | None = None) -> None:
        self._games = list(games)
        self._emulators = list(emulators or [])
        self.process_manager.refresh_all(self._games + self._emulators)
        self._filter_cards()

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

        self.settings_btn = QPushButton("Configurações")
        self.settings_btn.setFlat(True)
        self.settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.settings_btn.setFixedSize(140, 36)
        self.settings_btn.setFont(font_button())
        self.settings_btn.setStyleSheet(
            btn_style(COLORS["bg_panel"], COLORS["bg_card_hover"], COLORS["text_dim"])
        )
        self.settings_btn.clicked.connect(self._open_settings)
        layout.addWidget(self.settings_btn, 0, Qt.AlignmentFlag.AlignVCenter)
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
        title_row.addSpacing(12)

        self.games_tab_btn = QPushButton("Jogos")
        self.games_tab_btn.setFlat(True)
        self.games_tab_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.games_tab_btn.setFixedHeight(32)
        self.games_tab_btn.setFont(font_button())
        self.games_tab_btn.clicked.connect(lambda: self._set_library_section("games"))
        title_row.addWidget(self.games_tab_btn)

        self.emu_tab_btn = QPushButton("Emuladores")
        self.emu_tab_btn.setFlat(True)
        self.emu_tab_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.emu_tab_btn.setFixedHeight(32)
        self.emu_tab_btn.setFont(font_button())
        self.emu_tab_btn.clicked.connect(lambda: self._set_library_section("emulators"))
        title_row.addWidget(self.emu_tab_btn)

        title_row.addStretch(1)
        self.search_entry = QLineEdit()
        self.search_entry.setPlaceholderText("Pesquisar jogos...")
        self.search_entry.setFixedSize(260, 34)
        self.search_entry.setFont(font_body())
        self.search_entry.textChanged.connect(self._on_search_changed)
        self.search_entry.returnPressed.connect(self._apply_search)
        title_row.addWidget(self.search_entry)
        layout.addLayout(title_row)
        self._refresh_section_tabs()

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

    def _apply_scroll_speed(self, speed: float) -> None:
        self.library_scroll.set_scroll_speed(speed)
        self.download_panel.set_scroll_speed(speed)

    def _setup_tray(self) -> None:
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        icon = self.windowIcon()
        if icon.isNull():
            path = resolve_resource("assets", "app.ico")
            if path:
                icon = QIcon(str(path.resolve()))
        self._tray = QSystemTrayIcon(icon, self)
        self._tray.setToolTip("Steam dos Mussarelos")

        menu = QMenu()
        menu.setStyleSheet(
            f"""
            QMenu {{
                background-color: {COLORS['bg_medium']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                padding: 4px;
            }}
            QMenu::item {{
                padding: 8px 24px;
                background: transparent;
            }}
            QMenu::item:selected {{
                background-color: {COLORS['bg_card']};
            }}
            """
        )
        open_action = QAction("Abrir", self)
        open_action.triggered.connect(self._restore_from_tray)
        quit_action = QAction("Sair", self)
        quit_action.triggered.connect(self._quit_app)
        menu.addAction(open_action)
        menu.addSeparator()
        menu.addAction(quit_action)
        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._on_tray_activated)
        self._tray.show()

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self._restore_from_tray()

    def _restore_from_tray(self) -> None:
        self.restore_from_background()

    def restore_from_background(self) -> None:
        if self.isHidden():
            self.show()
        self.showNormal()
        self.raise_()
        self.activateWindow()
        if self._tray is not None and self.settings.close_to_tray:
            self._tray.show()

    def _quit_app(self) -> None:
        self._force_quit = True
        self._monitor_timer.stop()
        if self._tray is not None:
            self._tray.hide()
        self.close()
        QApplication.instance().quit()

    def _open_settings(self) -> None:
        if self._settings_dialog is not None and self._settings_dialog.isVisible():
            self._settings_dialog.raise_()
            self._settings_dialog.activateWindow()
            return
        dialog = SettingsDialog(self, self.settings, on_apply=self._apply_settings)
        self._settings_dialog = dialog
        dialog.finished.connect(lambda _=0: setattr(self, "_settings_dialog", None))
        dialog.exec()

    def _apply_settings(
        self,
        *,
        folder_change: str | None,
        scroll_speed: float | None,
        close_to_tray: bool | None,
        library_layout: str | None = None,
    ) -> None:
        if scroll_speed is not None:
            self.settings.scroll_speed = scroll_speed
            self._apply_scroll_speed(scroll_speed)
        if close_to_tray is not None:
            self.settings.close_to_tray = close_to_tray
            app = QApplication.instance()
            if close_to_tray:
                if self._tray is None:
                    self._setup_tray()
                else:
                    self._tray.show()
            elif self._tray is not None:
                self._tray.hide()
                self._tray = None
            if app is not None:
                app.setQuitOnLastWindowClosed(False)
        if library_layout is not None:
            changed = library_layout != self.settings.library_layout
            self.settings.library_layout = library_layout
            if changed:
                self._filter_cards()
        if folder_change:
            self._change_games_folder(folder_change)

    def _change_games_folder(self, folder: str) -> None:
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
            finally:
                ui_call(self._notify_settings_folder_done)

        threading.Thread(target=_apply, daemon=True).start()

    def _notify_settings_folder_done(self) -> None:
        if self._settings_dialog is not None:
            self._settings_dialog.notify_folder_done()

    def _on_folder_changed(self, status: str) -> None:
        self._reload_catalog()
        show_info(self, "Pasta atualizada", status)

    def _initial_load(self) -> None:
        self._reload_catalog()

    def _reload_catalog(self) -> None:
        self.reload_btn.setEnabled(False)
        self.reload_btn.setText("Atualizando...")

        def _fetch() -> None:
            try:
                catalog = self.catalog_service.fetch()
                ui_call(
                    lambda: self._render_catalog(catalog.games, catalog.emulators)
                )
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
        self._force_quit = True
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
        emulators = self.catalog_service.catalog.emulators
        tracked = games + emulators
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
            for emu in emulators:
                if emu.status == GameStatus.RUNNING:
                    continue
                if emu.download_state in (
                    DownloadState.DOWNLOADING,
                    DownloadState.EXTRACTING,
                ):
                    continue
                before = emu.status
                sync_emulator_with_disk(emu, self.settings)
                if emu.status != before:
                    card = self._card_for(emu.name)
                    if card:
                        card.refresh()

        changed = self.process_manager.refresh_all(tracked)
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
                if game.is_emulator and game.platform_id:
                    try:
                        ensure_roms_dir(self.settings, game.platform_id)
                    except Exception:
                        pass
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
        log("info", "on_play", name=game.name, emulator=game.is_emulator)
        if game.is_emulator:
            self._open_roms(game)
            return

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
        log("info", "on_play result", name=game.name, ok=ok, msg=msg)
        if not ok:
            show_warning(self, "Aviso", msg)
        game.update_status(is_running=True)
        card = self._card_for(game.name)
        if card:
            card.refresh()

    def _open_roms(self, emulator: Game) -> None:
        sync_emulator_with_disk(emulator, self.settings)
        if emulator.status == GameStatus.NOT_INSTALLED:
            show_info(
                self,
                "Emulador",
                f"Baixe o {emulator.name} antes de jogar ROMs.",
            )
            return
        RomsDialog(
            self,
            emulator,
            self.settings,
            on_play=self._on_play_rom,
        ).exec()
        card = self._card_for(emulator.name)
        if card:
            card.refresh()

    def _on_configure_emulator(self, emulator: Game) -> None:
        sync_emulator_with_disk(emulator, self.settings)
        if emulator.status == GameStatus.NOT_INSTALLED:
            show_info(
                self,
                "Emulador",
                f"Baixe o {emulator.name} antes de configurar.",
            )
            return
        EmulatorSettingsDialog(self, emulator).exec()

    def _on_play_rom(self, emulator: Game, rom: RomEntry) -> None:
        log(
            "info",
            "on_play_rom",
            emulator=emulator.name,
            rom=rom.name,
            path=rom.path,
            installed=rom.installed,
        )
        sync_emulator_with_disk(emulator, self.settings)
        if emulator.status == GameStatus.NOT_INSTALLED:
            show_info(
                self,
                "Emulador",
                f"Baixe o {emulator.name} antes de jogar ROMs.",
            )
            return
        if emulator.status == GameStatus.RUNNING:
            show_warning(self, "Aviso", f"{emulator.name} já está em execução.")
            return
        if not rom.installed or not rom.path:
            show_warning(self, "ROM", "Baixe a ROM antes de jogar.")
            return
        try:
            prepare_mgba_config(emulator, rom.platform_id)
            args = launch_args_for(emulator, rom)
            cwd = str(mgba_dir(emulator))
            log("info", "play_rom launch", cwd=cwd, args=args, exe=emulator.executable)
            ok, msg = self.process_manager.start(
                emulator,
                args=args,
                cwd=cwd,
            )
        except Exception as exc:
            log_exception("play_rom falhou", exc)
            show_error(self, "Emulador", str(exc))
            return
        log("info", "play_rom result", ok=ok, msg=msg, pid=emulator.pid)
        if not ok:
            show_warning(self, "Aviso", msg)
            return
        emulator.update_status(is_running=True)
        if self.isHidden():
            self.show()
        self.showNormal()
        self.raise_()
        card = self._card_for(emulator.name)
        if card:
            card.refresh()

    def _on_uninstall(self, game: Game) -> None:
        if game.status == GameStatus.RUNNING:
            show_warning(self, "Aviso", "Encerre o jogo antes de desinstalar.")
            return
        if game.is_emulator:
            if not ask_yes_no(
                self,
                "Desinstalar emulador",
                f"Remover {game.name}?\n\n"
                "As ROMs e os saves NÃO serão apagados.",
            ):
                return
        elif not ask_yes_no(
            self,
            "Desinstalar",
            f"Remover {game.name}?\n\nTodos os arquivos da instalação serão apagados.",
        ):
            return
        self.installer.remove_installation(game)
        card = self._card_for(game.name)
        if card:
            card.refresh()

    def _on_mods(self, game: Game) -> None:
        if not game.supports_mods:
            return
        if game.status == GameStatus.NOT_INSTALLED or not game.install_path:
            show_info(
                self,
                "Mods",
                f"Instale {game.name} antes de gerenciar mods.",
            )
            return
        ModsDialog(self, game, self.settings).exec()

    def _on_stop(self, game: Game) -> None:
        self.process_manager.stop(game)
        game.update_status(is_running=False)
        card = self._card_for(game.name)
        if card:
            card.refresh(force=True)

    def on_closing(self) -> None:
        self._quit_app()

    def closeEvent(self, event) -> None:
        log(
            "info",
            "closeEvent",
            force=self._force_quit,
            close_to_tray=self.settings.close_to_tray,
        )
        if self._force_quit or not self.settings.close_to_tray:
            self._monitor_timer.stop()
            if self._tray is not None:
                self._tray.hide()
            event.accept()
            QApplication.instance().quit()
            return

        if self._tray is None or not QSystemTrayIcon.isSystemTrayAvailable():
            self._monitor_timer.stop()
            event.accept()
            QApplication.instance().quit()
            return

        event.ignore()
        self.hide()
        if not self._tray_hint_shown:
            self._tray_hint_shown = True
            self._tray.showMessage(
                "Steam dos Mussarelos",
                "O launcher continua em segundo plano. Clique no ícone da bandeja para abrir ou sair.",
                QSystemTrayIcon.MessageIcon.Information,
                4000,
            )
