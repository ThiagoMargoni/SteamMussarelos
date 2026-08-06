from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from src.core.settings import Settings
from src.ui.dialogs import ask_yes_no
from src.ui.theme import COLORS, btn_style, font_body, font_body_bold, font_button, font_caption, font_heading


def _section_title(text: str) -> QLabel:
    label = QLabel(text)
    label.setFont(font_body_bold())
    label.setStyleSheet(f"color: {COLORS['text']}; background: transparent;")
    return label


def _hint(text: str) -> QLabel:
    label = QLabel(text)
    label.setFont(font_caption())
    label.setStyleSheet(f"color: {COLORS['text_muted']}; background: transparent;")
    label.setWordWrap(True)
    return label


class SettingsDialog(QDialog):
    def __init__(self, parent: QWidget, settings: Settings, on_apply) -> None:
        super().__init__(parent)
        self.settings = settings
        self.on_apply = on_apply
        self._folder_busy = False

        self.setWindowTitle("Configurações")
        self.setModal(True)
        self.setFixedSize(520, 440)
        self.setStyleSheet(f"background-color: {COLORS['bg_dark']};")
        if parent is not None and not parent.windowIcon().isNull():
            self.setWindowIcon(parent.windowIcon())

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 20)
        root.setSpacing(0)

        heading = QLabel("Configurações")
        heading.setFont(font_heading())
        heading.setStyleSheet(f"color: {COLORS['accent']}; background: transparent;")
        root.addWidget(heading)
        root.addSpacing(18)

        root.addWidget(_section_title("Pasta dos jogos"))
        root.addSpacing(6)
        root.addWidget(_hint("Onde os jogos são instalados e procurados neste PC."))
        root.addSpacing(10)

        folder_row = QHBoxLayout()
        folder_row.setSpacing(10)
        self.folder_label = QLabel()
        self.folder_label.setFont(font_body())
        self.folder_label.setStyleSheet(
            f"color: {COLORS['text_dim']}; background-color: {COLORS['bg_panel']};"
            f"border: 1px solid {COLORS['border']}; border-radius: 8px; padding: 8px 12px;"
        )
        self.folder_label.setWordWrap(False)
        folder_row.addWidget(self.folder_label, 1)

        self.folder_btn = QPushButton("Alterar")
        self.folder_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.folder_btn.setFixedSize(100, 36)
        self.folder_btn.setFont(font_button())
        self.folder_btn.setStyleSheet(
            btn_style(COLORS["bg_card"], COLORS["bg_card_hover"], COLORS["text"])
        )
        self.folder_btn.clicked.connect(self._change_folder)
        folder_row.addWidget(self.folder_btn)
        root.addLayout(folder_row)
        root.addSpacing(22)

        root.addWidget(_section_title("Velocidade do scroll"))
        root.addSpacing(6)
        root.addWidget(_hint("Controla o quanto a lista rola com a roda do mouse."))
        root.addSpacing(10)

        speed_row = QHBoxLayout()
        speed_row.setSpacing(12)
        slow = QLabel("Lenta")
        slow.setFont(font_caption())
        slow.setStyleSheet(f"color: {COLORS['text_muted']}; background: transparent;")
        speed_row.addWidget(slow)

        self.speed_slider = QSlider(Qt.Orientation.Horizontal)
        self.speed_slider.setRange(50, 300)
        self.speed_slider.setSingleStep(25)
        self.speed_slider.setPageStep(50)
        self.speed_slider.setFixedHeight(24)
        self.speed_slider.setValue(int(round(self.settings.scroll_speed * 100)))
        self.speed_slider.setStyleSheet(
            f"""
            QSlider::groove:horizontal {{
                height: 6px;
                background: {COLORS['border']};
                border-radius: 3px;
            }}
            QSlider::handle:horizontal {{
                width: 16px;
                height: 16px;
                margin: -5px 0;
                background: {COLORS['accent']};
                border-radius: 8px;
            }}
            QSlider::handle:horizontal:hover {{
                background: {COLORS['accent_hover']};
            }}
            """
        )
        self.speed_slider.valueChanged.connect(self._on_speed_changed)
        speed_row.addWidget(self.speed_slider, 1)

        fast = QLabel("Rápida")
        fast.setFont(font_caption())
        fast.setStyleSheet(f"color: {COLORS['text_muted']}; background: transparent;")
        speed_row.addWidget(fast)

        self.speed_value = QLabel()
        self.speed_value.setFont(font_body_bold())
        self.speed_value.setFixedWidth(48)
        self.speed_value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.speed_value.setStyleSheet(f"color: {COLORS['accent']}; background: transparent;")
        speed_row.addWidget(self.speed_value)
        root.addLayout(speed_row)
        root.addSpacing(22)

        root.addWidget(_section_title("Fechar o launcher"))
        root.addSpacing(6)
        root.addWidget(
            _hint("Se ativado, fechar a janela envia o app para a bandeja do sistema.")
        )
        root.addSpacing(10)

        self.tray_check = QCheckBox("Manter em segundo plano ao fechar")
        self.tray_check.setFont(font_body())
        self.tray_check.setChecked(self.settings.close_to_tray)
        self.tray_check.setCursor(Qt.CursorShape.PointingHandCursor)
        self.tray_check.setStyleSheet(
            f"""
            QCheckBox {{
                color: {COLORS['text']};
                spacing: 10px;
                background: transparent;
            }}
            QCheckBox::indicator {{
                width: 18px;
                height: 18px;
                border-radius: 4px;
                border: 1px solid {COLORS['border_light']};
                background: {COLORS['bg_panel']};
            }}
            QCheckBox::indicator:checked {{
                background: {COLORS['accent']};
                border: 1px solid {COLORS['accent']};
            }}
            """
        )
        root.addWidget(self.tray_check)
        root.addStretch(1)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        close_btn = QPushButton("Fechar")
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setFixedSize(120, 36)
        close_btn.setFont(font_button())
        close_btn.setStyleSheet(
            btn_style(COLORS["bg_card"], COLORS["bg_card_hover"], COLORS["text"])
        )
        close_btn.clicked.connect(self._save_and_close)
        buttons.addWidget(close_btn)
        buttons.addStretch(1)
        root.addLayout(buttons)

        self._refresh_folder_label()
        self._on_speed_changed(self.speed_slider.value())

    def _refresh_folder_label(self) -> None:
        folder = self.settings.games_folder or "Nenhuma pasta selecionada"
        self.folder_label.setText(self._shorten(folder, 48))
        self.folder_label.setToolTip(folder)

    @staticmethod
    def _shorten(path: str, max_len: int) -> str:
        if len(path) <= max_len:
            return path
        parts = Path(path).parts
        if len(parts) <= 2:
            return path[: max_len - 3] + "..."
        return str(Path(parts[0]) / "..." / Path(*parts[-2:]))

    def _on_speed_changed(self, value: int) -> None:
        speed = value / 100.0
        self.speed_value.setText(f"{speed:.2f}x".replace(".", ","))
        self.on_apply(folder_change=None, scroll_speed=speed, close_to_tray=None)

    def _change_folder(self) -> None:
        if self._folder_busy:
            return
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

        self._folder_busy = True
        self.folder_btn.setEnabled(False)
        self.folder_btn.setText("...")
        self.on_apply(folder_change=folder, scroll_speed=None, close_to_tray=None)

    def notify_folder_done(self) -> None:
        self._folder_busy = False
        self.folder_btn.setEnabled(True)
        self.folder_btn.setText("Alterar")
        self._refresh_folder_label()

    def _save_and_close(self) -> None:
        speed = self.speed_slider.value() / 100.0
        tray = self.tray_check.isChecked()
        self.on_apply(folder_change=None, scroll_speed=speed, close_to_tray=tray)
        self.accept()

    def closeEvent(self, event) -> None:
        if not self._folder_busy:
            speed = self.speed_slider.value() / 100.0
            tray = self.tray_check.isChecked()
            self.on_apply(folder_change=None, scroll_speed=speed, close_to_tray=tray)
        super().closeEvent(event)
