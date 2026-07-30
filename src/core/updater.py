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

DETACHED_PROCESS = 0x00000008
CREATE_NEW_PROCESS_GROUP = 0x00000200
CREATE_NO_WINDOW = 0x08000000

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

def _ps_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"

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
    script = update_dir / f"apply_update_{stamp}.ps1"

    notify("Baixando atualização...", 10)
    _download_file(asset_url, new_exe, lambda p: notify("Baixando atualização...", 10 + p * 0.75))

    if new_exe.stat().st_size < 1_000_000:
        raise ValueError("Arquivo baixado parece inválido (muito pequeno).")

    notify("Preparando reinício...", 90)
    pid = os.getpid()
    target_lit = _ps_literal(str(target))
    new_lit = _ps_literal(str(new_exe))
    log_lit = _ps_literal(str(log_file))

    script_content = f"""$ErrorActionPreference = 'Continue'
$pidToWait = {pid}
$target = {target_lit}
$newFile = {new_lit}
$logFile = {log_lit}

function Write-Log([string]$msg) {{
  $line = "[{{0}}] {{1}}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $msg
  Add-Content -Path $logFile -Value $line -Encoding UTF8
}}

Write-Log "update start pid=$pidToWait"
Write-Log "target=$target"
Write-Log "new=$newFile"

try {{
  Wait-Process -Id $pidToWait -Timeout 120 -ErrorAction SilentlyContinue
}} catch {{
  Write-Log "Wait-Process: $($_.Exception.Message)"
}}

Start-Sleep -Seconds 1

$copied = $false
for ($i = 1; $i -le 20; $i++) {{
  try {{
    Copy-Item -LiteralPath $newFile -Destination $target -Force -ErrorAction Stop
    $copied = $true
    Write-Log "copy ok attempt=$i"
    break
  }} catch {{
    Write-Log "copy fail attempt=$i err=$($_.Exception.Message)"
    Start-Sleep -Seconds 1
  }}
}}

if (-not $copied) {{
  Write-Log "copy failed permanently"
  exit 1
}}

Remove-Item -LiteralPath $newFile -Force -ErrorAction SilentlyContinue

try {{
  Start-Process -FilePath $target -Verb RunAs
  Write-Log "restart RunAs ok"
}} catch {{
  try {{
    Start-Process -FilePath $target
    Write-Log "restart normal ok"
  }} catch {{
    Write-Log "restart failed: $($_.Exception.Message)"
    exit 1
  }}
}}

Remove-Item -LiteralPath $PSCommandPath -Force -ErrorAction SilentlyContinue
Write-Log "update done"
"""
    script.write_text(script_content, encoding="utf-8")

    notify("Reiniciando...", 100)
    flags = DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW
    subprocess.Popen(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-WindowStyle",
            "Hidden",
            "-File",
            str(script),
        ],
        cwd=str(update_dir),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=flags,
        close_fds=True,
    )

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
