from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any, Optional

APP_NAME = "SteamMussarelos"
LAUNCHER_VERSION = "2.0.1"
LAYOUT_LIST = "list"
LAYOUT_COVERS = "covers"

REMOTE_CATALOG_URL = "https://raw.githubusercontent.com/ThiagoMargoni/SteamMussarelos/master/data/games.json"

def app_data_dir() -> Path:
    if _appdata_redirected():
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    else:
        base = (
            os.environ.get("APPDATA")
            or os.environ.get("LOCALAPPDATA")
            or str(Path.home())
        )
    path = Path(base) / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    _migrate_config_from_roaming(path)
    return path

def _appdata_redirected() -> bool:
    appdata = os.environ.get("APPDATA")
    if not appdata:
        return False
    probe = Path(appdata) / APP_NAME / "config.json"
    try:
        resolved = str(probe.resolve()).replace("/", "\\").lower()
    except OSError:
        return False
    return "\\packages\\" in resolved or "\\localcache\\" in resolved

def _migrate_config_from_roaming(dest_dir: Path) -> None:
    dest = dest_dir / "config.json"
    try:
        if dest.exists() and dest.stat().st_size > 2:
            return
    except OSError:
        return
    user = os.environ.get("USERPROFILE")
    if not user:
        return
    src = str(Path(user) / "AppData" / "Roaming" / APP_NAME / "config.json")
    try:
        raw = subprocess.check_output(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                f"if (Test-Path -LiteralPath '{src}') {{ "
                f"Get-Content -LiteralPath '{src}' -Raw -Encoding UTF8 }}",
            ],
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.SubprocessError):
        return
    text = (raw or "").strip()
    if not text.startswith("{"):
        return
    try:
        json.loads(text)
    except json.JSONDecodeError:
        return
    try:
        dest.write_text(text + "\n", encoding="utf-8")
    except OSError:
        return

class Settings:
    def __init__(self) -> None:
        self._path = app_data_dir() / "config.json"
        self._data: dict[str, Any] = self._load()
        if self._data.get("launcher_version") != LAUNCHER_VERSION:
            self._data["launcher_version"] = LAUNCHER_VERSION
            self.save()

    def _default_data(self) -> dict[str, Any]:
        return {
            "games_folder": None,
            "launcher_version": LAUNCHER_VERSION,
            "installed_games": {},
            "first_run_complete": False,
            "scroll_speed": 1.0,
            "close_to_tray": False,
            "library_layout": LAYOUT_LIST,
        }

    def _load(self) -> dict[str, Any]:
        if not self._path.exists():
            return self._default_data()
        try:
            raw = self._path.read_text(encoding="utf-8-sig").strip()
            if not raw:
                return self._default_data()
            data = json.loads(raw)
            if not isinstance(data, dict):
                return self._default_data()
            return data
        except (OSError, UnicodeError, json.JSONDecodeError):
            try:
                size = self._path.stat().st_size
            except OSError:
                size = 0
            if size > 0:
                backup = self._path.with_suffix(".json.bak")
                try:
                    if not backup.exists():
                        self._path.replace(backup)
                except OSError:
                    pass
            return self._default_data()

    def save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".json.tmp")
        payload = json.dumps(self._data, indent=2, ensure_ascii=False)
        with open(tmp, "w", encoding="utf-8", newline="\n") as f:
            f.write(payload)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, self._path)

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
        old_folder = self._data.get("games_folder")
        self._data["games_folder"] = folder
        for name, info in self.installed_games.items():
            old_path = info.get("path")
            relocated = False
            if old_folder and old_path:
                try:
                    rel = Path(old_path).resolve().relative_to(Path(old_folder).resolve())
                    info["path"] = str(Path(folder) / rel)
                    relocated = True
                except ValueError:
                    relocated = False
            if not relocated:
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
        existing = self.installed_games.get(name, {})
        entry = {
            "version": version,
            "path": path,
            "executable": executable,
        }
        mods = existing.get("mods")
        if isinstance(mods, list):
            entry["mods"] = mods
        self.installed_games[name] = entry
        self.save()

    def get_game_mods(self, name: str) -> list[dict[str, str]]:
        info = self.installed_games.get(name) or {}
        raw = info.get("mods")
        if not isinstance(raw, list):
            return []
        result: list[dict[str, str]] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            filename = str(item.get("filename") or "").strip()
            if not filename:
                continue
            mod_name = str(item.get("name") or Path(filename).stem).strip() or Path(filename).stem
            result.append({"name": mod_name, "filename": filename})
        return result

    def set_game_mods(self, name: str, mods: list[dict[str, str]]) -> None:
        info = self.installed_games.setdefault(name, {})
        cleaned: list[dict[str, str]] = []
        for item in mods:
            filename = str(item.get("filename") or "").strip()
            if not filename:
                continue
            mod_name = str(item.get("name") or Path(filename).stem).strip() or Path(filename).stem
            cleaned.append({"name": mod_name, "filename": filename})
        info["mods"] = cleaned
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

    @property
    def library_layout(self) -> str:
        value = str(self._data.get("library_layout", LAYOUT_LIST))
        if value not in (LAYOUT_LIST, LAYOUT_COVERS):
            return LAYOUT_LIST
        return value

    @library_layout.setter
    def library_layout(self, value: str) -> None:
        layout = value if value in (LAYOUT_LIST, LAYOUT_COVERS) else LAYOUT_LIST
        self._data["library_layout"] = layout
        self.save()
