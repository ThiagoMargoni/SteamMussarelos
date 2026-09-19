from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import Callable, Optional

from src.core.debug_mode import log, log_exception
from src.core.archive import ensure_extractor_available, extract_archive
from src.core.downloader import download_file
from src.core.settings import Settings, app_data_dir
from src.models.game import Game, RomEntry

def emulator_install_dir(settings: Settings, emulator: Game) -> Optional[Path]:
    root = settings.games_folder
    if not root:
        return None
    rel = emulator.install_subdir or f"Emulators/{emulator.name}"
    return Path(root) / Path(rel)

def default_roms_dir(settings: Settings, platform_id: str) -> Optional[Path]:
    root = settings.games_folder
    if not root:
        return None
    return Path(root) / "ROMs" / platform_id.lower()

def roms_dir_for(settings: Settings, platform_id: str) -> Optional[Path]:
    return default_roms_dir(settings, platform_id)

def saves_dir_for(platform_id: str) -> Path:
    path = app_data_dir() / "saves" / platform_id.lower()
    path.mkdir(parents=True, exist_ok=True)
    return path

def ensure_roms_dir(settings: Settings, platform_id: str) -> Path:
    folder = roms_dir_for(settings, platform_id)
    if folder is None:
        raise ValueError("Configure a pasta de jogos antes de gerenciar ROMs.")
    folder.mkdir(parents=True, exist_ok=True)
    return folder

def _exts_for(emulator: Game) -> set[str]:
    exts = {
        e.lower() if e.startswith(".") else f".{e.lower()}"
        for e in (emulator.rom_extensions or [".gba"])
    }
    return exts or {".gba"}

def list_roms(settings: Settings, emulator: Game) -> list[RomEntry]:
    platform_id = emulator.platform_id or "gba"
    folder = roms_dir_for(settings, platform_id)
    exts = _exts_for(emulator)
    by_file: dict[str, RomEntry] = {}

    for item in emulator.catalog_roms or []:
        filename = str(item.get("filename") or "").strip()
        if not filename:
            continue
        name = str(item.get("name") or Path(filename).stem).strip() or Path(filename).stem
        download = str(item.get("download") or "").strip()
        icon = str(item.get("icon") or "").strip()
        if not icon:
            icon = f"icons/emulators/{platform_id}/{Path(filename).stem}.png"
        path = ""
        installed = False
        if folder is not None:
            candidate = folder / filename
            if candidate.is_file():
                path = str(candidate.resolve())
                installed = True
        by_file[filename.lower()] = RomEntry(
            name=name,
            platform_id=platform_id,
            filename=filename,
            path=path,
            download=download,
            icon=icon,
            installed=installed,
        )

    if folder is not None and folder.is_dir():
        for path in sorted(folder.iterdir(), key=lambda p: p.name.casefold()):
            if not path.is_file() or path.suffix.lower() not in exts:
                continue
            key = path.name.lower()
            if key in by_file:
                entry = by_file[key]
                by_file[key] = RomEntry(
                    name=entry.name,
                    platform_id=platform_id,
                    filename=path.name,
                    path=str(path.resolve()),
                    download=entry.download,
                    icon=entry.icon,
                    installed=True,
                )
            else:
                by_file[key] = RomEntry(
                    name=path.stem,
                    platform_id=platform_id,
                    filename=path.name,
                    path=str(path.resolve()),
                    download="",
                    icon=f"icons/emulators/{platform_id}/{path.stem}.png",
                    installed=True,
                )

    result = list(by_file.values())
    result.sort(key=lambda r: (not r.installed, r.name.casefold()))
    return result

def add_rom(settings: Settings, emulator: Game, source: Path) -> RomEntry:
    platform_id = emulator.platform_id or "gba"
    folder = ensure_roms_dir(settings, platform_id)
    src = Path(source)
    if not src.is_file():
        raise ValueError("Arquivo de ROM inválido.")
    if src.suffix.lower() not in _exts_for(emulator):
        raise ValueError(f"Extensão não suportada: {src.suffix}")
    dest = folder / src.name
    if dest.resolve() != src.resolve():
        shutil.copy2(src, dest)
    return RomEntry(
        name=dest.stem,
        platform_id=platform_id,
        filename=dest.name,
        path=str(dest.resolve()),
        icon=f"icons/emulators/{platform_id}/{dest.stem}.png",
        installed=True,
    )

def remove_rom(rom: RomEntry) -> None:
    if not rom.path:
        return
    path = Path(rom.path)
    if path.is_file():
        path.unlink()

