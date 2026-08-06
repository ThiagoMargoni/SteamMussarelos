from __future__ import annotations

import hashlib
import io
import os
import threading
from pathlib import Path
from typing import Callable, Optional

import requests
from PIL import Image
from PySide6.QtGui import QImage, QPixmap

from src.core.debug_mode import use_local_assets
from src.core.settings import REMOTE_CATALOG_URL
from src.ui.qt_bridge import ui_call
from src.ui.theme import ICON_SIZE
from src.utils.paths import resolve_resource
from src.utils.remote_assets import resolve_icon_url

_pil_cache: dict[str, Image.Image] = {}
_pixmap_cache: dict[str, QPixmap] = {}
_memory_lock = threading.Lock()

def _cache_key(icon_path: str, size: int) -> str:
    return f"{icon_path}|{size}|contain"

def icon_cache_key(icon_path: str, size: int) -> str:
    return _cache_key(icon_path, size)

def _scale_icon(img: Image.Image, size: int) -> Image.Image:
    src = img.convert("RGBA")
    src.thumbnail((size, size), Image.Resampling.LANCZOS)
    return src

def _icon_cache_dir() -> Path:
    base = os.environ.get("APPDATA") or os.environ.get("LOCALAPPDATA") or str(Path.home())
    path = Path(base) / "SteamMussarelos" / "icon_cache"
    path.mkdir(parents=True, exist_ok=True)
    return path

def _cache_path_for_url(url: str) -> Path:
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()
    suffix = Path(url.split("?", 1)[0]).suffix.lower() or ".img"
    if suffix not in {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}:
        suffix = ".img"
    return _icon_cache_dir() / f"{digest}{suffix}"

def pil_to_pixmap(image: Image.Image) -> QPixmap:
    rgba = image.convert("RGBA")
    data = rgba.tobytes("raw", "RGBA")
    qimg = QImage(data, rgba.width, rgba.height, QImage.Format.Format_RGBA8888).copy()
    return QPixmap.fromImage(qimg)

def get_cached_icon(icon_path: Optional[str], size: int = ICON_SIZE) -> Optional[QPixmap]:
    if not icon_path:
        return None
    with _memory_lock:
        pix = _pixmap_cache.get(_cache_key(icon_path, size))
        return QPixmap(pix) if pix is not None else None

def load_game_icon(
    icon_path: Optional[str],
    on_ready: Callable[[Optional[QPixmap]], None],
    size: int = ICON_SIZE,
    catalog_url: str = REMOTE_CATALOG_URL,
) -> None:
    if not icon_path:
        on_ready(None)
        return

    cache_key = _cache_key(icon_path, size)
    with _memory_lock:
        cached = _pixmap_cache.get(cache_key)
    if cached is not None:
        on_ready(QPixmap(cached))
        return

    def _work() -> None:
        try:
            image = _fetch_image(icon_path, size, catalog_url)
            if image is None:
                ui_call(lambda: on_ready(None))
                return
            pixmap = pil_to_pixmap(image)
            with _memory_lock:
                _pil_cache[cache_key] = image
                _pixmap_cache[cache_key] = pixmap
            ui_call(lambda p=QPixmap(pixmap): on_ready(p))
        except Exception:
            ui_call(lambda: on_ready(None))

    threading.Thread(target=_work, daemon=True).start()

def _fetch_image(icon_path: Optional[str], size: int, catalog_url: str) -> Optional[Image.Image]:
    if not icon_path:
        return None

    if use_local_assets() or not (
        icon_path.startswith("http://") or icon_path.startswith("https://")
    ):
        found = resolve_resource(icon_path) or resolve_resource("icons", Path(icon_path).name)
        if found and found.exists():
            img = Image.open(found)
            img.load()
            return _scale_icon(img, size)
        if use_local_assets():
            return None

    remote = resolve_icon_url(icon_path, catalog_url)
    if remote and (remote.startswith("http://") or remote.startswith("https://")):
        img = _load_remote(remote)
        if img is not None:
            return _scale_icon(img, size)

    if not icon_path.startswith("http"):
        found = resolve_resource(icon_path) or resolve_resource("icons", Path(icon_path).name)
        if found and found.exists():
            img = Image.open(found)
            img.load()
            return _scale_icon(img, size)
    return None

def _load_remote(url: str) -> Optional[Image.Image]:
    cache = _cache_path_for_url(url)
    if cache.exists() and cache.stat().st_size > 0:
        try:
            img = Image.open(cache)
            img.load()
            threading.Thread(target=_refresh_cache, args=(url, cache), daemon=True).start()
            return img
        except Exception:
            cache.unlink(missing_ok=True)
    return _download_to_cache(url, cache)

def _refresh_cache(url: str, cache: Path) -> None:
    try:
        _download_to_cache(url, cache)
    except Exception:
        pass

def _download_to_cache(url: str, cache: Path) -> Optional[Image.Image]:
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        data = resp.content
        if not data:
            return None
        try:
            cache.write_bytes(data)
        except OSError:
            pass
        img = Image.open(io.BytesIO(data))
        img.load()
        return img
    except Exception:
        return None
