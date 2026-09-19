from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, QSize, Qt
from PySide6.QtWidgets import QLayout, QLayoutItem, QWidget

class FlowLayout(QLayout):
    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        margin_left: int = 12,
        margin_top: int = 12,
        margin_right: int = 12,
        margin_bottom: int = 12,
        hspacing: int = 12,
        vspacing: int = 12,
    ) -> None:
        super().__init__(parent)
        self._items: list[QLayoutItem] = []
        self._hspace = hspacing
        self._vspace = vspacing
        self._last_width = 0
        self.setContentsMargins(margin_left, margin_top, margin_right, margin_bottom)

    def addItem(self, item: QLayoutItem) -> None:
        self._items.append(item)

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index: int) -> QLayoutItem | None:
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index: int) -> QLayoutItem | None:
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def expandingDirections(self) -> Qt.Orientation:
        return Qt.Orientation(0)

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        return self._do_layout(QRect(0, 0, width, 0), True)

    def setGeometry(self, rect: QRect) -> None:
        super().setGeometry(rect)
        self._last_width = rect.width()
        self._do_layout(rect, False)

    def sizeHint(self) -> QSize:
        width = self._last_width
        if width <= 0 and self.parentWidget() is not None:
            width = self.parentWidget().width()
        if width > 0:
            return QSize(width, self.heightForWidth(width))
        return self.minimumSize()

    def minimumSize(self) -> QSize:
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        m = self.contentsMargins()
        size += QSize(m.left() + m.right(), m.top() + m.bottom())
        return size

    def invalidate(self) -> None:
        self._last_width = 0
        super().invalidate()

    def _do_layout(self, rect: QRect, test_only: bool) -> int:
        m = self.contentsMargins()
        effective = rect.adjusted(m.left(), m.top(), -m.right(), -m.bottom())
        if effective.width() <= 0:
            return m.top() + m.bottom()

        space_x = self._hspace
        space_y = self._vspace
        x = effective.x()
        y = effective.y()
        line_height = 0
        row_items: list[tuple[QLayoutItem, QSize]] = []

        def flush_row() -> None:
            nonlocal x, y, line_height, row_items
            if not row_items:
                return
            row_width = sum(s.width() for _, s in row_items) + space_x * (len(row_items) - 1)
            start_x = effective.x() + max(0, (effective.width() - row_width) // 2)
            if not test_only:
                cx = start_x
                for item, size in row_items:
                    item.setGeometry(QRect(QPoint(cx, y), size))
                    cx += size.width() + space_x
            y += line_height + space_y
            x = effective.x()
            line_height = 0
            row_items = []

        for item in self._items:
            hint = item.sizeHint()
            next_x = x + hint.width() + space_x
            if row_items and next_x - space_x > effective.right() + 1:
                flush_row()
            row_items.append((item, hint))
            x += hint.width() + space_x
            line_height = max(line_height, hint.height())

        flush_row()
        if y > effective.y():
            y -= space_y
        return y - rect.y() + m.bottom()
