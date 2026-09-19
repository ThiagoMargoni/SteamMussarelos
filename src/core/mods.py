from __future__ import annotations

import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from src.core.settings import Settings
from src.models.game import Game

@dataclass(frozen=True)
class ModInfo:
    name: str
    filename: str

def mods_dir_for(game: Game) -> Optional[Path]:
    if not game.supports_mods or not game.mods_folder:
        return None
    if not game.install_path:
        return None
    root = Path(game.install_path)
    folder = Path(game.mods_folder)
    if folder.is_absolute():
        return folder
    return (root / folder).resolve()

def list_mods(game: Game, settings: Settings) -> list[ModInfo]:
    saved = settings.get_game_mods(game.name)
    mods_dir = mods_dir_for(game)
    catalog_names = {
        str(item.get("filename") or "").lower(): str(item.get("name") or "").strip()
        for item in (game.included_mods or [])
        if item.get("filename")
    }

    by_file: dict[str, dict[str, str]] = {}

    for item in game.included_mods or []:
        filename = str(item.get("filename") or "").strip()
        if not filename:
            continue
        name = str(item.get("name") or Path(filename).stem).strip() or Path(filename).stem
        if mods_dir is not None and not (mods_dir / filename).is_file():
            continue
        by_file[filename.lower()] = {"name": name, "filename": filename}

    for item in saved:
        filename = item["filename"]
        name = item["name"]
        if mods_dir is not None and not (mods_dir / filename).is_file():
            continue
        key = filename.lower()
        if key in catalog_names and catalog_names[key]:
            name = catalog_names[key]
        by_file[key] = {"name": name, "filename": filename}

    if mods_dir is not None and mods_dir.is_dir():
        for path in sorted(mods_dir.iterdir(), key=lambda p: p.name.lower()):
            if not path.is_file():
                continue
            key = path.name.lower()
            if key in by_file:
                continue
            name = catalog_names.get(key) or path.stem
            by_file[key] = {"name": name, "filename": path.name}

    kept = list(by_file.values())
    kept.sort(key=lambda m: m["name"].casefold())
    if kept != saved:
        settings.set_game_mods(game.name, kept)
    return [ModInfo(name=m["name"], filename=m["filename"]) for m in kept]

def add_mod(
    game: Game,
    settings: Settings,
    source_path: Path,
    display_name: Optional[str] = None,
) -> ModInfo:
    if not game.supports_mods:
        raise ValueError("Este jogo não tem suporte a mods.")
    if not game.install_path:
        raise ValueError("Instale o jogo antes de adicionar mods.")
    source = Path(source_path)
    if not source.is_file():
        raise ValueError("Arquivo de mod inválido.")

    mods_dir = mods_dir_for(game)
    if mods_dir is None:
        raise ValueError("Pasta de mods não configurada.")
    mods_dir.mkdir(parents=True, exist_ok=True)

    filename = source.name
    dest = mods_dir / filename
    if dest.resolve() != source.resolve():
        shutil.copy2(source, dest)

    name = (display_name or source.stem).strip() or source.stem
    mods = settings.get_game_mods(game.name)
    mods = [m for m in mods if m["filename"].lower() != filename.lower()]
    mods.append({"name": name, "filename": filename})
    settings.set_game_mods(game.name, mods)
    return ModInfo(name=name, filename=filename)

def remove_mod(game: Game, settings: Settings, filename: str) -> None:
    mods_dir = mods_dir_for(game)
    if mods_dir is not None:
        path = mods_dir / filename
        if path.is_file():
            path.unlink()
    mods = [m for m in settings.get_game_mods(game.name) if m["filename"] != filename]
    settings.set_game_mods(game.name, mods)

def backup_mods(game: Game) -> Optional[Path]:
    mods_dir = mods_dir_for(game)
    if mods_dir is None or not mods_dir.exists():
        return None
    if not any(mods_dir.iterdir()):
        return None
    staging = Path(tempfile.mkdtemp(prefix="steam_mods_backup_"))
    dest = staging / "mods"
    shutil.copytree(mods_dir, dest)
    return dest

def restore_mods(game: Game, backup: Optional[Path]) -> None:
    if backup is None or not backup.exists():
        return
    staging = backup.parent if backup.name == "mods" else None
    try:
        mods_dir = mods_dir_for(game)
        if mods_dir is None:
            return
        if mods_dir.exists():
            shutil.rmtree(mods_dir, ignore_errors=True)
        mods_dir.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(backup, mods_dir)
    finally:
        cleanup = staging if staging is not None else backup
        if cleanup.exists():
            shutil.rmtree(cleanup, ignore_errors=True)
