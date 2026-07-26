from __future__ import annotations

from pathlib import Path

from src.core.settings import Settings
from src.models.game import Game

def _dir_has_content(path: Path) -> bool:
    try:
        return any(path.iterdir())
    except OSError:
        return False

def read_version_file(path: Path) -> str | None:
    version_file = path / "version.txt"
    if not version_file.exists():
        return None
    try:
        text = version_file.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return text or None

def is_installed_at(path: Path, executable: str | None = None) -> bool:
    if not path.is_dir() or not _dir_has_content(path):
        return False

    if executable and (path / executable).is_file():
        return True

    if (path / "version.txt").exists():
        return True

    return any(path.rglob("*.exe"))

def is_game_on_disk(game: Game) -> bool:
    if not game.install_path:
        return False
    return is_installed_at(Path(game.install_path), game.executable)

def clear_install_state(game: Game, settings: Settings) -> None:
    game.installed_version = None
    game.install_path = None
    game.pid = None
    settings.remove_installed_game(game.name)
    game.update_status(is_running=False)

def sync_game_with_disk(game: Game, settings: Settings) -> bool:
    games_folder = settings.games_folder
    folder_path = Path(games_folder) / game.name if games_folder else None

    path: Path | None = None
    if game.install_path and is_game_on_disk(game):
        path = Path(game.install_path)
    elif folder_path and is_installed_at(folder_path, game.executable):
        path = folder_path

    if path is not None:
        local = settings.get_installed_game(game.name)
        detected = read_version_file(path)
        game.install_path = str(path)
        if detected is not None:
            game.installed_version = detected
        elif local and local.get("version"):
            game.installed_version = local["version"]
        elif not game.installed_version:
            game.installed_version = "0.0.0"
        settings.set_installed_game(
            game.name,
            game.installed_version,
            str(path),
            game.executable,
        )
        game.update_status()
        return True

    if game.installed_version or game.install_path:
        clear_install_state(game, settings)

    game.update_status()
    return False
