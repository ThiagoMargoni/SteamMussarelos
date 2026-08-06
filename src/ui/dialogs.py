from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.ui.theme import COLORS, btn_style, font_body, font_button, font_heading


class SteamDialog(QDialog):
    """Popup no padrão visual do Steam dos Mussarelos (fundo escuro + botões do tema)."""

    def __init__(
        self,
        parent: QWidget | None,
        title: str,
        message: str,
        *,
        buttons: list[tuple[str, str]],
        default: str = "ok",
    ) -> None:
        super().__init__(parent)
        self._result = default
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(420)
        self.setMaximumWidth(520)
        self.setStyleSheet(f"background-color: {COLORS['bg_dark']};")
        if parent is not None and parent.windowIcon() and not parent.windowIcon().isNull():
            self.setWindowIcon(parent.windowIcon())

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 20)
        root.setSpacing(0)

        heading = QLabel(title)
        heading.setFont(font_heading())
        heading.setStyleSheet(f"color: {COLORS['accent']}; background: transparent;")
        heading.setWordWrap(True)
        root.addWidget(heading)
        root.addSpacing(12)

        body = QLabel(message)
        body.setFont(font_body())
        body.setStyleSheet(f"color: {COLORS['text']}; background: transparent;")
        body.setWordWrap(True)
        body.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        root.addWidget(body)
        root.addSpacing(22)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(10)
        row.addStretch(1)

        primary = {"sim", "ok", "continuar"}
        for key, label in buttons:
            btn = QPushButton(label)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedHeight(36)
            btn.setMinimumWidth(100)
            btn.setFont(font_button())
            if key.lower() in primary or (len(buttons) == 1 and key == default):
                btn.setStyleSheet(
                    btn_style(COLORS["accent"], COLORS["accent_hover"], COLORS["bg_medium"])
                )
            else:
                btn.setStyleSheet(
                    btn_style(COLORS["bg_card"], COLORS["bg_card_hover"], COLORS["text"])
                )
            btn.clicked.connect(lambda _=False, k=key: self._choose(k))
            row.addWidget(btn)

        row.addStretch(1)
        root.addLayout(row)

    def _choose(self, key: str) -> None:
        self._result = key
        if key.lower() in {"sim", "ok", "continuar"}:
            self.accept()
        else:
            self.reject()

    @property
    def result_key(self) -> str:
        return self._result


def show_info(parent: QWidget | None, title: str, message: str) -> None:
    SteamDialog(parent, title, message, buttons=[("ok", "OK")]).exec()


def show_warning(parent: QWidget | None, title: str, message: str) -> None:
    SteamDialog(parent, title, message, buttons=[("ok", "OK")]).exec()


def show_error(parent: QWidget | None, title: str, message: str) -> None:
    SteamDialog(parent, title, message, buttons=[("ok", "OK")]).exec()


def ask_yes_no(parent: QWidget | None, title: str, message: str) -> bool:
    dlg = SteamDialog(
        parent,
        title,
        message,
        buttons=[("nao", "Não"), ("sim", "Sim")],
        default="nao",
    )
    dlg.exec()
    return dlg.result_key.lower() == "sim"
