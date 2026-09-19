from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
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

from src.core.settings import LAYOUT_COVERS, LAYOUT_LIST, Settings
from src.ui.dialogs import ask_yes_no
from src.ui.theme import (
    COLORS,
    btn_style,
    font_body,
    font_body_bold,
    font_button,
    font_caption,
    font_heading,
)

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

class LayoutPreviewCard(QWidget):
    clicked = Signal(str)

    def __init__(self, layout_value: str, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.layout_value = layout_value
        self._title = title
        self._checked = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(220, 148)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
        self.setStyleSheet("background: transparent; border: none;")

    def isChecked(self) -> bool:
        return self._checked

    def setChecked(self, checked: bool) -> None:
        if self._checked == checked:
            return
        self._checked = checked
        self.update()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.layout_value)
        super().mousePressEvent(event)

    def keyPressEvent(self, event) -> None:
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.clicked.emit(self.layout_value)
            return
        super().keyPressEvent(event)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        border = QColor(COLORS["accent"] if self._checked else COLORS["border"])
        fill = QColor(COLORS["bg_panel"])
        if self._checked:
            fill = QColor(COLORS["bg_card"])

        body = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        painter.setPen(QPen(border, 2 if self._checked else 1))
        painter.setBrush(fill)
        painter.drawRoundedRect(body, 10, 10)

        preview = QRectF(12, 12, self.width() - 24, 88)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(COLORS["bg_medium"]))
        painter.drawRoundedRect(preview, 8, 8)

        if self.layout_value == LAYOUT_COVERS:
            self._paint_covers_preview(painter, preview)
        else:
            self._paint_list_preview(painter, preview)

        painter.setPen(QColor(COLORS["text"] if self._checked else COLORS["text_dim"]))
        painter.setFont(font_body_bold())
        painter.drawText(
            QRectF(12, 108, self.width() - 24, 28),
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter,
            self._title,
        )

    def _paint_list_preview(self, painter: QPainter, area: QRectF) -> None:
        rows = 3
        gap = 6
        pad = 8
        row_h = (area.height() - pad * 2 - gap * (rows - 1)) / rows
        for i in range(rows):
            y = area.top() + pad + i * (row_h + gap)
            row = QRectF(area.left() + pad, y, area.width() - pad * 2, row_h)
            painter.setBrush(QColor(COLORS["bg_card"]))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(row, 5, 5)

            icon = QRectF(row.left() + 5, row.top() + 4, row_h - 8, row_h - 8)
            painter.setBrush(QColor(COLORS["accent"] if i == 0 else COLORS["border_light"]))
            painter.drawRoundedRect(icon, 3, 3)

            line1 = QRectF(icon.right() + 6, row.top() + 5, row.width() * 0.42, 5)
            line2 = QRectF(icon.right() + 6, row.top() + row_h * 0.55, row.width() * 0.28, 4)
            painter.setBrush(QColor(COLORS["text"]))
            painter.drawRoundedRect(line1, 2, 2)
            painter.setBrush(QColor(COLORS["text_muted"]))
            painter.drawRoundedRect(line2, 2, 2)

            btn = QRectF(row.right() - 34, row.center().y() - 7, 28, 14)
            painter.setBrush(QColor(COLORS["success"] if i == 0 else COLORS["accent"]))
            painter.drawRoundedRect(btn, 4, 4)

    def _paint_covers_preview(self, painter: QPainter, area: QRectF) -> None:
        cols, rows = 3, 2
        gap = 6
        pad = 8
        cell_w = (area.width() - pad * 2 - gap * (cols - 1)) / cols
        cell_h = (area.height() - pad * 2 - gap * (rows - 1)) / rows
        colors = [
            COLORS["accent"],
            COLORS["success"],
            COLORS["warning"],
            COLORS["border_light"],
            COLORS["danger"],
            COLORS["bg_card_hover"],
        ]
        idx = 0
        for r in range(rows):
            for c in range(cols):
                x = area.left() + pad + c * (cell_w + gap)
                y = area.top() + pad + r * (cell_h + gap)
                card = QRectF(x, y, cell_w, cell_h)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor(colors[idx % len(colors)]))
                painter.drawRoundedRect(card, 4, 4)
                if idx == 1:
                    painter.setBrush(QColor(0, 0, 0, 140))
                    painter.drawRoundedRect(
                        QRectF(card.left(), card.bottom() - 10, card.width(), 10), 0, 0
                    )
                idx += 1

