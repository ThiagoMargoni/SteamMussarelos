from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Optional

APP_NAME = "SteamMussarelos"
LAUNCHER_VERSION = "1.6.7"

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
        if self._data.get("launcher_version") != LAUNCHER_VERSION:
            self._data["launcher_version"] = LAUNCHER_VERSION
            self.save()

    def _load(self) -> dict[str, Any]:
        if self._path.exists():
            with open(self._path, encoding="utf-8") as f:
                return json.load(f)
        return {
            "games_folder": None,
            "launcher_version": LAUNCHER_VERSION,
            "installed_games": {},
            "first_run_complete": False,
            "scroll_speed": 1.0,
            "close_to_tray": False,
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
        return LAUNCHER_VERSION

    @launcher_version.setter
    def launcher_version(self, value: str) -> None:
        self._data["launcher_version"] = value
        self.save()

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

    @property
    def scroll_speed(self) -> float:
        try:
            value = float(self._data.get("scroll_speed", 1.0))
        except (TypeError, ValueError):
            value = 1.0
        return max(0.5, min(3.0, value))

    @scroll_speed.setter
    def scroll_speed(self, value: float) -> None:
        self._data["scroll_speed"] = max(0.5, min(3.0, float(value)))
        self.save()

    @property
    def close_to_tray(self) -> bool:
        return bool(self._data.get("close_to_tray", False))

    @close_to_tray.setter
    def close_to_tray(self, value: bool) -> None:
        self._data["close_to_tray"] = bool(value)
        self.save()
