from __future__ import annotations

from PySide6.QtCore import QObject, Signal

class UiInvoke(QObject):
    _invoke = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self._invoke.connect(self._run)

    def _run(self, fn) -> None:
        try:
            fn()
        except Exception:
            pass

    def post(self, fn) -> None:
        self._invoke.emit(fn)

_bridge: UiInvoke | None = None

def ui_bridge() -> UiInvoke:
    global _bridge
    if _bridge is None:
        _bridge = UiInvoke()
    return _bridge

def ui_call(fn) -> None:
    ui_bridge().post(fn)
