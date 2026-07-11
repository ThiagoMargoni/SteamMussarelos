from __future__ import annotations

import sys
from pathlib import Path

def project_root() -> Path:
    """Raiz do projeto em desenvolvimento, ou pasta temporária do PyInstaller."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parents[2]

def resource_path(*parts: str) -> Path:
    """Caminho para um recurso empacotado (icons/, data/, etc.)."""
    return project_root().joinpath(*parts)