def download_rom(
    settings: Settings,
    emulator: Game,
    rom: RomEntry,
    on_status: Optional[Callable[[str], None]] = None,
    cancel_check: Optional[Callable[[], bool]] = None,
) -> RomEntry:
    if not rom.download:
        raise ValueError("Esta ROM não tem link de download.")
    platform_id = emulator.platform_id or "gba"
    folder = ensure_roms_dir(settings, platform_id)
    dest = folder / rom.filename
    if dest.is_file():
        return RomEntry(
            name=rom.name,
            platform_id=platform_id,
            filename=rom.filename,
            path=str(dest.resolve()),
            download=rom.download,
            icon=rom.icon,
            installed=True,
        )

    tmp_dir = Path(tempfile.mkdtemp(prefix="steam_rom_"))
    try:
        ensure_extractor_available(rom.download)
        if on_status:
            on_status("Baixando...")
        archive = tmp_dir / "rom.bin"

        def _chunk(_downloaded: int, _total: int) -> None:
            if on_status:
                on_status("Baixando...")

        final = download_file(
            rom.download,
            archive,
            on_chunk=_chunk,
            cancel_check=cancel_check,
        )
        if cancel_check and cancel_check():
            raise RuntimeError("Download cancelado.")

        suffix = final.suffix.lower()
        if suffix in {".zip", ".rar", ".7z"}:
            if on_status:
                on_status("Extraindo...")
            extract_dir = tmp_dir / "out"
            extract_dir.mkdir(parents=True, exist_ok=True)
            extract_archive(final, extract_dir)
            matches = [
                p
                for p in extract_dir.rglob("*")
                if p.is_file() and p.suffix.lower() in _exts_for(emulator)
            ]
            if not matches:
                raise ValueError("Nenhuma ROM encontrada no arquivo baixado.")
            preferred = [p for p in matches if p.name.lower() == rom.filename.lower()]
            chosen = preferred[0] if preferred else matches[0]
            shutil.copy2(chosen, dest)
        else:
            shutil.copy2(final, dest)

        return RomEntry(
            name=rom.name,
            platform_id=platform_id,
            filename=dest.name,
            path=str(dest.resolve()),
            download=rom.download,
            icon=rom.icon or f"icons/emulators/{platform_id}/{Path(dest.name).stem}.png",
            installed=True,
        )
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

def _upsert_ini_keys(path: Path, section: str, updates: dict[str, str]) -> None:
    lines: list[str] = []
    if path.is_file():
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            lines = []

    section_header = f"[{section}]"
    section_start = -1
    for i, line in enumerate(lines):
        if line.strip() == section_header:
            section_start = i
            break

    if section_start < 0:
        if lines and lines[-1].strip():
            lines.append("")
        lines.append(section_header)
        for key, value in updates.items():
            lines.append(f"{key}={value}")
        lines.append("")
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return

    section_end = len(lines)
    for i in range(section_start + 1, len(lines)):
        stripped = lines[i].strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            section_end = i
            break

    pending = dict(updates)
    for i in range(section_start + 1, section_end):
        stripped = lines[i].strip()
        if not stripped or stripped.startswith("#") or stripped.startswith(";"):
            continue
        if "=" not in stripped:
            continue
        key = stripped.split("=", 1)[0].strip()
        if key in pending:
            lines[i] = f"{key}={pending.pop(key)}"

    insert_at = section_end
    while insert_at > section_start + 1 and not lines[insert_at - 1].strip():
        insert_at -= 1
    for key, value in pending.items():
        lines.insert(insert_at, f"{key}={value}")
        insert_at += 1
        section_end += 1

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

def mgba_dir(emulator: Game) -> Path:
    install = Path(emulator.install_path or "")
    if not install.is_dir():
        raise ValueError("Emulador não instalado.")
    exe_rel = emulator.executable or "mgba-qt.exe"
    exe_path = (install / exe_rel).resolve()
    if exe_path.is_file():
        root = exe_path.parent
        log("debug", "mgba_dir via executable", root=str(root), exe=str(exe_path))
        return root
    matches = list(install.rglob("mgba-qt.exe"))
    if matches:
        root = matches[0].resolve().parent
        log("debug", "mgba_dir via rglob", root=str(root), exe=str(matches[0]))
        return root
    log("debug", "mgba_dir fallback install", root=str(install.resolve()))
    return install.resolve()

