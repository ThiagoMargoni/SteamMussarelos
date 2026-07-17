from __future__ import annotations

import shutil
import subprocess
import zipfile
from pathlib import Path
from typing import Optional

ARCHIVE_SUFFIXES = {".zip", ".rar", ".7z"}

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

def _find_7zip() -> Optional[str]:
    candidates = [
        shutil.which("7z"),
        shutil.which("7za"),
        r"C:\Program Files\7-Zip\7z.exe",
        r"C:\Program Files (x86)\7-Zip\7z.exe",
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
        seven = _find_7zip()
        if seven:
            return _extract_with_7zip(archive, dest, seven)

        if kind == "rar" or archive.suffix.lower() == ".rar":
            winrar = _find_winrar()
            if winrar:
                return _extract_with_winrar(archive, dest, winrar)

        tool = "7-Zip ou WinRAR" if (kind == "rar" or archive.suffix.lower() == ".rar") else "7-Zip"
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
