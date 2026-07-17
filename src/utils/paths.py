from __future__ import annotations

import sys
from pathlib import Path

def project_root() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parents[2]

def exe_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return project_root()

def resource_path(*parts: str | Path) -> Path:
    flat: list[str] = []
    for part in parts:
        flat.extend(Path(part).parts)
    return project_root().joinpath(*flat)

def resolve_resource(*parts: str | Path) -> Path | None:
    flat: list[str] = []
    for part in parts:
        flat.extend(Path(part).parts)

    candidates = [
        project_root().joinpath(*flat),
        exe_dir().joinpath(*flat),
    ]
    seen: set[Path] = set()
    for path in candidates:
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        if path.exists():
            return path
    return None