def prepare_mgba_config(emulator: Game, platform_id: str) -> Path:
    root = mgba_dir(emulator)
    install = Path(emulator.install_path or "").resolve()
    saves = saves_dir_for(platform_id)
    states = saves / "states"
    states.mkdir(parents=True, exist_ok=True)
    if install.is_dir() and root != install:
        for name in ("config.ini", "portable.ini", "qt.ini"):
            src = install / name
            dest = root / name
            if src.is_file() and not dest.is_file():
                try:
                    shutil.copy2(src, dest)
                    log("info", "migrou config mgba", src=str(src), dest=str(dest))
                except OSError as exc:
                    log_exception("falha ao migrar config mgba", exc)
    portable = root / "portable.ini"
    if not portable.is_file():
        portable.write_text("", encoding="utf-8")
    qt_ini = root / "qt.ini"
    if not qt_ini.is_file():
        qt_ini.write_text("", encoding="utf-8")
    save_path = str(saves).replace("\\", "/")
    state_path = str(states).replace("\\", "/")
    config = root / "config.ini"
    _upsert_ini_keys(
        config,
        "ports.qt",
        {
            "savegamePath": save_path,
            "savestatePath": state_path,
        },
    )
    log(
        "info",
        "prepare_mgba_config",
        root=str(root),
        config=str(config),
        portable=portable.is_file(),
        saves=save_path,
    )
    return saves

MGBA_DEFAULT_BINDS: dict[str, int] = {
    "keyA": 88,
    "keyB": 90,
    "keyL": 65,
    "keyR": 83,
    "keyStart": 16777220,
    "keySelect": 16777219,
    "keyUp": 16777235,
    "keyDown": 16777237,
    "keyLeft": 16777234,
    "keyRight": 16777236,
}

MGBA_BIND_ORDER: list[tuple[str, str]] = [
    ("keyUp", "Cima"),
    ("keyDown", "Baixo"),
    ("keyLeft", "Esquerda"),
    ("keyRight", "Direita"),
    ("keyA", "A"),
    ("keyB", "B"),
    ("keyL", "L"),
    ("keyR", "R"),
    ("keyStart", "Start"),
    ("keySelect", "Select"),
]

def _read_ini_section(path: Path, section: str) -> dict[str, str]:
    result: dict[str, str] = {}
    if not path.is_file():
        return result
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return result
    header = f"[{section}]"
    in_section = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            in_section = stripped == header
            continue
        if not in_section or not stripped or stripped.startswith("#") or stripped.startswith(";"):
            continue
        if "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        result[key.strip()] = value.strip()
    return result

def load_mgba_settings(emulator: Game) -> dict:
    platform_id = emulator.platform_id or "gba"
    prepare_mgba_config(emulator, platform_id)
    root = mgba_dir(emulator)
    config = root / "config.ini"
    ports = _read_ini_section(config, "ports.qt")
    binds_raw = _read_ini_section(config, "gba.input.QT_K")
    if not binds_raw:
        binds_raw = _read_ini_section(config, "input.QT_K")
    binds = dict(MGBA_DEFAULT_BINDS)
    for key in MGBA_DEFAULT_BINDS:
        if key in binds_raw:
            try:
                binds[key] = int(binds_raw[key])
            except ValueError:
                pass
    volume = 256
    try:
        volume = int(ports.get("volume", "256"))
    except ValueError:
        volume = 256
    volume_pct = max(0, min(100, round(volume * 100 / 256)))
    return {
        "binds": binds,
        "fullscreen": ports.get("fullscreen", "0") == "1",
        "mute": ports.get("mute", "0") == "1",
        "lock_aspect": ports.get("lockAspectRatio", "1") != "0",
        "volume_pct": volume_pct,
        "config_path": str(config),
    }

def save_mgba_settings(
    emulator: Game,
    *,
    binds: dict[str, int],
    fullscreen: bool,
    mute: bool,
    lock_aspect: bool,
    volume_pct: int,
) -> Path:
    platform_id = emulator.platform_id or "gba"
    prepare_mgba_config(emulator, platform_id)
    root = mgba_dir(emulator)
    config = root / "config.ini"
    volume = max(0, min(256, round(int(volume_pct) * 256 / 100)))
    _upsert_ini_keys(
        config,
        "ports.qt",
        {
            "fullscreen": "1" if fullscreen else "0",
            "mute": "1" if mute else "0",
            "lockAspectRatio": "1" if lock_aspect else "0",
            "volume": str(volume),
        },
    )
    bind_map = {key: str(int(binds.get(key, MGBA_DEFAULT_BINDS[key]))) for key in MGBA_DEFAULT_BINDS}
    _upsert_ini_keys(config, "gba.input.QT_K", bind_map)
    _upsert_ini_keys(config, "input.QT_K", bind_map)
    log(
        "info",
        "save_mgba_settings",
        config=str(config),
        fullscreen=fullscreen,
        mute=mute,
        lock_aspect=lock_aspect,
        volume=volume,
        binds=bind_map,
    )
    return config

