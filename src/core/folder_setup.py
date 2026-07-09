from __future__ import annotations

from pathlib import Path

from src.core.defender import DefenderService
from src.core.settings import Settings

def apply_games_folder(settings: Settings, folder: str) -> tuple[bool, str]:
    path = Path(folder).resolve()
    path.mkdir(parents=True, exist_ok=True)

    ok, msg = DefenderService.add_exclusion(str(path))
    settings.set_games_folder(str(path))
    settings.first_run_complete = True

    status = f"Pasta configurada:\n{path}\n\n{msg}"
    if not ok:
        status += "\n\nExecute como administrador para adicionar exclusão no Defender."
    return ok, status
