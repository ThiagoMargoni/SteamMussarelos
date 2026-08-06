from __future__ import annotations

from pathlib import Path

from PIL import Image
from PySide6.QtGui import QIcon, QPixmap

from src.ui.icon_loader import pil_to_pixmap
from src.ui.theme import UNINSTALL_ICON
from src.utils.paths import resolve_resource

_cache: dict[int, QIcon] = {}

def _load_trash_rgba() -> Image.Image:
    path = resolve_resource("assets", "trash.png")
    if path is None:
        path = Path(__file__).resolve().parents[2] / "assets" / "trash.png"
    img = Image.open(path)
    img.load()
    img = img.convert("RGBA")
    pixels = img.getdata()
    cleaned = []
    for r, g, b, a in pixels:
        if r < 40 and g < 40 and b < 40:
            cleaned.append((0, 0, 0, 0))
        else:
            cleaned.append((255, 255, 255, a if a > 0 else 255))
    img.putdata(cleaned)
    return img

def get_uninstall_icon(size: int = UNINSTALL_ICON) -> QIcon:
    cached = _cache.get(size)
    if cached is not None:
        return QIcon(cached)
    src = _load_trash_rgba()
    src.thumbnail((size, size), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    x = (size - src.width) // 2
    y = (size - src.height) // 2
    canvas.paste(src, (x, y), src)
    icon = QIcon(pil_to_pixmap(canvas))
    _cache[size] = icon
    return QIcon(icon)

def get_uninstall_pixmap(size: int = UNINSTALL_ICON) -> QPixmap:
    return get_uninstall_icon(size).pixmap(size, size)
