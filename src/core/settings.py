from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Optional

APP_NAME = "SteamMussarelos"
LAUNCHER_VERSION = "1.0.0"

REMOTE_CATALOG_URL = "https://raw.githubusercontent.com/ThiagoMargoni/SteamMussarelos/master/data/games.json"

def _app_data_dir() -> Path:
    base = os.environ.get("APPDATA") or os.environ.get("LOCALAPPDATA") or str(Path.home())
    path = Path(base) / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path

class Settings:
    def __init__(self) -> None:
        self._path = _app_data_dir() / "config.json"
        self._data: dict[str, Any] = self._load()

    def _load(self) -> dict[str, Any]:
        if self._path.exists():
            with open(self._path, encoding="utf-8") as f:
                return json.load(f)
        return {
            "games_folder": None,
            "launcher_version": LAUNCHER_VERSION,
            "installed_games": {},
            "first_run_complete": False,
        }

    def save(self) -> None:
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2, ensure_ascii=False)

    @property
    def config_path(self) -> Path:
        return self._path

    @property
    def games_folder(self) -> Optional[str]:
        return self._data.get("games_folder")

    @games_folder.setter
    def games_folder(self, value: str) -> None:
        self._data["games_folder"] = value

    def set_games_folder(self, folder: str) -> None:
        folder = str(Path(folder).resolve())
        self._data["games_folder"] = folder
        for name, info in self.installed_games.items():
            info["path"] = str(Path(folder) / name)
            
        self.save()

    @property
    def launcher_version(self) -> str:
        return self._data.get("launcher_version", LAUNCHER_VERSION)

    @launcher_version.setter
    def launcher_version(self, value: str) -> None:
        self._data["launcher_version"] = value

    @property
    def first_run_complete(self) -> bool:
        return bool(self._data.get("first_run_complete"))

    @first_run_complete.setter
    def first_run_complete(self, value: bool) -> None:
        self._data["first_run_complete"] = value

    @property
    def installed_games(self) -> dict[str, dict[str, Any]]:
        return self._data.setdefault("installed_games", {})

    def set_installed_game(
        self,
        name: str,
        version: str,
        path: str,
        executable: Optional[str] = None,
    ) -> None:
        self.installed_games[name] = {
            "version": version,
            "path": path,
            "executable": executable,
        }
        self.save()

    def remove_installed_game(self, name: str) -> None:
        self.installed_games.pop(name, None)
        self.save()

    def get_installed_game(self, name: str) -> Optional[dict[str, Any]]:
        return self.installed_games.get(name)
