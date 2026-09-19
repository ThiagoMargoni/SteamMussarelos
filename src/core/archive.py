from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Callable, Optional

from src.core.debug_mode import log, log_exception
from src.core.settings import app_data_dir

ARCHIVE_SUFFIXES = {".zip", ".rar", ".7z"}
_SEVEN_ZIP_INSTALLERS = (
    "https://www.7-zip.org/a/7z2603-x64.exe",
    "https://www.7-zip.org/a/7z2602-x64.exe",
    "https://www.7-zip.org/a/7z2501-x64.exe",
)
_SEVEN_ZR_URL = "https://www.7-zip.org/a/7zr.exe"

def detect_archive_type(path: Path) -> str:
    try:
        with open(path, "rb") as f:
            magic = f.read(8)
    except OSError:
        return "unknown"

    if magic[:2] == b"PK":
        return "zip"
    if magic[:4] == b"Rar!" or magic[:7] == b"\x52\x61\x72\x21\x1a\x07\x00":
        return "rar"
    if magic[:6] == b"7z\xbc\xaf\x27\x1c":
        return "7z"
    if magic[:2] == b"\x1f\x8b":
        return "gzip"
    return "unknown"

def _tools_dir() -> Path:
    path = app_data_dir() / "tools" / "7zip"
    path.mkdir(parents=True, exist_ok=True)
    return path

def _find_7zip() -> Optional[str]:
    tools = _tools_dir()
    candidates = [
        shutil.which("7z"),
        shutil.which("7za"),
        shutil.which("7zr"),
        r"C:\Program Files\7-Zip\7z.exe",
        r"C:\Program Files (x86)\7-Zip\7z.exe",
        str(tools / "7z.exe"),
        str(tools / "7za.exe"),
        str(tools / "7zr.exe"),
    ]
    for path in candidates:
        if path and Path(path).is_file():
            return path
    return None

def _find_winrar() -> Optional[str]:
    candidates = [
        shutil.which("UnRAR"),
        shutil.which("unrar"),
        shutil.which("WinRAR"),
        r"C:\Program Files\WinRAR\UnRAR.exe",
        r"C:\Program Files\WinRAR\WinRAR.exe",
        r"C:\Program Files (x86)\WinRAR\UnRAR.exe",
        r"C:\Program Files (x86)\WinRAR\WinRAR.exe",
    ]
    for path in candidates:
        if path and Path(path).is_file():
            return path
    return None

def _archive_hint_from_name(name: str) -> str:
    lower = (name or "").lower().split("?", 1)[0]
    if lower.endswith(".7z"):
        return "7z"
    if lower.endswith(".rar"):
        return "rar"
    if lower.endswith(".zip"):
        return "zip"
    return ""

def _download_url(url: str, dest: Path) -> Path:
    from src.core.downloader import download_file

    dest.parent.mkdir(parents=True, exist_ok=True)
    return download_file(url, dest)