class SettingsDialog(QDialog):
    def __init__(self, parent: QWidget, settings: Settings, on_apply) -> None:
        super().__init__(parent)
        self.settings = settings
        self.on_apply = on_apply
        self._folder_busy = False
        self._selected_layout_value = (
            LAYOUT_COVERS
            if self.settings.library_layout == LAYOUT_COVERS
            else LAYOUT_LIST
        )

        self.setObjectName("settingsDialog")
        self.setWindowTitle("Configurações")
        self.setModal(True)
        self.setFixedSize(520, 720)
        self.setStyleSheet(
            f"QDialog#settingsDialog {{ background-color: {COLORS['bg_dark']}; }}"
        )
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
        root.addSpacing(20)

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
        self.speed_value.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        self.speed_value.setStyleSheet(f"color: {COLORS['accent']}; background: transparent;")
        speed_row.addWidget(self.speed_value)
        root.addLayout(speed_row)
        root.addSpacing(20)

        root.addWidget(_section_title("Layout da biblioteca"))
        root.addSpacing(6)
        root.addWidget(
            _hint(
                "Escolha como os jogos aparecem. No modo imagens, o nome aparece no "
                "hover e o botão direito abre as ações."
            )
        )
        root.addSpacing(10)

        layout_row = QHBoxLayout()
        layout_row.setSpacing(12)
        self.list_preview = LayoutPreviewCard(LAYOUT_LIST, "Lista", self)
        self.covers_preview = LayoutPreviewCard(LAYOUT_COVERS, "Imagens", self)
        self.list_preview.clicked.connect(self._select_layout)
        self.covers_preview.clicked.connect(self._select_layout)
        layout_row.addWidget(self.list_preview)
        layout_row.addWidget(self.covers_preview)
        layout_row.addStretch(1)
        root.addLayout(layout_row)
        self._refresh_layout_cards()
        root.addSpacing(20)

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
        self.on_apply(
            folder_change=None,
            scroll_speed=speed,
            close_to_tray=None,
            library_layout=None,
        )

    def _selected_layout(self) -> str:
        return self._selected_layout_value

    def _refresh_layout_cards(self) -> None:
        self.list_preview.setChecked(self._selected_layout_value == LAYOUT_LIST)
        self.covers_preview.setChecked(self._selected_layout_value == LAYOUT_COVERS)

    def _select_layout(self, value: str) -> None:
        if value not in (LAYOUT_LIST, LAYOUT_COVERS):
            return
        if value == self._selected_layout_value:
            return
        self._selected_layout_value = value
        self._refresh_layout_cards()
        self.on_apply(
            folder_change=None,
            scroll_speed=None,
            close_to_tray=None,
            library_layout=value,
        )

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
        self.on_apply(
            folder_change=folder,
            scroll_speed=None,
            close_to_tray=None,
            library_layout=None,
        )

    def notify_folder_done(self) -> None:
        self._folder_busy = False
        self.folder_btn.setEnabled(True)
        self.folder_btn.setText("Alterar")
        self._refresh_folder_label()

    def _save_and_close(self) -> None:
        speed = self.speed_slider.value() / 100.0
        tray = self.tray_check.isChecked()
        self.on_apply(
            folder_change=None,
            scroll_speed=speed,
            close_to_tray=tray,
            library_layout=self._selected_layout(),
        )
        self.accept()

    def closeEvent(self, event) -> None:
        if not self._folder_busy:
            speed = self.speed_slider.value() / 100.0
            tray = self.tray_check.isChecked()
            self.on_apply(
                folder_change=None,
                scroll_speed=speed,
                close_to_tray=tray,
                library_layout=self._selected_layout(),
            )
        super().closeEvent(event)
