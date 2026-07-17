from __future__ import annotations

import hashlib
import io
import os
import threading
from pathlib import Path
from typing import Callable, Optional

import customtkinter as ctk
import requests
from PIL import Image, ImageOps

import PIL.JpegImagePlugin  # noqa: F401
import PIL.PngImagePlugin  # noqa: F401
import PIL.GifImagePlugin  # noqa: F401
import PIL.BmpImagePlugin  # noqa: F401
import PIL.WebPImagePlugin  # noqa: F401

from src.core.settings import REMOTE_CATALOG_URL
from src.ui.theme import COLORS, ICON_SIZE
from src.utils.paths import resolve_resource
from src.utils.remote_assets import resolve_icon_url

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

def load_game_icon(
    icon_path: Optional[str],
    on_ready: Callable[[Optional[ctk.CTkImage]], None],
    size: int = ICON_SIZE,
    catalog_url: str = REMOTE_CATALOG_URL,
) -> None:
    def _work() -> None:
        try:
            image = _fetch_image(icon_path, size, catalog_url)
            if image is None:
                on_ready(None)
                return
            on_ready(_to_ctk_image(image, size))
        except Exception:
            on_ready(None)

    threading.Thread(target=_work, daemon=True).start()

def _fetch_image(
    icon_path: Optional[str],
    size: int,
    catalog_url: str,
) -> Optional[Image.Image]:
    if not icon_path:
        return None

    remote = resolve_icon_url(icon_path, catalog_url)
    if remote and (remote.startswith("http://") or remote.startswith("https://")):
        img = _load_remote(remote)
        if img is not None:
            return ImageOps.fit(img.convert("RGB"), (size, size), Image.Resampling.LANCZOS)

    if not icon_path.startswith("http"):
        found = resolve_resource(icon_path) or resolve_resource("icons", Path(icon_path).name)
        if found and found.exists():
            img = Image.open(found)
            img.load()
            return ImageOps.fit(img.convert("RGB"), (size, size), Image.Resampling.LANCZOS)

    return None

def _load_remote(url: str) -> Optional[Image.Image]:
    cache = _cache_path_for_url(url)

    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        data = resp.content
        if data:
            try:
                cache.write_bytes(data)
            except OSError:
                pass
            img = Image.open(io.BytesIO(data))
            img.load()
            return img
    except Exception:
        pass

    if cache.exists() and cache.stat().st_size > 0:
        try:
            img = Image.open(cache)
            img.load()
            return img
        except Exception:
            cache.unlink(missing_ok=True)

    return None

def _to_ctk_image(img: Image.Image, size: int) -> ctk.CTkImage:
    return ctk.CTkImage(light_image=img, dark_image=img, size=(size, size))

def apply_icon_to_label(
    label: ctk.CTkLabel,
    ctk_image: Optional[ctk.CTkImage],
    placeholder: str = "?",
) -> ctk.CTkImage | None:
    if ctk_image:
        label.configure(image=ctk_image, text="")
        label._icon_ref = ctk_image
        return ctk_image

    label.configure(
        image=None,
        text=placeholder,
        font=("Segoe UI", 32, "bold"),
        text_color=COLORS["text_muted"],
    )
    label._icon_ref = None
    return None
