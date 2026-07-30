from __future__ import annotations

import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Callable, Optional
from urllib.parse import urlparse

import requests

from src.core.settings import APP_NAME

ProgressCallback = Callable[[str, float], None]

CREATE_NO_WINDOW = 0x08000000
DETACHED_PROCESS = 0x00000008
CREATE_NEW_PROCESS_GROUP = 0x00000200

def _github_repo_from_url(url: str) -> Optional[tuple[str, str]]:
    parsed = urlparse(url)
    if "github.com" not in parsed.netloc:
        return None
    parts = [p for p in parsed.path.split("/") if p]
    if len(parts) >= 2:
        return parts[0], parts[1].removesuffix(".git")
    return None

def resolve_release_asset_url(download_hint: str) -> str:
    hint = (download_hint or "").strip()
    if not hint:
        raise ValueError("URL de download do launcher não configurada.")

    if hint.lower().endswith(".exe") and "github.com" in hint:
        return hint

    repo = _github_repo_from_url(hint)
    if not repo:
        return hint

    owner, name = repo
    api = f"https://api.github.com/repos/{owner}/{name}/releases/latest"
    resp = requests.get(
        api,
        timeout=20,
        headers={"Accept": "application/vnd.github+json", "User-Agent": "SteamMussarelos"},
    )
    resp.raise_for_status()
    data = resp.json()

    assets = data.get("assets") or []
    exe_assets = [a for a in assets if str(a.get("name", "")).lower().endswith(".exe")]
    if not exe_assets:
        raise ValueError(
            "Nenhum .exe encontrado no release mais recente do GitHub.\n"
            "Publique o SteamMussarelos.exe como asset do release."
        )

    preferred = next(
        (
            a
            for a in exe_assets
            if re.search(r"steammussarelos|launcher|main", a["name"], re.I)
        ),
        exe_assets[0],
    )
    url = preferred.get("browser_download_url")
    if not url:
        raise ValueError("Asset do release sem URL de download.")
    return url

def current_executable_path() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve()
    return Path(sys.argv[0]).resolve()

def _updates_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA") or str(Path.home())
    path = Path(base) / APP_NAME / "updates"
    path.mkdir(parents=True, exist_ok=True)
    return path

def apply_launcher_update(
    download_hint: str,
    new_version: str,
    settings=None,
    on_progress: Optional[ProgressCallback] = None,
) -> None:
    def notify(msg: str, pct: float) -> None:
        if on_progress:
            on_progress(msg, pct)

    if not getattr(sys, "frozen", False):
        raise RuntimeError(
            "Atualização automática só funciona no .exe empacotado.\n"
            "Em desenvolvimento, atualize o código e gere um novo build."
        )

    notify("Resolvendo release...", 5)
    asset_url = resolve_release_asset_url(download_hint)

    target = current_executable_path()
    update_dir = _updates_dir()
    stamp = str(int(time.time()))
    new_exe = update_dir / f"SteamMussarelos_{new_version}_{stamp}.exe"
    log_file = update_dir / "update.log"
    bat = update_dir / f"apply_update_{stamp}.bat"

    notify("Baixando atualização...", 10)
    _download_file(asset_url, new_exe, lambda p: notify("Baixando atualização...", 10 + p * 0.75))

    if new_exe.stat().st_size < 1_000_000:
        raise ValueError("Arquivo baixado parece inválido (muito pequeno).")

    notify("Preparando reinício...", 90)
    target_s = str(target)
    new_s = str(new_exe)
    log_s = str(log_file)
    pid = os.getpid()

    bat_content = f"""@echo off
setlocal EnableExtensions
set "TARGET={target_s}"
set "NEW={new_s}"
set "LOG={log_s}"
set "PID={pid}"

echo [%date% %time%] update start >> "%LOG%"
echo target=%TARGET% >> "%LOG%"
echo new=%NEW% >> "%LOG%"

:wait
tasklist /FI "PID eq %PID%" 2>nul | find "%PID%" >nul
if not errorlevel 1 (
  ping -n 2 127.0.0.1 >nul
  goto wait
)

ping -n 2 127.0.0.1 >nul

set "OK=0"
for /L %%i in (1,1,15) do (
  copy /Y "%NEW%" "%TARGET%" >nul 2>&1
  if not errorlevel 1 (
    set "OK=1"
    goto copied
  )
  ping -n 2 127.0.0.1 >nul
)

:copied
if "%OK%"=="0" (
  echo [%date% %time%] copy failed >> "%LOG%"
  exit /b 1
)

echo [%date% %time%] copy ok >> "%LOG%"
del /F /Q "%NEW%" >nul 2>&1

powershell -NoProfile -ExecutionPolicy Bypass -Command "try {{ Start-Process -FilePath '%TARGET%' -Verb RunAs }} catch {{ Start-Process -FilePath '%TARGET%' }}" >> "%LOG%" 2>&1
echo [%date% %time%] restart requested >> "%LOG%"
del /F /Q "%~f0" >nul 2>&1
"""
    bat.write_text(bat_content, encoding="utf-8")

    notify("Reiniciando...", 100)
    flags = DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    if sys.platform == "win32":
        flags |= CREATE_NO_WINDOW

    subprocess.Popen(
        ["cmd.exe", "/c", str(bat)],
        cwd=str(update_dir),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=flags,
        close_fds=True,
    )

def _download_file(
    url: str,
    dest: Path,
    on_pct: Optional[Callable[[float], None]] = None,
) -> None:
    session = requests.Session()
    session.headers.update({"User-Agent": "SteamMussarelos"})
    with session.get(url, stream=True, timeout=120, allow_redirects=True) as resp:
        resp.raise_for_status()
        total = int(resp.headers.get("content-length", 0))
        downloaded = 0
        dest.parent.mkdir(parents=True, exist_ok=True)
        with open(dest, "wb") as f:
            for chunk in resp.iter_content(chunk_size=256 * 1024):
                if not chunk:
                    continue
                f.write(chunk)
                downloaded += len(chunk)
                if on_pct and total:
                    on_pct(min(100.0, (downloaded / total) * 100))
                elif on_pct:
                    on_pct(min(99.0, downloaded / (1024 * 1024)))
