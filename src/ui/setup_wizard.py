from __future__ import annotations

import threading

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from src.core.folder_setup import apply_games_folder
from src.core.settings import Settings
from src.ui.dialogs import show_warning
from src.ui.qt_bridge import ui_call
from src.ui.theme import COLORS, btn_style, font_body, font_button, font_caption, font_display, font_heading

class SetupWizard(QDialog):
    def __init__(self, parent, settings: Settings, on_complete) -> None:
        super().__init__(parent)
        self.settings = settings
        self.on_complete = on_complete
        self.setWindowTitle("Configuração Inicial")
        self.setFixedSize(600, 380)
        self.setModal(True)
        self.setWindowFlag(Qt.WindowType.WindowCloseButtonHint, False)
        self.setStyleSheet(f"background-color: {COLORS['bg_dark']};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 28, 28, 28)
        layout.setSpacing(0)

        welcome = QLabel("Bem-vindo")
        welcome.setFont(font_display())
        welcome.setStyleSheet(f"color: {COLORS['accent']}; background: transparent;")
        welcome.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(welcome)
        layout.addSpacing(4)

        brand = QLabel("Steam dos Mussarelos")
        brand.setFont(font_heading())
        brand.setStyleSheet(f"color: {COLORS['text']}; background: transparent;")
        brand.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(brand)
        layout.addSpacing(12)

        tip = QLabel("Escolha onde os jogos serão instalados no seu computador.")
        tip.setFont(font_body())
        tip.setStyleSheet(f"color: {COLORS['text_dim']}; background: transparent;")
        tip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(tip)
        layout.addSpacing(20)

        row = QHBoxLayout()
        row.setSpacing(10)
        self.folder_entry = QLineEdit()
        self.folder_entry.setPlaceholderText("C:\\Jogos")
        self.folder_entry.setFixedHeight(40)
        self.folder_entry.setFont(font_body())
        row.addWidget(self.folder_entry, 1)
        browse = QPushButton("Procurar")
        browse.setCursor(Qt.CursorShape.PointingHandCursor)
        browse.setFixedSize(100, 40)
        browse.setFont(font_button())
        browse.setStyleSheet(btn_style(COLORS["bg_card"], COLORS["bg_card_hover"], COLORS["text"]))
        browse.clicked.connect(self._browse)
        row.addWidget(browse)
        layout.addLayout(row)

        self.status_label = QLabel()
        self.status_label.setFont(font_caption())
        self.status_label.setStyleSheet(f"color: {COLORS['text_muted']}; background: transparent;")
        self.status_label.setWordWrap(True)
        layout.addSpacing(20)
        layout.addWidget(self.status_label)
        layout.addStretch(1)

        self.confirm_btn = QPushButton("Confirmar e continuar")
        self.confirm_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.confirm_btn.setFixedSize(240, 42)
        self.confirm_btn.setFont(font_button())
        self.confirm_btn.setStyleSheet(
            btn_style(COLORS["accent"], COLORS["accent_hover"], COLORS["bg_medium"])
        )
        self.confirm_btn.clicked.connect(self._confirm)
        layout.addWidget(self.confirm_btn, 0, Qt.AlignmentFlag.AlignCenter)
        layout.addSpacing(8)

    def reject(self) -> None:
        return

    def _browse(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Selecione a pasta dos jogos")
        if folder:
            self.folder_entry.setText(folder)

    def _confirm(self) -> None:
        folder = self.folder_entry.text().strip()
        if not folder:
            show_warning(self, "Atenção", "Selecione uma pasta válida.")
            return
        self.confirm_btn.setEnabled(False)
        self.status_label.setText("Configurando pasta e verificando antivírus...")

        def _setup() -> None:
            _, status = apply_games_folder(self.settings, folder)
            ui_call(lambda: self._finish(status))

        threading.Thread(target=_setup, daemon=True).start()

    def _finish(self, status: str) -> None:
        self.status_label.setText(status)
        from PySide6.QtCore import QTimer

        QTimer.singleShot(1400, self._close)

    def _close(self) -> None:
        self.accept()
        self.on_complete()
