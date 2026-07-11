from __future__ import annotations

import re
from pathlib import Path
from typing import Callable, Optional
from urllib.parse import parse_qs, urlparse

import requests

CHUNK_SIZE = 256 * 1024
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)
GDRIVE_DOWNLOAD = "https://drive.usercontent.google.com/download"

def extract_gdrive_file_id(url: str) -> Optional[str]:
    if "drive.google.com" not in url and "docs.google.com" not in url and "drive.usercontent.google.com" not in url:
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
    file_id = extract_gdrive_file_id(url)
    if file_id:
        return f"{GDRIVE_DOWNLOAD}?id={file_id}&export=download"
    return url

def _parse_gdrive_form(html: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for name, value in re.findall(
        r'<input[^>]+type="hidden"[^>]*name="([^"]+)"[^>]*value="([^"]*)"',
        html,
        flags=re.IGNORECASE,
    ):
        fields[name] = value
    for name, value in re.findall(
        r'<input[^>]+name="([^"]+)"[^>]*value="([^"]*)"[^>]*type="hidden"',
        html,
        flags=re.IGNORECASE,
    ):
        fields.setdefault(name, value)
    return fields

def _is_html_response(response: requests.Response, peek: bytes = b"") -> bool:
    content_type = (response.headers.get("content-type") or "").lower()
    if "text/html" in content_type:
        return True
    sample = peek[:200].lower()
    return b"<html" in sample or b"<!doctype html" in sample

def download_file(
    url: str,
    dest: Path,
    on_chunk: Optional[Callable[[int, int], None]] = None,
    cancel_check: Optional[Callable[[], bool]] = None,
) -> Path:
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
) -> Path:
    params: dict[str, str] = {"id": file_id, "export": "download"}

    response = session.get(GDRIVE_DOWNLOAD, params=params, stream=True, timeout=120)
    response.raise_for_status()

    if _is_html_response(response):
        html = response.text
        response.close()
        fields = _parse_gdrive_form(html)

        if not fields.get("confirm") and "can't scan" not in html.lower() and "virus" not in html.lower():
            raise ValueError(
                "Google Drive bloqueou o download. "
                "Verifique se o arquivo está público ('Qualquer pessoa com o link')."
            )

        params = {
            "id": fields.get("id", file_id),
            "export": fields.get("export", "download"),
            "confirm": fields.get("confirm", "t"),
        }
        if fields.get("uuid"):
            params["uuid"] = fields["uuid"]

        response = session.get(GDRIVE_DOWNLOAD, params=params, stream=True, timeout=120)
        response.raise_for_status()

        if _is_html_response(response):
            response.close()
            raise ValueError(
                "Google Drive ainda exige confirmação. "
                "Confirme que o link está público e tente novamente."
            )

    disposition = response.headers.get("content-disposition") or ""
    filename_match = re.search(r'filename="?([^";]+)"?', disposition)
    suggested_name = filename_match.group(1) if filename_match else dest.name

    suffix = Path(suggested_name).suffix.lower()
    if suffix and dest.suffix.lower() != suffix:
        dest = dest.with_suffix(suffix)

    total = int(response.headers.get("content-length", 0))
    downloaded = _stream_to_file(response, dest, total, on_chunk, cancel_check)
    response.close()

    if downloaded < 100:
        raise ValueError("Download incompleto ou arquivo vazio.")

    with open(dest, "rb") as f:
        header = f.read(512)

    if b"<html" in header.lower() or b"<!doctype" in header.lower():
        raise ValueError(
            "Google Drive retornou uma página HTML em vez do arquivo. "
            "Confirme que o link está público."
        )

    return dest

def _download_stream(
    session: requests.Session,
    url: str,
    dest: Path,
    on_chunk: Optional[Callable[[int, int], None]],
    cancel_check: Optional[Callable[[], bool]],
) -> Path:
    response = session.get(url, stream=True, timeout=120)
    response.raise_for_status()
    total = int(response.headers.get("content-length", 0))
    _stream_to_file(response, dest, total, on_chunk, cancel_check)
    response.close()
    return dest

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
