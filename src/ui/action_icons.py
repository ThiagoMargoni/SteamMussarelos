from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw
from PySide6.QtGui import QIcon, QPixmap

from src.ui.icon_loader import pil_to_pixmap
from src.ui.theme import UNINSTALL_ICON
from src.utils.paths import resolve_resource

_trash_cache: dict[int, QIcon] = {}
_gear_cache: dict[int, QIcon] = {}

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

def _make_gear_rgba(size: int) -> Image.Image:
    scale = 4
    s = size * scale
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    cx = cy = s / 2
    teeth = 8
    outer = s * 0.44
    valley = s * 0.32
    hub = s * 0.20
    hole = s * 0.10
    color = (255, 255, 255, 255)
    pts: list[tuple[float, float]] = []
    steps = teeth * 4
    for i in range(steps):
        angle = (i / steps) * math.pi * 2 - math.pi / 2
        r = outer if (i % 4) < 2 else valley
        pts.append((cx + math.cos(angle) * r, cy + math.sin(angle) * r))
    draw.polygon(pts, fill=color)
    draw.ellipse([cx - hub, cy - hub, cx + hub, cy + hub], fill=color)
    draw.ellipse([cx - hole, cy - hole, cx + hole, cy + hole], fill=(0, 0, 0, 0))
    px = img.load()
    for y in range(s):
        for x in range(s):
            dx = x - cx
            dy = y - cy
            if dx * dx + dy * dy <= hole * hole:
                px[x, y] = (0, 0, 0, 0)
    return img.resize((size, size), Image.Resampling.LANCZOS)

def get_uninstall_icon(size: int = UNINSTALL_ICON) -> QIcon:
    cached = _trash_cache.get(size)
    if cached is not None:
        return QIcon(cached)
    src = _load_trash_rgba()
    src.thumbnail((size, size), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    x = (size - src.width) // 2
    y = (size - src.height) // 2
    canvas.paste(src, (x, y), src)
    icon = QIcon(pil_to_pixmap(canvas))
    _trash_cache[size] = icon
    return QIcon(icon)

def get_uninstall_pixmap(size: int = UNINSTALL_ICON) -> QPixmap:
    return get_uninstall_icon(size).pixmap(size, size)

def get_settings_icon(size: int = UNINSTALL_ICON) -> QIcon:
    cached = _gear_cache.get(size)
    if cached is not None:
        return QIcon(cached)
    icon = QIcon(pil_to_pixmap(_make_gear_rgba(size)))
    _gear_cache[size] = icon
    return QIcon(icon)
