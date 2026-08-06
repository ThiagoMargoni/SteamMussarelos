from __future__ import annotations

from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from src.models.game import DownloadState, Game
from src.ui.progress_bar import RoundProgressBar
from src.ui.scroll_frame import PillScrollBar
from src.ui.speed_scroll import SpeedScrollArea
from src.ui.theme import (
    COLORS,
    DOWNLOAD_PANEL_HEIGHT,
    font_body_bold,
    font_caption,
    font_heading,
    font_small,
)


class _DownloadRow(QFrame):
    def __init__(self, parent, game_name: str) -> None:
        super().__init__(parent)
        self.game_name = game_name
        self.setObjectName("downloadRow")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
        self.setAutoFillBackground(False)
        self._fill = QColor(COLORS["bg_card"])
        self._edge = QColor(COLORS["border"])
        self._radius = 8.0

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        self.name_label = QLabel(game_name)
        self.name_label.setFont(font_body_bold())
        self.name_label.setStyleSheet(f"color: {COLORS['text']}; background: transparent;")
        top.addWidget(self.name_label, 1)
        self.pct_label = QLabel("0%")
        self.pct_label.setFont(font_body_bold())
        self.pct_label.setFixedWidth(52)
        self.pct_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.pct_label.setStyleSheet(f"color: {COLORS['accent']}; background: transparent;")
        top.addWidget(self.pct_label)
        layout.addLayout(top)

        self.progress = RoundProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        layout.addWidget(self.progress)

        bottom = QHBoxLayout()
        bottom.setContentsMargins(0, 0, 0, 0)
        self.state_label = QLabel("Aguardando...")
        self.state_label.setFont(font_caption())
        self.state_label.setStyleSheet(f"color: {COLORS['text_dim']}; background: transparent;")
        bottom.addWidget(self.state_label, 1)
        self.detail_label = QLabel()
        self.detail_label.setFont(font_small())
        self.detail_label.setStyleSheet(f"color: {COLORS['text_muted']}; background: transparent;")
        bottom.addWidget(self.detail_label)
        layout.addLayout(bottom)

        self._chunk(COLORS["accent"])

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        path = QPainterPath()
        path.addRoundedRect(
            QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5),
            self._radius,
            self._radius,
        )
        painter.setPen(Qt.PenStyle.NoPen)
        painter.fillPath(path, self._fill)
        pen = QPen(self._edge, 1.0)
        pen.setCosmetic(True)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)

    def update_game(self, game: Game) -> None:
        progress = max(0, min(100, int(game.download_progress)))
        self.progress.setValue(progress)
        self.pct_label.setText(f"{progress}%")

        if game.download_state == DownloadState.ERROR:
            self.state_label.setText(game.download_error or "Erro")
            self.state_label.setStyleSheet(f"color: {COLORS['danger']}; background: transparent;")
            self._chunk(COLORS["danger"])
        elif game.download_state == DownloadState.FINISHED:
            self.state_label.setText("Finalizado")
            self.state_label.setStyleSheet(f"color: {COLORS['success']}; background: transparent;")
            self.progress.setValue(100)
            self.pct_label.setText("100%")
            self._chunk(COLORS["success"])
        elif game.download_state == DownloadState.EXTRACTING:
            self.state_label.setText("Extraindo arquivos...")
            self.state_label.setStyleSheet(f"color: {COLORS['warning']}; background: transparent;")
            self._chunk(COLORS["warning"])
        else:
            self.state_label.setText("Baixando...")
            self.state_label.setStyleSheet(f"color: {COLORS['accent']}; background: transparent;")
            self._chunk(COLORS["accent"])

        parts = [p for p in (game.download_speed, game.download_size) if p]
        self.detail_label.setText("  ·  ".join(parts))

    def _chunk(self, color: str) -> None:
        self.progress.setChunkColor(color)


