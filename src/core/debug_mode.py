from __future__ import annotations

import sys
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any

_enabled = False
_log_path: Path | None = None
_project_log_path: Path | None = None

def set_local_assets(enabled: bool) -> None:
    global _enabled
    _enabled = bool(enabled)
    if _enabled:
        _ensure_log_file()
        log("info", "modo --local ativo")

def use_local_assets() -> bool:
    return _enabled

def logging_enabled() -> bool:
    return _enabled

def log_path() -> Path | None:
    return _log_path

def project_log_path() -> Path | None:
    return _project_log_path

def _ensure_log_file() -> Path | None:
    global _log_path, _project_log_path
    if _log_path is not None:
        return _log_path
    try:
        from src.core.settings import app_data_dir

        path = app_data_dir() / "debug-local.log"
        path.parent.mkdir(parents=True, exist_ok=True)
        _log_path = path
        try:
            root = Path(__file__).resolve().parents[2]
            _project_log_path = root / "debug-local.log"
        except Exception:
            _project_log_path = None
        header = (
            "\n" + "=" * 60 + "\n"
            f"session {datetime.now().isoformat(timespec='seconds')}\n"
            + "=" * 60 + "\n"
        )
        with open(path, "a", encoding="utf-8") as f:
            f.write(header)
        if _project_log_path is not None:
            try:
                with open(_project_log_path, "a", encoding="utf-8") as f:
                    f.write(header)
            except OSError:
                _project_log_path = None
        return path
    except Exception:
        _log_path = None
        return None

def log(level: str, message: str, **fields: Any) -> None:
    if not _enabled:
        return
    stamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    extra = ""
    if fields:
        parts = []
        for key, value in fields.items():
            parts.append(f"{key}={value!r}")
        extra = " | " + " ".join(parts)
    line = f"[{stamp}] {level.upper():5} {message}{extra}"
    try:
        print(line, flush=True)
    except Exception:
        pass
    path = _ensure_log_file()
    for target in (path, _project_log_path):
        if target is None:
            continue
        try:
            with open(target, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except OSError:
            pass

def log_exception(message: str, exc: BaseException | None = None) -> None:
    if not _enabled:
        return
    err = exc or sys.exc_info()[1]
    log("error", message, error=repr(err) if err is not None else None)
    tb = "".join(
        traceback.format_exception(
            type(err), err, err.__traceback__ if err is not None else None
        )
    ) if err is not None else traceback.format_exc()
    _write_raw(tb + "\n")
    try:
        print(tb, flush=True)
    except Exception:
        pass

def _write_raw(text: str) -> None:
    _ensure_log_file()
    for target in (_log_path, _project_log_path):
        if target is None:
            continue
        try:
            with open(target, "a", encoding="utf-8") as f:
                f.write(text)
        except OSError:
            pass

def install_excepthook() -> None:
    if not _enabled:
        return
    previous = sys.excepthook

    def _hook(exc_type, exc, tb) -> None:
        log("error", "excecao nao tratada", error=repr(exc))
        text = "".join(traceback.format_exception(exc_type, exc, tb))
        _write_raw(text + "\n")
        try:
            print(text, flush=True)
        except Exception:
            pass
        previous(exc_type, exc, tb)

    sys.excepthook = _hook
