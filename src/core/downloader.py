from __future__ import annotations

import re
from pathlib import Path
from typing import Callable, Optional
from urllib.parse import parse_qs, urlparse

import requests

from src.utils.helpers import format_bytes, format_speed

CHUNK_SIZE = 256 * 1024
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

def extract_gdrive_file_id(url: str) -> Optional[str]:
    if "drive.google.com" not in url and "docs.google.com" not in url:
        return None

    if "/file/d/" in url:
        match = re.search(r"/file/d/([^/]+)", url)
        if match:
            return match.group(1)

    if "id=" in url:
        parsed = parse_qs(urlparse(url).query)
        return parsed.get("id", [None])[0]

    return None

def normalize_gdrive_url(url: str) -> str:
    """Converte links de compartilhamento do Google Drive em URL de download direto."""
    file_id = extract_gdrive_file_id(url)
    if file_id:
        return f"https://drive.google.com/uc?export=download&id={file_id}"
    return url

def _gdrive_confirm_token(response: requests.Response) -> Optional[str]:
    for key, value in response.cookies.items():
        if key.startswith("download_warning"):
            return value

    text = response.text[:8192] if response.text else ""
    match = re.search(r"confirm=([0-9A-Za-z_]+)", text)
    if match:
        return match.group(1)

    match = re.search(r'id="download-form"[^>]*action="[^"]*confirm=([0-9A-Za-z_]+)', text)
    if match:
        return match.group(1)

    return None

def download_file(
    url: str,
    dest: Path,
    on_chunk: Optional[Callable[[int, int], None]] = None,
    cancel_check: Optional[Callable[[], bool]] = None,
) -> int:
    """
    Baixa um arquivo de URL genérica ou Google Drive.
    Retorna o total de bytes baixados.
    """
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    file_id = extract_gdrive_file_id(url)
    if file_id:
        return _download_gdrive(session, file_id, dest, on_chunk, cancel_check)

    return _download_stream(session, url, dest, on_chunk, cancel_check)

def _download_gdrive(
    session: requests.Session,
    file_id: str,
    dest: Path,
    on_chunk: Optional[Callable[[int, int], None]],
    cancel_check: Optional[Callable[[], bool]],
) -> int:
    base_url = "https://drive.google.com/uc"
    params: dict[str, str] = {"export": "download", "id": file_id}

    response = session.get(base_url, params=params, stream=True, timeout=60)
    response.raise_for_status()

    content_type = (response.headers.get("content-type") or "").lower()
    if "text/html" in content_type:
        token = _gdrive_confirm_token(response)
        response.close()
        if token:
            params["confirm"] = token
            response = session.get(base_url, params=params, stream=True, timeout=60)
            response.raise_for_status()
        else:
            raise ValueError(
                "Google Drive exige confirmação de download. "
                "Verifique se o arquivo está público ('Qualquer pessoa com o link')."
            )

    total = int(response.headers.get("content-length", 0))
    downloaded = _stream_to_file(response, dest, total, on_chunk, cancel_check)
    response.close()

    if downloaded < 100:
        raise ValueError("Download incompleto ou arquivo vazio.")

    with open(dest, "rb") as f:
        header = f.read(512)
    if header[:2] != b"PK" and b"<html" in header.lower():
        raise ValueError(
            "Google Drive retornou uma página HTML em vez do arquivo. "
            "Confirme que o link está público e aponta para um ZIP."
        )

    return downloaded

def _download_stream(
    session: requests.Session,
    url: str,
    dest: Path,
    on_chunk: Optional[Callable[[int, int], None]],
    cancel_check: Optional[Callable[[], bool]],
) -> int:
    response = session.get(url, stream=True, timeout=60)
    response.raise_for_status()
    total = int(response.headers.get("content-length", 0))
    downloaded = _stream_to_file(response, dest, total, on_chunk, cancel_check)
    response.close()
    return downloaded

def _stream_to_file(
    response: requests.Response,
    dest: Path,
    total: int,
    on_chunk: Optional[Callable[[int, int], None]],
    cancel_check: Optional[Callable[[], bool]],
) -> int:
    downloaded = 0
    dest.parent.mkdir(parents=True, exist_ok=True)

    with open(dest, "wb") as f:
        for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
            if cancel_check and cancel_check():
                raise InterruptedError("Download cancelado.")
            if not chunk:
                continue
            f.write(chunk)
            downloaded += len(chunk)
            if on_chunk:
                on_chunk(downloaded, total)

    return downloaded