def _install_7zip_via_winget() -> bool:
    winget = shutil.which("winget")
    if not winget:
        return False
    log("info", "instalando 7-Zip via winget")
    try:
        result = subprocess.run(
            [
                winget,
                "install",
                "--id",
                "7zip.7zip",
                "-e",
                "--silent",
                "--accept-package-agreements",
                "--accept-source-agreements",
                "--disable-interactivity",
            ],
            capture_output=True,
            text=True,
            timeout=300,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        log_exception("winget 7-Zip falhou", exc)
        return False
    log("info", "winget 7-Zip", code=result.returncode)
    return _find_7zip() is not None

def _install_7zip_silent() -> bool:
    tmp = Path(tempfile.mkdtemp(prefix="steam_7zip_"))
    try:
        installer: Path | None = None
        for url in _SEVEN_ZIP_INSTALLERS:
            target = tmp / Path(url).name
            try:
                log("info", "baixando instalador 7-Zip", url=url)
                installer = _download_url(url, target)
                if installer.is_file() and installer.stat().st_size > 100_000:
                    break
            except Exception as exc:
                log_exception("download instalador 7-Zip falhou", exc)
                installer = None
        if installer is None or not installer.is_file():
            return False

        log("info", "instalando 7-Zip silenciosamente", path=str(installer))
        result = subprocess.run(
            [str(installer), "/S"],
            capture_output=True,
            text=True,
            timeout=300,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        log("info", "instalador 7-Zip finalizado", code=result.returncode)
        return _find_7zip() is not None
    except Exception as exc:
        log_exception("instalacao silenciosa 7-Zip falhou", exc)
        return False
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

def _ensure_portable_7zr() -> Optional[str]:
    dest = _tools_dir() / "7zr.exe"
    if dest.is_file() and dest.stat().st_size > 50_000:
        return str(dest)
    try:
        log("info", "baixando 7zr.exe portatil", url=_SEVEN_ZR_URL)
        _download_url(_SEVEN_ZR_URL, dest)
    except Exception as exc:
        log_exception("download 7zr.exe falhou", exc)
        return None
    if dest.is_file() and dest.stat().st_size > 10_000:
        return str(dest)
    return None

def ensure_7zip(
    *,
    need_rar: bool = False,
    on_status: Callable[[str], None] | None = None,
) -> str:
    found = _find_7zip()
    if found:
        return found

    def status(text: str) -> None:
        log("info", text)
        if on_status is not None:
            on_status(text)

    if not need_rar:
        status("Baixando extrator 7-Zip...")
        portable = _ensure_portable_7zr()
        if portable:
            return portable

    status("Instalando 7-Zip...")
    if sys.platform == "win32":
        if _install_7zip_via_winget():
            found = _find_7zip()
            if found:
                return found
        if _install_7zip_silent():
            found = _find_7zip()
            if found:
                return found

    if not need_rar:
        portable = _ensure_portable_7zr()
        if portable:
            return portable

    raise ValueError(
        "Não foi possível instalar o 7-Zip automaticamente.\n\n"
        "Instale manualmente em https://www.7-zip.org/ e tente de novo."
    )

def ensure_extractor_available(
    url_or_name: str,
    on_status: Callable[[str], None] | None = None,
) -> None:
    kind = _archive_hint_from_name(url_or_name)
    if kind == "7z":
        ensure_7zip(need_rar=False, on_status=on_status)
        return
    if kind == "rar":
        if _find_7zip() or _find_winrar():
            return
        ensure_7zip(need_rar=True, on_status=on_status)
        if _find_7zip() or _find_winrar():
            return
        raise ValueError(
            "Este download é um arquivo .rar e não foi possível preparar o 7-Zip.\n\n"
            "Instale o 7-Zip em https://www.7-zip.org/ e tente de novo."
        )

def _move_contents(src: Path, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    for item in list(src.iterdir()):
        target = dest / item.name
        if target.exists():
            if target.is_dir() and item.is_dir():
                _move_contents(item, target)
                shutil.rmtree(item, ignore_errors=True)
                continue
            if target.is_dir():
                shutil.rmtree(target)
            else:
                target.unlink()
        shutil.move(str(item), str(target))

def _strip_single_root(dest: Path) -> bool:
    try:
        children = [c for c in dest.iterdir() if c.name.lower() != "version.txt"]
    except OSError:
        return False

    if len(children) != 1 or not children[0].is_dir():
        return False

    root = children[0]
    _move_contents(root, dest)
    shutil.rmtree(root, ignore_errors=True)
    return True

def _extract_zip(archive: Path, dest: Path) -> int:
    extracted = 0
    with zipfile.ZipFile(archive, "r") as zf:
        names = [n for n in zf.namelist() if n.strip()]
        if not names:
            raise ValueError("ZIP vazio — nenhum arquivo encontrado.")

        for member in zf.infolist():
            rel = member.filename.replace("\\", "/")
            if not rel or rel.endswith("/"):
                (dest / rel).mkdir(parents=True, exist_ok=True)
                continue

            target = dest / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(member) as src, open(target, "wb") as out:
                shutil.copyfileobj(src, out)
            extracted += 1

    return extracted

def _extract_with_7zip(archive: Path, dest: Path, seven_zip: str) -> int:
    before = {p for p in dest.rglob("*")} if dest.exists() else set()
    result = subprocess.run(
        [seven_zip, "x", str(archive), f"-o{dest}", "-y"],
        capture_output=True,
        text=True,
        timeout=600,
    )
    if result.returncode != 0:
        raise ValueError(result.stderr.strip() or result.stdout.strip() or "Falha ao extrair com 7-Zip.")
    after = {p for p in dest.rglob("*")}
    return max(1, len(after - before))

def _extract_with_winrar(archive: Path, dest: Path, winrar: str) -> int:
    before = {p for p in dest.rglob("*")} if dest.exists() else set()
    result = subprocess.run(
        [winrar, "x", "-y", str(archive), str(dest) + "\\"],
        capture_output=True,
        text=True,
        timeout=600,
    )
    if result.returncode != 0:
        raise ValueError(result.stderr.strip() or result.stdout.strip() or "Falha ao extrair com WinRAR.")
    after = {p for p in dest.rglob("*")}
    return max(1, len(after - before))

def _extract_one(archive: Path, dest: Path) -> int:
    dest.mkdir(parents=True, exist_ok=True)
    kind = detect_archive_type(archive)

    if kind == "zip" or archive.suffix.lower() == ".zip":
        return _extract_zip(archive, dest)

    if kind in ("rar", "7z") or archive.suffix.lower() in {".rar", ".7z"}:
        need_rar = kind == "rar" or archive.suffix.lower() == ".rar"
        seven = _find_7zip()
        if not seven:
            try:
                seven = ensure_7zip(need_rar=need_rar)
            except ValueError:
                seven = None
        if seven:
            return _extract_with_7zip(archive, dest, seven)

        if need_rar:
            winrar = _find_winrar()
            if winrar:
                return _extract_with_winrar(archive, dest, winrar)

        tool = "7-Zip ou WinRAR" if need_rar else "7-Zip"
        raise ValueError(
            f"O arquivo é {archive.suffix.upper().lstrip('.') or kind.upper()}, "
            f"mas {tool} não foi encontrado.\n\n"
            "Instale o 7-Zip (https://www.7-zip.org/) ou reenvie o jogo como ZIP."
        )

    raise ValueError(
        "Formato de arquivo não suportado. "
        "Use ZIP ou RAR (com 7-Zip instalado)."
    )

def _find_nested_archives(root: Path) -> list[Path]:
    found: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() in ARCHIVE_SUFFIXES:
            found.append(path)
            continue
        if detect_archive_type(path) in {"zip", "rar", "7z"}:
            found.append(path)
    return found

def _extract_nested_archives(root: Path, max_passes: int = 5) -> None:
    for _ in range(max_passes):
        nested = _find_nested_archives(root)
        if not nested:
            return

        progress = False
        for archive in nested:
            if not archive.exists():
                continue
            target_dir = archive.parent
            try:
                _extract_one(archive, target_dir)
                archive.unlink(missing_ok=True)
                progress = True
            except Exception:
                continue

        if not progress:
            return

def _find_exe(root: Path, preferred: Optional[str] = None) -> Optional[Path]:
    if preferred:
        preferred_name = Path(preferred).name.lower()
        matches = [p for p in root.rglob("*.exe") if p.name.lower() == preferred_name]
        if matches:
            return sorted(matches, key=lambda p: len(p.relative_to(root).parts))[0]

    exes = [p for p in root.rglob("*.exe") if p.is_file()]
    if not exes:
        return None

    ignore = {
        "unitycrashhandler64.exe",
        "unitycrashhandler32.exe",
        "crashreportclient.exe",
        "uninstall.exe",
        "unins000.exe",
        "vc_redist.x64.exe",
        "vc_redist.x86.exe",
        "dxsetup.exe",
    }
    filtered = [p for p in exes if p.name.lower() not in ignore]
    candidates = filtered or exes
    return sorted(candidates, key=lambda p: (len(p.relative_to(root).parts), p.name.lower()))[0]

def _promote_game_root(dest: Path, preferred_executable: Optional[str] = None) -> Optional[str]:
    for _ in range(6):
        if not _strip_single_root(dest):
            break

    exe = _find_exe(dest, preferred_executable)
    if not exe:
        return None

    game_root = exe.parent
    if game_root.resolve() != dest.resolve():
        _move_contents(game_root, dest)
        shutil.rmtree(game_root, ignore_errors=True)

        for folder in sorted(dest.rglob("*"), reverse=True):
            if folder.is_dir():
                try:
                    next(folder.iterdir())
                except StopIteration:
                    folder.rmdir()
                except OSError:
                    pass

    for leftover in list(dest.glob("*")):
        if leftover.is_file() and (
            leftover.suffix.lower() in ARCHIVE_SUFFIXES
            or detect_archive_type(leftover) in {"zip", "rar", "7z"}
        ):
            leftover.unlink(missing_ok=True)

    exe_final = dest / exe.name
    if exe_final.exists():
        return exe.name

    found = _find_exe(dest, preferred_executable)
    if found:
        return str(found.relative_to(dest)).replace("\\", "/")
    return None

def extract_archive(
    archive: Path,
    dest: Path,
    preferred_executable: Optional[str] = None,
) -> tuple[int, Optional[str]]:
    if not archive.exists() or archive.stat().st_size < 4:
        raise ValueError("Arquivo baixado está vazio ou incompleto.")

    dest.mkdir(parents=True, exist_ok=True)
    extracted = _extract_one(archive, dest)
    if extracted == 0:
        raise ValueError("Nenhum arquivo foi extraído.")

    _extract_nested_archives(dest)
    exe_rel = _promote_game_root(dest, preferred_executable)

    file_count = sum(1 for p in dest.rglob("*") if p.is_file())
    if file_count == 0:
        raise ValueError("Nenhum arquivo ficou na pasta após a extração.")

    return file_count, exe_rel