def launch_args_for(emulator: Game, rom: RomEntry) -> list[str]:
    if not rom.path:
        raise ValueError("ROM não está instalada.")
    args: list[str] = []
    try:
        data = load_mgba_settings(emulator)
        if data.get("fullscreen"):
            args.append("-f")
    except Exception as exc:
        log_exception("launch_args: falha ao ler settings", exc)
    args.append(rom.path)
    log("info", "launch_args_for", rom=rom.path, args=args)
    return args

def save_stem_for(rom: RomEntry) -> str:
    return Path(rom.filename or rom.path or rom.name).stem

def battery_save_path(rom: RomEntry) -> Path:
    return saves_dir_for(rom.platform_id) / f"{save_stem_for(rom)}.sav"

def find_rom_saves(rom: RomEntry) -> list[Path]:
    folder = saves_dir_for(rom.platform_id)
    stem = save_stem_for(rom).casefold()
    found: list[Path] = []
    if not folder.is_dir():
        return found
    for path in sorted(folder.iterdir(), key=lambda p: p.name.casefold()):
        if not path.is_file():
            continue
        if path.stem.casefold() == stem and path.suffix.lower() in {".sav", ".sa1", ".sa2"}:
            found.append(path)
    battery = battery_save_path(rom)
    if battery.is_file() and battery not in found:
        found.insert(0, battery)
    return found

def has_battery_save(rom: RomEntry) -> bool:
    return battery_save_path(rom).is_file()

def import_battery_save(rom: RomEntry, source: Path) -> Path:
    src = Path(source)
    if not src.is_file():
        raise ValueError("Arquivo de save inválido.")
    dest = battery_save_path(rom)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.resolve() != src.resolve():
        shutil.copy2(src, dest)
    return dest

def export_battery_save(rom: RomEntry, dest: Path) -> Path:
    src = battery_save_path(rom)
    if not src.is_file():
        raise ValueError("Esta ROM ainda não tem save.")
    target = Path(dest)
    if target.is_dir():
        target = target / src.name
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, target)
    return target

def open_saves_folder(platform_id: str) -> Path:
    folder = saves_dir_for(platform_id)
    folder.mkdir(parents=True, exist_ok=True)
    return folder

def sync_emulator_with_disk(emulator: Game, settings: Settings) -> None:
    target = emulator_install_dir(settings, emulator)
    local = settings.get_installed_game(emulator.name)
    if local:
        emulator.installed_version = local.get("version")
        emulator.install_path = local.get("path") or (str(target) if target else None)
        if not emulator.executable:
            emulator.executable = local.get("executable")
    if target is not None and target.is_dir():
        version_file = target / "version.txt"
        if version_file.exists():
            try:
                text = version_file.read_text(encoding="utf-8").strip()
                if text:
                    emulator.installed_version = text
            except OSError:
                pass
        preferred = _prefer_mgba_executable(target, emulator.executable)
        if preferred:
            changed = preferred != (emulator.executable or "")
            emulator.executable = preferred
            emulator.install_path = str(target)
            if emulator.installed_version and (
                changed or not local or local.get("executable") != preferred
            ):
                settings.set_installed_game(
                    emulator.name,
                    emulator.installed_version,
                    str(target),
                    preferred,
                )
                log("info", "emulator executable preferido", name=emulator.name, exe=preferred)
    emulator.update_status()

def _prefer_mgba_executable(root: Path, current: str | None) -> str | None:
    ranking = (
        "mgba-qt.exe",
        "mgba.exe",
        "mgba-sdl.exe",
    )
    found: dict[str, Path] = {}
    for path in root.rglob("*.exe"):
        if not path.is_file():
            continue
        found[path.name.lower()] = path
    for name in ranking:
        hit = found.get(name)
        if hit is not None:
            return str(hit.relative_to(root)).replace("\\", "/")
    if current:
        candidate = root / current
        if candidate.is_file():
            return str(Path(current)).replace("\\", "/")
    if found:
        best = sorted(found.values(), key=lambda p: (len(p.relative_to(root).parts), p.name.lower()))[0]
        return str(best.relative_to(root)).replace("\\", "/")
    return None
