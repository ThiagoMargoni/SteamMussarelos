from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Optional

import requests
from packaging import version

from src.core.install_state import is_installed_at, sync_game_with_disk
from src.core.settings import REMOTE_CATALOG_URL, Settings
from src.models.game import Catalog, Game, LauncherInfo

class CatalogService:
    def __init__(self, settings: Settings, catalog_url: str = REMOTE_CATALOG_URL) -> None:
        self.settings = settings
        self.catalog_url = catalog_url
        self._catalog: Optional[Catalog] = None
        self._lock = threading.Lock()

    @property
    def catalog(self) -> Optional[Catalog]:
        return self._catalog

    def fetch(self, local_fallback: bool = True) -> Catalog:
        data = None
        errors: list[str] = []

        try:
            resp = requests.get(self.catalog_url, timeout=15)
            resp.raise_for_status()
            data = resp.json()

        except Exception as exc:
            errors.append(str(exc))

            if local_fallback:
                local_path = Path(__file__).resolve().parents[2] / "data" / "games.json"
                if local_path.exists():
                    with open(local_path, encoding="utf-8") as f:
                        data = json.load(f)

        if data is None:
            raise RuntimeError(
                "Não foi possível carregar o catálogo remoto."
                + (f" ({errors[0]})" if errors else "")
            )

        catalog = self._parse_catalog(data)
        self._merge_local_state(catalog)
        with self._lock:
            self._catalog = catalog

        return catalog

    def _parse_catalog(self, data: dict) -> Catalog:
        launcher_data = data.get("launcher", {})
        launcher = LauncherInfo(
            version=launcher_data.get("version", "1.0.0"),
            download=launcher_data.get("download"),
            latest_version=launcher_data.get("version"),
        )

        games = []
        for entry in data.get("games", []):
            games.append(
                Game(
                    name=entry["name"],
                    version=entry["version"],
                    download=entry["download"],
                    icon=entry.get("icon"),
                    executable=entry.get("executable"),
                )
            )

        return Catalog(launcher=launcher, games=games)

    def _merge_local_state(self, catalog: Catalog) -> None:
        for game in catalog.games:
            local = self.settings.get_installed_game(game.name)
            if local:
                game.installed_version = local.get("version")
                game.install_path = local.get("path")
                if not game.executable:
                    game.executable = local.get("executable")

            sync_game_with_disk(game, self.settings)

        self._scan_existing_installs(catalog)

        for game in catalog.games:
            game.update_status()

    def _scan_existing_installs(self, catalog: Catalog) -> None:
        folder = self.settings.games_folder
        if not folder or not os.path.isdir(folder):
            return

        catalog_by_name = {g.name: g for g in catalog.games}

        for entry in Path(folder).iterdir():
            if not entry.is_dir():
                continue

            name = entry.name
            if name not in catalog_by_name:
                continue

            game = catalog_by_name[name]
            if not is_installed_at(entry, game.executable):
                continue

            detected_version = self._detect_version(entry) or game.version

            if (
                not game.installed_version
                or version.parse(detected_version) > version.parse(game.installed_version)
            ):
                game.installed_version = detected_version
                game.install_path = str(entry)
                exe = game.executable or self._find_executable(entry)
                game.executable = exe
                self.settings.set_installed_game(
                    name, detected_version, str(entry), exe
                )

            game.update_status()

    def _detect_version(self, game_dir: Path) -> Optional[str]:
        version_file = game_dir / "version.txt"

        if version_file.exists():
            return version_file.read_text(encoding="utf-8").strip()
        
        return None

    def _find_executable(self, game_dir: Path) -> Optional[str]:
        exes = list(game_dir.glob("*.exe"))
        if exes:
            return exes[0].name
        
        for sub in game_dir.iterdir():
            if sub.is_dir():
                sub_exes = list(sub.glob("*.exe"))
                if sub_exes:
                    return str(sub_exes[0].relative_to(game_dir)).replace("\\", "/")
                
        return None

    def launcher_update_available(self) -> bool:
        if not self._catalog:
            return False
        
        remote = self._catalog.launcher.latest_version
        local = self.settings.launcher_version

        if not remote:
            return False
        
        try:
            return version.parse(remote) > version.parse(local)
        
        except Exception:
            return remote != local
