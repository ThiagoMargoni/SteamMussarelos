from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
from typing import Callable, Optional
from urllib.parse import urlparse

import requests

from src.core.settings import LAUNCHER_VERSION, Settings

ProgressCallback = Callable[[str, float], None]

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

def apply_launcher_update(
    download_hint: str,
    new_version: str,
    settings: Settings,
    on_progress: Optional[ProgressCallback] = None,
) -> None:
    def notify(msg: str, pct: float) -> None:
        if on_progress:
            on_progress(msg, pct)

    notify("Resolvendo release...", 5)
    asset_url = resolve_release_asset_url(download_hint)

    target = current_executable_path()
    if not getattr(sys, "frozen", False):
        raise RuntimeError(
            "Atualização automática só funciona no .exe empacotado.\n"
            "Em desenvolvimento, atualize o código e gere um novo build."
        )

    tmp_dir = Path(tempfile.mkdtemp(prefix="steam_mussarelos_update_"))
    new_exe = tmp_dir / "SteamMussarelos_new.exe"

    notify("Baixando atualização...", 10)
    _download_file(asset_url, new_exe, lambda p: notify("Baixando atualização...", 10 + p * 0.75))

    if new_exe.stat().st_size < 1_000_000:
        raise ValueError("Arquivo baixado parece inválido (muito pequeno).")

    notify("Preparando substituição...", 90)
    settings.launcher_version = new_version
    settings.save()

    bat = tmp_dir / "apply_update.bat"
    bat_content = f"""@echo off
setlocal
set "TARGET={target}"
set "NEW={new_exe}"
set "PID={os.getpid()}"

:wait
tasklist /FI "PID eq %PID%" | find "%PID%" >nul
if not errorlevel 1 (
  timeout /t 1 /nobreak >nul
  goto wait
)

timeout /t 1 /nobreak >nul
copy /Y "%NEW%" "%TARGET%" >nul
if errorlevel 1 (
  echo Falha ao substituir o executavel.
  pause
  exit /b 1
)

start "" "%TARGET%"
del "%NEW%" >nul 2>&1
del "%~f0" >nul 2>&1
"""
    bat.write_text(bat_content, encoding="utf-8")

    notify("Reiniciando...", 100)
    subprocess.Popen(
        ["cmd", "/c", str(bat)],
        cwd=str(tmp_dir),
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
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
