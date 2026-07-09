from __future__ import annotations

import re
from urllib.parse import parse_qs, urlparse

def normalize_gdrive_url(url: str) -> str:
    if "drive.google.com" not in url:
        return url

    file_id = None
    if "/file/d/" in url:
        match = re.search(r"/file/d/([^/]+)", url)
        if match:
            file_id = match.group(1)

    elif "id=" in url:
        parsed = parse_qs(urlparse(url).query)
        file_id = parsed.get("id", [None])[0]

    if file_id:
        return f"https://drive.google.com/uc?export=download&id={file_id}"
    return url

def format_bytes(num: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if num < 1024:
            return f"{num:.1f} {unit}" if unit != "B" else f"{num} B"
        num /= 1024
    return f"{num:.1f} TB"

def format_speed(bytes_per_sec: float) -> str:
    return f"{format_bytes(int(bytes_per_sec))}/s"
