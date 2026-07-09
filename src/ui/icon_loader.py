from __future__ import annotations

import io
import threading
from pathlib import Path
from typing import Callable, Optional

import customtkinter as ctk
import requests
from PIL import Image, ImageOps

from src.ui.theme import COLORS, ICON_SIZE

PROJECT_ROOT = Path(__file__).resolve().parents[2]

def load_game_icon(
    icon_path: Optional[str],
    on_ready: Callable[[Optional[ctk.CTkImage]], None],
    size: int = ICON_SIZE,
) -> None:
    def _work() -> None:
        try:
            image = _fetch_image(icon_path, size)
            if image is None:
                on_ready(None)
                return
            
            ctk_img = _to_ctk_image(image, size)
            on_ready(ctk_img)

        except Exception:
            on_ready(None)

    threading.Thread(target=_work, daemon=True).start()

def _fetch_image(icon_path: Optional[str], size: int) -> Optional[Image.Image]:
    if not icon_path:
        return None

    if icon_path.startswith("http"):
        resp = requests.get(icon_path, timeout=12)
        resp.raise_for_status()
        img = Image.open(io.BytesIO(resp.content))

    else:
        path = Path(icon_path)
        if not path.is_absolute():
            path = PROJECT_ROOT / icon_path

        if not path.exists():
            return None
        img = Image.open(path)

    return ImageOps.fit(img.convert("RGB"), (size, size), Image.Resampling.LANCZOS)

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
