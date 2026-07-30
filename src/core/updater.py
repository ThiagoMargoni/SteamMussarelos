from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path
from typing import Callable, Optional
from urllib.parse import urlparse

import psutil
import requests

from src.core.settings import APP_NAME

ProgressCallback = Callable[[str, float], None]

APPLY_UPDATE_FLAG = "--apply-update"
UPDATE_TARGET_FLAG = "--update-target"
UPDATE_PID_FLAG = "--update-pid"

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

    lower = hint.lower()
    if (lower.endswith(".zip") or lower.endswith(".exe")) and "github.com" in lower:
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

    def _pick(candidates: list[dict], pattern: str) -> Optional[dict]:
        if not candidates:
            return None
        preferred = next(
            (a for a in candidates if re.search(pattern, a.get("name", ""), re.I)),
            candidates[0],
        )
        return preferred if preferred.get("browser_download_url") else None

    zip_assets = [a for a in assets if str(a.get("name", "")).lower().endswith(".zip")]
    chosen = _pick(zip_assets, r"steammussarelos|launcher")
    if chosen is None:
        exe_assets = [a for a in assets if str(a.get("name", "")).lower().endswith(".exe")]
        chosen = _pick(exe_assets, r"steammussarelos|launcher|main")

    if chosen is None:
        raise ValueError(
            "Nenhum .zip/.exe encontrado no release mais recente do GitHub.\n"
            "Publique SteamMussarelos.zip (com o .exe dentro) como asset do release."
        )
    return str(chosen["browser_download_url"])

def current_executable_path() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve()
    return Path(sys.argv[0]).resolve()

def _updates_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA") or str(Path.home())
    path = Path(base) / APP_NAME / "updates"
    path.mkdir(parents=True, exist_ok=True)
    return path

def _log_update(message: str) -> None:
    log_file = _updates_dir() / "update.log"
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {message}\n"
    try:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(line)
    except OSError:
        pass

def _extract_exe_from_zip(archive: Path, dest_exe: Path) -> Path:
    with zipfile.ZipFile(archive, "r") as zf:
        exe_names = [
            name
            for name in zf.namelist()
            if name.lower().endswith(".exe") and not name.endswith("/")
        ]
        if not exe_names:
            raise ValueError("O .zip do release não contém nenhum .exe.")

        preferred = next(
            (n for n in exe_names if re.search(r"steammussarelos", Path(n).name, re.I)),
            exe_names[0],
        )
        dest_exe.parent.mkdir(parents=True, exist_ok=True)
        with zf.open(preferred) as src, open(dest_exe, "wb") as out:
            shutil.copyfileobj(src, out)
    return dest_exe

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
    download_path = update_dir / f"SteamMussarelos_{new_version}_{stamp}.download"
    new_exe = update_dir / f"SteamMussarelos_{new_version}_{stamp}.exe"

    notify("Baixando atualização...", 10)
    _download_file(asset_url, download_path, lambda p: notify("Baixando atualização...", 10 + p * 0.7))

    if download_path.stat().st_size < 500_000:
        raise ValueError("Arquivo baixado parece inválido (muito pequeno).")

    notify("Extraindo...", 82)
    lower_url = asset_url.lower()
    if lower_url.endswith(".zip") or zipfile.is_zipfile(download_path):
        _extract_exe_from_zip(download_path, new_exe)
        try:
            download_path.unlink()
        except OSError:
            pass
    else:
        download_path.replace(new_exe)

    if not new_exe.is_file() or new_exe.stat().st_size < 1_000_000:
        raise ValueError("Não foi possível obter o .exe da atualização.")

    notify("Preparando reinício...", 95)
    _log_update(f"launch apply-update new={new_exe} target={target} pid={os.getpid()}")

    subprocess.Popen(
        [
            str(new_exe),
            APPLY_UPDATE_FLAG,
            UPDATE_TARGET_FLAG,
            str(target),
            UPDATE_PID_FLAG,
            str(os.getpid()),
        ],
        cwd=str(new_exe.parent),
        close_fds=True,
    )
    notify("Reiniciando...", 100)

def run_apply_update(target: Path, wait_pid: int) -> int:
    source = current_executable_path()
    target = target.resolve()
    _log_update(f"apply-update start source={source} target={target} wait_pid={wait_pid}")

    if wait_pid > 0:
        try:
            proc = psutil.Process(wait_pid)
            proc.wait(timeout=120)
        except (psutil.NoSuchProcess, psutil.TimeoutExpired):
            pass
        except Exception as exc:
            _log_update(f"wait pid error: {exc}")

    time.sleep(1.0)

    copied = False
    last_error = ""
    for attempt in range(1, 21):
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            copied = True
            _log_update(f"copy ok attempt={attempt}")
            break
        except OSError as exc:
            last_error = str(exc)
            _log_update(f"copy fail attempt={attempt} err={exc}")
            time.sleep(1.0)

    if not copied:
        _log_update(f"copy failed permanently: {last_error}")
        return 1

    try:
        subprocess.Popen([str(target)], cwd=str(target.parent), close_fds=True)
        _log_update("restart ok")
    except OSError as exc:
        _log_update(f"restart failed: {exc}")
        return 1

    _log_update("apply-update done")
    return 0

def force_exit_for_update() -> None:
    os._exit(0)

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
