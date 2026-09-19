from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from src.core.emulators import (
    MGBA_BIND_ORDER,
    MGBA_DEFAULT_BINDS,
    load_mgba_settings,
    save_mgba_settings,
)
from src.models.game import Game
from src.ui.dialogs import show_error, show_info
from src.ui.theme import COLORS, btn_style, font_body, font_body_bold, font_button, font_caption, font_heading

def _checkbox_style() -> str:
    return f"""
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

def _panel() -> QFrame:
    frame = QFrame()
    frame.setObjectName("settingsPanel")
    frame.setStyleSheet(
        f"QFrame#settingsPanel {{ background-color: {COLORS['bg_panel']};"
        f" border: 1px solid {COLORS['border']}; border-radius: 10px; }}"
    )
    return frame

class _KeyBindButton(QPushButton):
    def __init__(self, parent: QWidget, key_code: int) -> None:
        super().__init__(parent)
        self.key_code = int(key_code)
        self._listening = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(30)
        self.setMinimumWidth(96)
        self.setFont(font_button())
        self._refresh_style()
        self._refresh_label()
        self.clicked.connect(self._start_listen)

    def _refresh_style(self) -> None:
        if self._listening:
            self.setStyleSheet(
                btn_style(COLORS["accent"], COLORS["accent_hover"], COLORS["bg_medium"])
            )
        else:
            self.setStyleSheet(
                btn_style(COLORS["bg_card"], COLORS["bg_card_hover"], COLORS["text"])
            )

    def _refresh_label(self) -> None:
        if self._listening:
            self.setText("Tecla...")
            return
        seq = QKeySequence(self.key_code)
        text = seq.toString(QKeySequence.SequenceFormat.NativeText)
        self.setText(text or f"Key {self.key_code}")

    def _start_listen(self) -> None:
        self._listening = True
        self._refresh_style()
        self._refresh_label()
        self.setFocus(Qt.FocusReason.ShortcutFocusReason)
        self.grabKeyboard()

    def keyPressEvent(self, event) -> None:
        if not self._listening:
            super().keyPressEvent(event)
            return
        key = event.key()
        if key in (Qt.Key.Key_Escape, Qt.Key.Key_unknown):
            self._stop_listen()
            return
        if key in (
            Qt.Key.Key_Control,
            Qt.Key.Key_Shift,
            Qt.Key.Key_Alt,
            Qt.Key.Key_Meta,
        ):
            return
        self.key_code = int(key)
        self._stop_listen()

    def focusOutEvent(self, event) -> None:
        if self._listening:
            self._stop_listen()
        super().focusOutEvent(event)

    def _stop_listen(self) -> None:
        self._listening = False
        self.releaseKeyboard()
        self._refresh_style()
        self._refresh_label()

class EmulatorSettingsDialog(QDialog):
    def __init__(self, parent: QWidget, emulator: Game) -> None:
        super().__init__(parent)
        self.emulator = emulator
        self.setObjectName("emulatorSettingsDialog")
        self.setWindowTitle(f"Configurar — {emulator.name}")
        self.setModal(True)
        self.setFixedSize(620, 430)
        self.setStyleSheet(
            f"QDialog#emulatorSettingsDialog {{ background-color: {COLORS['bg_dark']}; }}"
        )
        if parent is not None and not parent.windowIcon().isNull():
            self.setWindowIcon(parent.windowIcon())

        try:
            data = load_mgba_settings(emulator)
        except Exception as exc:
            show_error(parent, "Configurar", str(exc))
            self._failed = True
            return
        self._failed = False

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 18, 22, 16)
        root.setSpacing(0)

        heading = QLabel(f"Configurar — {emulator.name}", self)
        heading.setFont(font_heading())
        heading.setStyleSheet(f"color: {COLORS['accent']}; background: transparent;")
        root.addWidget(heading)
        root.addSpacing(4)

        hint = QLabel(
            "Controles e opções salvos no emulador. Não precisa abrir o mGBA.",
            self,
        )
        hint.setFont(font_caption())
        hint.setWordWrap(True)
        hint.setStyleSheet(f"color: {COLORS['text_muted']}; background: transparent;")
        root.addWidget(hint)
        root.addSpacing(14)

        columns = QHBoxLayout()
        columns.setSpacing(16)

        left = QVBoxLayout()
        left.setSpacing(0)
        binds_title = QLabel("Controles", self)
        binds_title.setFont(font_body_bold())
        binds_title.setStyleSheet(f"color: {COLORS['text']}; background: transparent;")
        left.addWidget(binds_title)
        left.addSpacing(8)

        binds_panel = _panel()
        binds_layout = QGridLayout(binds_panel)
        binds_layout.setContentsMargins(12, 10, 12, 10)
        binds_layout.setHorizontalSpacing(10)
        binds_layout.setVerticalSpacing(8)
        self._bind_btns: dict[str, _KeyBindButton] = {}
        binds = data.get("binds") or dict(MGBA_DEFAULT_BINDS)
        half = (len(MGBA_BIND_ORDER) + 1) // 2
        for idx, (key, label) in enumerate(MGBA_BIND_ORDER):
            col = 0 if idx < half else 2
            row = idx if idx < half else idx - half
            name = QLabel(label, binds_panel)
            name.setFont(font_body())
            name.setStyleSheet(f"color: {COLORS['text_dim']}; background: transparent;")
            btn = _KeyBindButton(binds_panel, int(binds.get(key, MGBA_DEFAULT_BINDS[key])))
            self._bind_btns[key] = btn
            binds_layout.addWidget(name, row, col)
            binds_layout.addWidget(btn, row, col + 1)
        left.addWidget(binds_panel, 1)
        columns.addLayout(left, 3)

        right = QVBoxLayout()
        right.setSpacing(0)
        opts_title = QLabel("Opções", self)
        opts_title.setFont(font_body_bold())
        opts_title.setStyleSheet(f"color: {COLORS['text']}; background: transparent;")
        right.addWidget(opts_title)
        right.addSpacing(8)

        opts_panel = _panel()
        opts_layout = QVBoxLayout(opts_panel)
        opts_layout.setContentsMargins(14, 12, 14, 14)
        opts_layout.setSpacing(10)

        check_style = _checkbox_style()
        self.fullscreen = QCheckBox("Tela cheia", opts_panel)
        self.fullscreen.setFont(font_body())
        self.fullscreen.setCursor(Qt.CursorShape.PointingHandCursor)
        self.fullscreen.setChecked(bool(data.get("fullscreen")))
        self.fullscreen.setStyleSheet(check_style)
        opts_layout.addWidget(self.fullscreen)

        self.mute = QCheckBox("Sem som", opts_panel)
        self.mute.setFont(font_body())
        self.mute.setCursor(Qt.CursorShape.PointingHandCursor)
        self.mute.setChecked(bool(data.get("mute")))
        self.mute.setStyleSheet(check_style)
        opts_layout.addWidget(self.mute)

        self.lock_aspect = QCheckBox("Travar proporção", opts_panel)
        self.lock_aspect.setFont(font_body())
        self.lock_aspect.setCursor(Qt.CursorShape.PointingHandCursor)
        self.lock_aspect.setChecked(bool(data.get("lock_aspect", True)))
        self.lock_aspect.setStyleSheet(check_style)
        opts_layout.addWidget(self.lock_aspect)

        divider = QFrame(opts_panel)
        divider.setFixedHeight(1)
        divider.setStyleSheet(f"background-color: {COLORS['border']}; border: none;")
        opts_layout.addSpacing(4)
        opts_layout.addWidget(divider)
        opts_layout.addSpacing(4)

        vol_label = QLabel("Volume", opts_panel)
        vol_label.setFont(font_caption())
        vol_label.setStyleSheet(f"color: {COLORS['text_muted']}; background: transparent;")
        opts_layout.addWidget(vol_label)

        vol_row = QHBoxLayout()
        vol_row.setSpacing(10)
        self.volume = QSlider(Qt.Orientation.Horizontal, opts_panel)
        self.volume.setRange(0, 100)
        self.volume.setValue(int(data.get("volume_pct", 100)))
        self.volume.setFixedHeight(22)
        self.volume.setStyleSheet(
            f"""
            QSlider::groove:horizontal {{
                height: 6px; background: {COLORS['border']}; border-radius: 3px;
            }}
            QSlider::handle:horizontal {{
                width: 14px; height: 14px; margin: -4px 0;
                background: {COLORS['accent']}; border-radius: 7px;
            }}
            QSlider::handle:horizontal:hover {{
                background: {COLORS['accent_hover']};
            }}
            """
        )
        vol_row.addWidget(self.volume, 1)
        self.volume_value = QLabel(f"{self.volume.value()}%", opts_panel)
        self.volume_value.setFixedWidth(40)
        self.volume_value.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        self.volume_value.setFont(font_body_bold())
        self.volume_value.setStyleSheet(f"color: {COLORS['accent']}; background: transparent;")
        self.volume.valueChanged.connect(lambda v: self.volume_value.setText(f"{v}%"))
        vol_row.addWidget(self.volume_value)
        opts_layout.addLayout(vol_row)
        opts_layout.addStretch(1)
        right.addWidget(opts_panel, 1)
        columns.addLayout(right, 2)

        root.addLayout(columns, 1)
        root.addSpacing(14)

        buttons = QHBoxLayout()
        buttons.setSpacing(10)
        reset_btn = QPushButton("Restaurar padrões", self)
        reset_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        reset_btn.setFixedHeight(34)
        reset_btn.setFont(font_button())
        reset_btn.setStyleSheet(
            btn_style(COLORS["bg_card"], COLORS["bg_card_hover"], COLORS["text"])
        )
        reset_btn.clicked.connect(self._reset_defaults)
        buttons.addWidget(reset_btn)
        buttons.addStretch(1)

        save_btn = QPushButton("Salvar", self)
        save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_btn.setFixedSize(100, 34)
        save_btn.setFont(font_button())
        save_btn.setStyleSheet(
            btn_style(COLORS["accent"], COLORS["accent_hover"], COLORS["bg_medium"])
        )
        save_btn.clicked.connect(self._save)
        buttons.addWidget(save_btn)

        close_btn = QPushButton("Fechar", self)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setFixedSize(100, 34)
        close_btn.setFont(font_button())
        close_btn.setStyleSheet(
            btn_style(COLORS["bg_card"], COLORS["bg_card_hover"], COLORS["text"])
        )
        close_btn.clicked.connect(self.reject)
        buttons.addWidget(close_btn)
        root.addLayout(buttons)

    def exec(self) -> int:
        if getattr(self, "_failed", False):
            return 0
        return super().exec()

    def _reset_defaults(self) -> None:
        for key, btn in self._bind_btns.items():
            btn.key_code = int(MGBA_DEFAULT_BINDS[key])
            btn._refresh_label()
        self.fullscreen.setChecked(False)
        self.mute.setChecked(False)
        self.lock_aspect.setChecked(True)
        self.volume.setValue(100)

    def _save(self) -> None:
        binds = {key: btn.key_code for key, btn in self._bind_btns.items()}
        try:
            path = save_mgba_settings(
                self.emulator,
                binds=binds,
                fullscreen=self.fullscreen.isChecked(),
                mute=self.mute.isChecked(),
                lock_aspect=self.lock_aspect.isChecked(),
                volume_pct=self.volume.value(),
            )
        except Exception as exc:
            show_error(self, "Configurar", str(exc))
            return
        show_info(self, "Configurar", f"Configurações salvas.\n\n{path}")
        self.accept()
