from __future__ import annotations

import os
import subprocess
import sys
import winreg
from pathlib import Path

import psutil

def is_steam_running() -> bool:
    names = {"steam.exe", "steamwebhelper.exe"}
    for p in psutil.process_iter(["name"]):
        try:
            name = (p.info.get("name") or "").lower()
            if name in names:
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return False

def find_steam_executable() -> Path | None:
    candidates: list[Path] = []

    for root, path in (
        (winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Valve\Steam"),
    ):
        try:
            with winreg.OpenKey(root, path) as key:
                value, _ = winreg.QueryValueEx(key, "SteamExe")
                if value:
                    candidates.append(Path(value))
                value, _ = winreg.QueryValueEx(key, "InstallPath")
                if value:
                    candidates.append(Path(value) / "steam.exe")
        except OSError:
            continue

    pf = os.environ.get("ProgramFiles(x86)") or r"C:\Program Files (x86)"
    pf64 = os.environ.get("ProgramFiles") or r"C:\Program Files"
    candidates.extend(
        [
            Path(pf) / "Steam" / "steam.exe",
            Path(pf64) / "Steam" / "steam.exe",
            Path.home() / "Steam" / "steam.exe",
        ]
    )

    for path in candidates:
        try:
            if path.is_file():
                return path.resolve()
        except OSError:
            continue
    return None


def ensure_steam_running() -> tuple[bool, str]:
    if is_steam_running():
        return True, "Steam já está em execução."

    steam = find_steam_executable()
    if not steam:
        return False, "Steam não encontrada. Instale a Steam ou inicie manualmente."

    try:
        flags = 0
        if sys.platform == "win32":
            flags = getattr(subprocess, "DETACHED_PROCESS", 0x00000008)
            flags |= getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)
        subprocess.Popen(
            [str(steam), "-silent"],
            cwd=str(steam.parent),
            creationflags=flags,
            close_fds=True,
        )
        return True, f"Steam iniciada: {steam}"
    except OSError as exc:
        return False, f"Não foi possível abrir a Steam: {exc}"