class DownloadPanel(QFrame):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("downloadPanel")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedHeight(DOWNLOAD_PANEL_HEIGHT)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 10, 14, 10)
        root.setSpacing(4)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        title = QLabel("Downloads")
        title.setFont(font_heading())
        title.setStyleSheet(f"color: {COLORS['text']}; background: transparent;")
        header.addWidget(title)
        self.count_label = QLabel()
        self.count_label.setFont(font_small())
        self.count_label.setStyleSheet(f"color: {COLORS['text_muted']}; background: transparent;")
        header.addWidget(self.count_label, 0, Qt.AlignmentFlag.AlignRight)
        root.addLayout(header)

        self.body = QWidget()
        self.body.setStyleSheet("background: transparent;")
        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(0, 0, 0, 0)
        self.body_layout.setSpacing(0)

        self.empty_label = QLabel("Nenhum download em andamento")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setFont(font_caption())
        self.empty_label.setStyleSheet(f"color: {COLORS['text_muted']}; background: transparent;")
        self.body_layout.addWidget(self.empty_label)

        self.single_host = QWidget()
        self.single_host.setStyleSheet("background: transparent;")
        self.single_layout = QVBoxLayout(self.single_host)
        self.single_layout.setContentsMargins(0, 0, 0, 0)
        self.single_host.hide()
        self.body_layout.addWidget(self.single_host)

        self.multi_scroll = SpeedScrollArea()
        self.multi_scroll.setObjectName("downloadScroll")
        self.multi_scroll.setWidgetResizable(True)
        self.multi_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.multi_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.multi_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.multi_scroll.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.multi_scroll.setStyleSheet(
            "QScrollArea#downloadScroll { border: none; background: transparent; }"
        )
        self.multi_scroll.setVerticalScrollBar(PillScrollBar(self.multi_scroll))

        self.multi_inner = QWidget()
        self.multi_inner.setObjectName("downloadScrollInner")
        self.multi_inner.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.multi_inner.setStyleSheet(
            "QWidget#downloadScrollInner { background: transparent; border: none; }"
        )
        self.multi_layout = QVBoxLayout(self.multi_inner)
        self.multi_layout.setContentsMargins(0, 0, 4, 0)
        self.multi_layout.setSpacing(8)
        self.multi_layout.addStretch(1)
        self.multi_scroll.setWidget(self.multi_inner)

        viewport = self.multi_scroll.viewport()
        if viewport is not None:
            viewport.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
            viewport.setAutoFillBackground(False)
            viewport.setStyleSheet("background: transparent; border: none;")

        self.multi_scroll.hide()
        self.body_layout.addWidget(self.multi_scroll)

        root.addWidget(self.body, 1)

        self._rows: dict[str, _DownloadRow] = {}
        self._game_refs: dict[str, Game] = {}
        self._pending_remove: dict[str, QTimer] = {}
        self._layout_mode = "empty"

    def update_game(self, game: Game) -> None:
        state = game.download_state
        if state == DownloadState.IDLE:
            if game.name in self._game_refs:
                self._schedule_remove(game.name)
            return

        if game.name in self._pending_remove:
            self._pending_remove[game.name].stop()
            del self._pending_remove[game.name]

        prev = len(self._game_refs)
        self._game_refs[game.name] = game
        mode = self._mode_for_count(len(self._game_refs))
        if prev != len(self._game_refs) or self._layout_mode != mode:
            self._rebuild_rows()
        else:
            row = self._rows.get(game.name)
            if row:
                row.update_game(game)

        if state == DownloadState.FINISHED:
            self._schedule_remove(game.name, 4000)
        elif state == DownloadState.ERROR:
            self._schedule_remove(game.name, 8000)

    def _mode_for_count(self, count: int) -> str:
        if count == 0:
            return "empty"
        if count == 1:
            return "single"
        return "multi"

    def _clear_layout(self, layout: QVBoxLayout, keep_stretch: bool = False) -> None:
        stretch = None
        if keep_stretch and layout.count():
            last = layout.itemAt(layout.count() - 1)
            if last is not None and last.spacerItem() is not None:
                stretch = layout.takeAt(layout.count() - 1)

        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()

        if stretch is not None:
            layout.addItem(stretch)
        elif keep_stretch:
            layout.addStretch(1)

    def _rebuild_rows(self) -> None:
        self._rows.clear()
        self._clear_layout(self.single_layout, keep_stretch=False)
        self._clear_layout(self.multi_layout, keep_stretch=True)

        count = len(self._game_refs)
        mode = self._mode_for_count(count)
        self._layout_mode = mode
        self.empty_label.setVisible(mode == "empty")
        self.single_host.setVisible(mode == "single")
        self.multi_scroll.setVisible(mode == "multi")

        if mode == "empty":
            self._update_count()
            return

        host = self.single_host if mode == "single" else self.multi_inner
        parent_layout = self.single_layout if mode == "single" else self.multi_layout
        for name, game in self._game_refs.items():
            row = _DownloadRow(host, name)
            row.update_game(game)
            if mode == "single":
                parent_layout.addWidget(row)
            else:
                parent_layout.insertWidget(parent_layout.count() - 1, row)
            self._rows[name] = row
        self._update_count()

    def _schedule_remove(self, name: str, delay_ms: int = 3000) -> None:
        if name in self._pending_remove:
            self._pending_remove[name].stop()

        timer = QTimer(self)
        timer.setSingleShot(True)

        def _remove() -> None:
            self._pending_remove.pop(name, None)
            self._game_refs.pop(name, None)
            self._rebuild_rows()

        timer.timeout.connect(_remove)
        self._pending_remove[name] = timer
        timer.start(delay_ms)

    def _update_count(self) -> None:
        n = len(self._game_refs)
        self.count_label.setText(f"{n} ativo{'s' if n != 1 else ''}" if n else "")

    def set_scroll_speed(self, speed: float) -> None:
        self.multi_scroll.set_scroll_speed(speed)
