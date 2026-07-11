from __future__ import annotations

import shutil
import subprocess
import zipfile
from pathlib import Path
from typing import Optional


def detect_archive_type(path: Path) -> str:
    with open(path, "rb") as f:
        magic = f.read(8)

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


def _strip_single_root(dest: Path) -> None:
    """Se a extração criou uma única pasta raiz, sobe o conteúdo um nível."""
    try:
        children = [c for c in dest.iterdir()]
    except OSError:
        return

    if len(children) != 1 or not children[0].is_dir():
        return

    root = children[0]
    # Evita mover se a pasta raiz tem o mesmo nome do destino (já está ok)
    for item in list(root.iterdir()):
        target = dest / item.name
        if target.exists():
            if target.is_dir():
                shutil.rmtree(target)
            else:
                target.unlink()
        shutil.move(str(item), str(target))
    shutil.rmtree(root, ignore_errors=True)


def _extract_zip(archive: Path, dest: Path) -> int:
    extracted = 0
    with zipfile.ZipFile(archive, "r") as zf:
        names = [n for n in zf.namelist() if n.strip()]
        if not names:
            raise ValueError("ZIP vazio — nenhum arquivo encontrado.")

        normalized = [n.replace("\\", "/") for n in names]
        top_levels = {n.split("/")[0] for n in normalized if n.split("/")[0]}

        strip_prefix: str | None = None
        if len(top_levels) == 1:
            root = next(iter(top_levels))
            if all(n.startswith(root + "/") for n in normalized):
                strip_prefix = root

        for member in zf.infolist():
            rel = member.filename.replace("\\", "/")
            if strip_prefix:
                if rel == strip_prefix or rel == strip_prefix + "/":
                    continue
                if rel.startswith(strip_prefix + "/"):
                    rel = rel[len(strip_prefix) + 1 :]

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
    result = subprocess.run(
        [seven_zip, "x", str(archive), f"-o{dest}", "-y"],
        capture_output=True,
        text=True,
        timeout=600,
    )
    if result.returncode != 0:
        raise ValueError(result.stderr.strip() or result.stdout.strip() or "Falha ao extrair com 7-Zip.")
    _strip_single_root(dest)
    return sum(1 for _ in dest.rglob("*") if _.is_file())


def _extract_with_winrar(archive: Path, dest: Path, winrar: str) -> int:
    # UnRAR: e = extract without paths, x = extract with full paths
    result = subprocess.run(
        [winrar, "x", "-y", str(archive), str(dest) + "\\"],
        capture_output=True,
        text=True,
        timeout=600,
    )
    if result.returncode != 0:
        raise ValueError(result.stderr.strip() or result.stdout.strip() or "Falha ao extrair com WinRAR.")
    _strip_single_root(dest)
    return sum(1 for _ in dest.rglob("*") if _.is_file())


def extract_archive(archive: Path, dest: Path) -> int:
    """
    Extrai ZIP/RAR/7z para dest, removendo pasta raiz duplicada quando houver.
    Retorna quantidade de arquivos extraídos.
    """
    if not archive.exists() or archive.stat().st_size < 4:
        raise ValueError("Arquivo baixado está vazio ou incompleto.")

    dest.mkdir(parents=True, exist_ok=True)
    kind = detect_archive_type(archive)

    if kind == "zip":
        extracted = _extract_zip(archive, dest)
        if extracted == 0:
            raise ValueError("Nenhum arquivo foi extraído do ZIP.")
        return extracted

    if kind in ("rar", "7z"):
        seven = _find_7zip()
        if seven:
            extracted = _extract_with_7zip(archive, dest, seven)
            if extracted == 0:
                raise ValueError("Nenhum arquivo foi extraído do arquivo.")
            return extracted

        if kind == "rar":
            winrar = _find_winrar()
            if winrar:
                extracted = _extract_with_winrar(archive, dest, winrar)
                if extracted == 0:
                    raise ValueError("Nenhum arquivo foi extraído do RAR.")
                return extracted

        tool = "7-Zip ou WinRAR" if kind == "rar" else "7-Zip"
        raise ValueError(
            f"O arquivo é {kind.upper()}, mas {tool} não foi encontrado.\n\n"
            "Instale o 7-Zip (https://www.7-zip.org/) ou reenvie o jogo como ZIP."
        )

    raise ValueError(
        "Formato de arquivo não suportado. "
        "Use ZIP ou RAR (com 7-Zip instalado)."
    )
