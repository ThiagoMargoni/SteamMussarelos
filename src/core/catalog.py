from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Optional

import requests
from packaging import version

from src.core.debug_mode import use_local_assets
from src.core.install_state import is_installed_at, sync_game_with_disk
from src.core.settings import LAUNCHER_VERSION, REMOTE_CATALOG_URL, Settings
from src.models.game import Catalog, Game, LauncherInfo
from src.utils.paths import resolve_resource, resource_path
from src.utils.remote_assets import resolve_icon_url

def _parse_included_mods(mods_block: dict) -> list[dict[str, str]]:
    raw = mods_block.get("included")
    if raw is None:
        raw = mods_block.get("installed")
    if not isinstance(raw, list):
        return []
    result: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in raw:
        if not isinstance(item, dict):
            continue
        filename = str(item.get("filename") or "").strip()
        if not filename:
            continue
        key = filename.lower()
        if key in seen:
            continue
        seen.add(key)
        name = str(item.get("name") or Path(filename).stem).strip() or Path(filename).stem
        result.append({"name": name, "filename": filename})
    return result

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

        if use_local_assets():
            local_path = resolve_resource("data", "games.json") or resource_path("data", "games.json")
            if not local_path or not Path(local_path).exists():
                raise RuntimeError("Modo local: data/games.json não encontrado.")
            with open(local_path, encoding="utf-8") as f:
                data = json.load(f)
        else:
            try:
                resp = requests.get(self.catalog_url, timeout=15)
                resp.raise_for_status()
                data = resp.json()
            except Exception as exc:
                errors.append(str(exc))
                if local_fallback:
                    local_path = resolve_resource("data", "games.json") or resource_path("data", "games.json")
                    if local_path and Path(local_path).exists():
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
            raw_icon = entry.get("icon")
            if use_local_assets():
                icon = raw_icon
            else:
                icon = resolve_icon_url(raw_icon, self.catalog_url)
            mods = entry.get("mods") or {}
            folder = mods.get("folderPath") if isinstance(mods, dict) else None
            mods_folder = str(folder).strip().replace("\\", "/") if folder else None
            included_mods = _parse_included_mods(mods if isinstance(mods, dict) else {})
            games.append(
                Game(
                    name=entry["name"],
                    version=entry["version"],
                    download=entry["download"],
                    icon=icon,
                    executable=entry.get("executable"),
                    mods_folder=mods_folder or None,
                    included_mods=included_mods,
                )
            )

        emulators = []
        for entry in data.get("emulators", []):
            raw_icon = entry.get("icon")
            if use_local_assets():
                icon = raw_icon
            else:
                icon = resolve_icon_url(raw_icon, self.catalog_url)
            platform_id = str(entry.get("id") or "gba").strip().lower()
            emu_name = str(entry.get("emulatorName") or entry.get("name") or "mGBA").strip()
            exts_raw = entry.get("extensions") or [".gba"]
            extensions = []
            if isinstance(exts_raw, list):
                for item in exts_raw:
                    text = str(item).strip().lower()
                    if not text:
                        continue
                    if not text.startswith("."):
                        text = f".{text}"
                    extensions.append(text)
            if not extensions:
                extensions = [".gba"]
            install_subdir = str(entry.get("installSubdir") or f"Emulators/{emu_name}").strip()
            catalog_roms: list[dict[str, str]] = []
            raw_roms = entry.get("roms")
            if isinstance(raw_roms, list):
                for item in raw_roms:
                    if not isinstance(item, dict):
                        continue
                    filename = str(item.get("filename") or "").strip()
                    if not filename:
                        continue
                    catalog_roms.append(
                        {
                            "name": str(item.get("name") or Path(filename).stem).strip()
                            or Path(filename).stem,
                            "filename": filename,
                            "download": str(item.get("download") or "").strip(),
                            "icon": str(item.get("icon") or "").strip(),
                        }
                    )
            emulators.append(
                Game(
                    name=emu_name,
                    version=str(entry.get("version") or "1.0.0"),
                    download=str(entry.get("download") or ""),
                    icon=icon,
                    executable=entry.get("executable") or "mGBA.exe",
                    kind="emulator",
                    platform_id=platform_id,
                    platform_name=str(entry.get("name") or "Game Boy Advance"),
                    rom_extensions=extensions,
                    install_subdir=install_subdir,
                    catalog_roms=catalog_roms,
                )
            )

        return Catalog(launcher=launcher, games=games, emulators=emulators)

    def _merge_local_state(self, catalog: Catalog) -> None:
        from src.core.emulators import sync_emulator_with_disk

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

        for emu in catalog.emulators:
            sync_emulator_with_disk(emu, self.settings)

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

            detected_version = self._detect_version(entry)
            exe = game.executable or self._find_executable(entry)
            game.executable = exe
            game.install_path = str(entry)

            if detected_version is not None:
                game.installed_version = detected_version
            elif not game.installed_version:
                game.installed_version = "0.0.0"

            self.settings.set_installed_game(
                name,
                game.installed_version,
                str(entry),
                exe,
            )
            game.update_status()

    def _detect_version(self, game_dir: Path) -> Optional[str]:
        version_file = game_dir / "version.txt"
        if version_file.exists():
            try:
                text = version_file.read_text(encoding="utf-8").strip()
            except OSError:
                return None
            return text or None
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
        local = LAUNCHER_VERSION
        if not remote:
            return False

        try:
            return version.parse(remote) > version.parse(local)
        except Exception:
            return remote != local
