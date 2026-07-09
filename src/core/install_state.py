from __future__ import annotations

from pathlib import Path

from src.core.settings import Settings
from src.models.game import Game

def _dir_has_content(path: Path) -> bool:
    try:
        return any(path.iterdir())
    except OSError:
        return False

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
    """
    Alinha o estado do jogo com o que existe no disco.
    Retorna True se o jogo está instalado após a sincronização.
    """
    games_folder = settings.games_folder
    folder_path = Path(games_folder) / game.name if games_folder else None

    if game.install_path and is_game_on_disk(game):
        return True

    if folder_path and is_installed_at(folder_path, game.executable):
        version_file = folder_path / "version.txt"
        detected = version_file.read_text(encoding="utf-8").strip() if version_file.exists() else None
        local = settings.get_installed_game(game.name)
        game.install_path = str(folder_path)
        game.installed_version = detected or (local.get("version") if local else game.version)
        settings.set_installed_game(
            game.name,
            game.installed_version,
            str(folder_path),
            game.executable,
        )
        game.update_status()
        return True

    if game.installed_version or game.install_path:
        clear_install_state(game, settings)

    game.update_status()
    return False
