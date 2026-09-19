from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from src.core.mods import add_mod, list_mods, remove_mod
from src.core.settings import Settings
from src.models.game import Game, GameStatus
from src.ui.dialogs import ask_yes_no, show_error
from src.ui.theme import COLORS, btn_style, font_body, font_body_bold, font_button, font_caption, font_heading

class ModsDialog(QDialog):
    def __init__(self, parent: QWidget, game: Game, settings: Settings) -> None:
        super().__init__(parent)
        self.game = game
        self.settings = settings

        self.setObjectName("modsDialog")
        self.setWindowTitle(f"Mods - {game.name}")
        self.setModal(True)
        self.setFixedSize(480, 420)
        self.setStyleSheet(
            f"QDialog#modsDialog {{ background-color: {COLORS['bg_dark']}; }}"
        )
        if parent is not None and not parent.windowIcon().isNull():
            self.setWindowIcon(parent.windowIcon())

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 20)
        root.setSpacing(0)

        heading = QLabel(f"Mods - {game.name}", self)
        heading.setFont(font_heading())
        heading.setStyleSheet(f"color: {COLORS['accent']}; background: transparent;")
        root.addWidget(heading)
        root.addSpacing(6)

        hint = QLabel(
            f"Arquivos em {game.mods_folder or 'Mods'}. "
            "Eles são mantidos quando o jogo é atualizado.",
            self,
        )
        hint.setFont(font_caption())
        hint.setWordWrap(True)
        hint.setStyleSheet(f"color: {COLORS['text_muted']}; background: transparent;")
        root.addWidget(hint)
        root.addSpacing(14)

        self.list_host = QWidget(self)
        self.list_host.setStyleSheet("background: transparent;")
        self.list_layout = QVBoxLayout(self.list_host)
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        self.list_layout.setSpacing(8)
        self.list_layout.addStretch(1)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setStyleSheet(
            f"QScrollArea {{ background: {COLORS['bg_panel']}; border: 1px solid {COLORS['border']};"
            f" border-radius: 8px; }}"
        )
        scroll.setWidget(self.list_host)
        root.addWidget(scroll, 1)
        root.addSpacing(14)

        buttons = QHBoxLayout()
        buttons.setSpacing(10)

        self.add_btn = QPushButton("Adicionar mod", self)
        self.add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_btn.setFixedHeight(36)
        self.add_btn.setFont(font_button())
        self.add_btn.setStyleSheet(
            btn_style(COLORS["accent"], COLORS["accent_hover"], COLORS["bg_medium"])
        )
        self.add_btn.clicked.connect(self._add_mod)
        buttons.addWidget(self.add_btn)

        close_btn = QPushButton("Fechar", self)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setFixedSize(120, 36)
        close_btn.setFont(font_button())
        close_btn.setStyleSheet(
            btn_style(COLORS["bg_card"], COLORS["bg_card_hover"], COLORS["text"])
        )
        close_btn.clicked.connect(self.accept)
        buttons.addWidget(close_btn)
        root.addLayout(buttons)

        installed = game.status in (
            GameStatus.INSTALLED,
            GameStatus.UPDATE_AVAILABLE,
            GameStatus.RUNNING,
        ) and bool(game.install_path)
        self.add_btn.setEnabled(installed)
        if not installed:
            hint.setText("Instale o jogo para gerenciar mods nesta pasta.")

        self._refresh_list()

    def _clear_list(self) -> None:
        while self.list_layout.count():
            item = self.list_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _refresh_list(self) -> None:
        self._clear_list()
        mods = list_mods(self.game, self.settings)
        if not mods:
            empty = QLabel("Nenhum mod adicionado.", self.list_host)
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setFont(font_body())
            empty.setStyleSheet(
                f"color: {COLORS['text_muted']}; background: transparent; padding: 28px;"
            )
            self.list_layout.addWidget(empty)
            self.list_layout.addStretch(1)
            return

        for mod in mods:
            row = QWidget(self.list_host)
            row.setObjectName("modRow")
            row.setStyleSheet(
                f"QWidget#modRow {{ background-color: {COLORS['bg_card']};"
                f" border: 1px solid {COLORS['border']}; border-radius: 8px; }}"
                f" QWidget#modRow QLabel {{ background: transparent; border: none; }}"
            )
            layout = QHBoxLayout(row)
            layout.setContentsMargins(12, 10, 12, 10)
            layout.setSpacing(10)

            texts = QVBoxLayout()
            texts.setContentsMargins(0, 0, 0, 0)
            texts.setSpacing(2)
            name = QLabel(mod.name, row)
            name.setFont(font_body_bold())
            name.setStyleSheet(
                f"color: {COLORS['text']}; background: transparent; border: none;"
            )
            texts.addWidget(name)
            filename = QLabel(mod.filename, row)
            filename.setFont(font_caption())
            filename.setStyleSheet(
                f"color: {COLORS['text_dim']}; background: transparent; border: none;"
            )
            texts.addWidget(filename)
            layout.addLayout(texts, 1)

            remove_btn = QPushButton("Remover", row)
            remove_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            remove_btn.setFixedSize(90, 32)
            remove_btn.setFont(font_button())
            remove_btn.setStyleSheet(
                btn_style(COLORS["danger"], COLORS["danger_hover"], "#ffffff")
            )
            remove_btn.clicked.connect(
                lambda _=False, fn=mod.filename, nm=mod.name: self._remove_mod(fn, nm)
            )
            layout.addWidget(remove_btn)
            self.list_layout.addWidget(row)

        self.list_layout.addStretch(1)

    def _add_mod(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Selecionar arquivo de mod",
            "",
            "Mods (*.dll *.zip *.pak *.rar *.7z);;Todos os arquivos (*.*)",
        )
        if not path:
            return
        try:
            add_mod(self.game, self.settings, Path(path))
        except Exception as exc:
            show_error(self, "Mods", str(exc))
            return
        self._refresh_list()

    def _remove_mod(self, filename: str, name: str) -> None:
        if not ask_yes_no(self, "Remover mod", f'Remover "{name}"?\n\n{filename}'):
            return
        try:
            remove_mod(self.game, self.settings, filename)
        except Exception as exc:
            show_error(self, "Mods", str(exc))
            return
        self._refresh_list()
