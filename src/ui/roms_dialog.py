from __future__ import annotations

import subprocess
import threading
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from src.core.emulators import (
    add_rom,
    battery_save_path,
    download_rom,
    export_battery_save,
    has_battery_save,
    import_battery_save,
    list_roms,
    remove_rom,
)
from src.core.settings import Settings
from src.models.game import Game, GameStatus, RomEntry
from src.ui.dialogs import ask_yes_no, show_error, show_info
from src.ui.flow_layout import FlowLayout
from src.ui.qt_bridge import ui_call
from src.ui.rom_cover_card import RomCoverCard
from src.ui.theme import COLORS, btn_style, font_body, font_button, font_caption, font_heading

class RomsDialog(QDialog):
    def __init__(
        self,
        parent: QWidget,
        emulator: Game,
        settings: Settings,
        on_play,
    ) -> None:
        super().__init__(parent)
        self.emulator = emulator
        self.settings = settings
        self._on_play = on_play
        self._busy = False

        title = emulator.platform_name or emulator.name
        self.setObjectName("romsDialog")
        self.setWindowTitle(f"ROMs - {title}")
        self.setModal(True)
        self.setMinimumSize(720, 520)
        self.resize(780, 560)
        self.setStyleSheet(
            f"QDialog#romsDialog {{ background-color: {COLORS['bg_dark']}; }}"
        )
        if parent is not None and not parent.windowIcon().isNull():
            self.setWindowIcon(parent.windowIcon())

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 16)
        root.setSpacing(0)

        heading = QLabel(f"ROMs - {title}", self)
        heading.setFont(font_heading())
        heading.setStyleSheet(f"color: {COLORS['accent']}; background: transparent;")
        root.addWidget(heading)
        root.addSpacing(4)

        self.hint = QLabel(
            "Clique para jogar ou baixar. Botão direito para save e remover.",
            self,
        )
        self.hint.setFont(font_caption())
        self.hint.setWordWrap(True)
        self.hint.setStyleSheet(f"color: {COLORS['text_muted']}; background: transparent;")
        root.addWidget(self.hint)
        root.addSpacing(12)

        self.list_host = QWidget(self)
        self.list_host.setObjectName("romsGridHost")
        self.list_host.setStyleSheet(
            f"QWidget#romsGridHost {{ background: {COLORS['bg_panel']}; }}"
        )
        self.grid = FlowLayout(
            self.list_host,
            margin_left=14,
            margin_top=14,
            margin_right=14,
            margin_bottom=14,
            hspacing=12,
            vspacing=12,
        )

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setStyleSheet(
            f"QScrollArea {{ background: {COLORS['bg_panel']}; border: 1px solid {COLORS['border']};"
            f" border-radius: 8px; }}"
        )
        scroll.setWidget(self.list_host)
        root.addWidget(scroll, 1)
        root.addSpacing(12)

        buttons = QHBoxLayout()
        buttons.setSpacing(8)

        self.add_btn = QPushButton("Adicionar", self)
        self.add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_btn.setFixedHeight(34)
        self.add_btn.setFont(font_button())
        self.add_btn.setStyleSheet(
            btn_style(COLORS["accent"], COLORS["accent_hover"], COLORS["bg_medium"])
        )
        self.add_btn.clicked.connect(self._add_rom)
        buttons.addWidget(self.add_btn)

        close_btn = QPushButton("Fechar", self)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setFixedSize(100, 34)
        close_btn.setFont(font_button())
        close_btn.setStyleSheet(
            btn_style(COLORS["bg_card"], COLORS["bg_card_hover"], COLORS["text"])
        )
        close_btn.clicked.connect(self.accept)
        buttons.addWidget(close_btn)
        root.addLayout(buttons)

        ready = emulator.status in (
            GameStatus.INSTALLED,
            GameStatus.UPDATE_AVAILABLE,
            GameStatus.RUNNING,
        ) and bool(emulator.install_path)
        self.add_btn.setEnabled(ready and not self._busy)
        if not ready:
            self.hint.setText("Baixe o emulador antes de gerenciar ROMs.")

        self._refresh_list()

    def _clear_grid(self) -> None:
        while self.grid.count():
            item = self.grid.takeAt(0)
            widget = item.widget() if item is not None else None
            if widget is not None:
                widget.deleteLater()

    def _refresh_list(self) -> None:
        self._clear_grid()
        roms = list_roms(self.settings, self.emulator)
        if not roms:
            empty = QLabel("Nenhuma ROM.", self.list_host)
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setFont(font_body())
            empty.setStyleSheet(
                f"color: {COLORS['text_muted']}; background: transparent; padding: 40px;"
            )
            self.grid.addWidget(empty)
            return

        emu_ready = self.emulator.status in (
            GameStatus.INSTALLED,
            GameStatus.UPDATE_AVAILABLE,
            GameStatus.RUNNING,
        ) and bool(self.emulator.install_path)
        can_play = emu_ready and self.emulator.status != GameStatus.RUNNING

        for rom in roms:
            card = RomCoverCard(
                self.list_host,
                rom,
                on_play=self._play_rom,
                on_download=self._download_rom,
                on_save=self._save_menu,
                on_remove=self._remove_rom,
                can_play=can_play,
                busy=self._busy,
            )
            self.grid.addWidget(card)

    def _save_menu(self, rom: RomEntry, anchor: QPushButton) -> None:
        menu = QMenu(self)
        menu.setStyleSheet(
            f"""
            QMenu {{
                background-color: {COLORS['bg_medium']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                padding: 4px;
            }}
            QMenu::item {{
                padding: 8px 18px;
                background: transparent;
            }}
            QMenu::item:selected {{
                background-color: {COLORS['bg_card']};
            }}
            QMenu::item:disabled {{
                color: {COLORS['text_muted']};
            }}
            """
        )
        act_import = menu.addAction("Importar save...")
        act_export = menu.addAction("Exportar save...")
        act_show = menu.addAction("Localizar save")
        has_save = has_battery_save(rom)
        act_export.setEnabled(has_save)
        act_show.setEnabled(has_save)

        chosen = menu.exec(anchor.mapToGlobal(anchor.rect().bottomLeft()))
        if chosen is act_import:
            self._import_save(rom)
        elif chosen is act_export:
            self._export_save(rom)
        elif chosen is act_show:
            self._reveal_save(rom)

    def _import_save(self, rom: RomEntry) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            f'Importar save — {rom.name}',
            "",
            "Saves (*.sav *.sa1 *.sa2);;Todos os arquivos (*.*)",
        )
        if not path:
            return
        try:
            dest = import_battery_save(rom, Path(path))
        except Exception as exc:
            show_error(self, "Save", str(exc))
            return
        show_info(self, "Save", f"Save importado para:\n{dest}")
        self._refresh_list()

    def _export_save(self, rom: RomEntry) -> None:
        default = battery_save_path(rom).name
        path, _ = QFileDialog.getSaveFileName(
            self,
            f'Exportar save — {rom.name}',
            default,
            "Saves (*.sav);;Todos os arquivos (*.*)",
        )
        if not path:
            return
        try:
            dest = export_battery_save(rom, Path(path))
        except Exception as exc:
            show_error(self, "Save", str(exc))
            return
        show_info(self, "Save", f"Save exportado para:\n{dest}")

    def _reveal_save(self, rom: RomEntry) -> None:
        path = battery_save_path(rom)
        if not path.is_file():
            show_info(self, "Save", "Ainda não existe save para esta ROM.")
            return
        try:
            subprocess.Popen(["explorer", "/select,", str(path)])
        except OSError as exc:
            show_error(self, "Save", str(exc))

    def _add_rom(self) -> None:
        if self._busy:
            return
        exts = self.emulator.rom_extensions or [".gba"]
        patterns = " ".join(f"*{e}" for e in exts)
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Selecionar ROM",
            "",
            f"ROMs ({patterns});;Todos os arquivos (*.*)",
        )
        if not path:
            return
        try:
            add_rom(self.settings, self.emulator, Path(path))
        except Exception as exc:
            show_error(self, "ROMs", str(exc))
            return
        self._refresh_list()

    def _remove_rom(self, rom: RomEntry) -> None:
        if self._busy:
            return
        if not ask_yes_no(self, "Remover ROM", f'Remover "{rom.name}"?\n\n{rom.filename}'):
            return
        try:
            remove_rom(rom)
        except Exception as exc:
            show_error(self, "ROMs", str(exc))
            return
        self._refresh_list()

    def _play_rom(self, rom: RomEntry) -> None:
        if self._busy:
            return
        play = self._on_play
        emu = self.emulator
        try:
            play(emu, rom)
        finally:
            self.accept()

    def _download_rom(self, rom: RomEntry) -> None:
        if self._busy or not rom.download:
            return
        self._busy = True
        self.add_btn.setEnabled(False)
        self.hint.setText(f'Baixando "{rom.name}"...')
        self._refresh_list()

        def _run() -> None:
            try:
                downloaded = download_rom(
                    self.settings,
                    self.emulator,
                    rom,
                    on_status=lambda text: ui_call(
                        lambda t=text: self.hint.setText(f"{t} — {rom.name}")
                    ),
                )
                ui_call(lambda: self._download_done(downloaded, None))
            except Exception as exc:
                ui_call(lambda: self._download_done(None, str(exc)))

        threading.Thread(target=_run, daemon=True).start()

    def _download_done(self, rom: RomEntry | None, error: str | None) -> None:
        self._busy = False
        ready = self.emulator.status in (
            GameStatus.INSTALLED,
            GameStatus.UPDATE_AVAILABLE,
            GameStatus.RUNNING,
        ) and bool(self.emulator.install_path)
        self.add_btn.setEnabled(ready)
        self.hint.setText("Clique para jogar ou baixar. Botão direito para save e remover.")
        if error:
            show_error(self, "ROMs", error)
            self._refresh_list()
            return
        self._refresh_list()
        if rom is not None and ask_yes_no(self, "ROM pronta", f'Jogar "{rom.name}" agora?'):
            self._play_rom(rom)
