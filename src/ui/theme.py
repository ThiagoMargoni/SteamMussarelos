from __future__ import annotations

from PySide6.QtGui import QColor, QFont

COLORS = {
    "bg_dark": "#1b2838",
    "bg_medium": "#171a21",
    "bg_panel": "#1e2329",
    "bg_card": "#2a475e",
    "bg_card_running": "#1e4d2b",
    "bg_card_hover": "#3d6b8e",
    "bg_icon": "#0e1419",
    "accent": "#66c0f4",
    "accent_hover": "#8ed1f7",
    "text": "#dfe9f2",
    "text_dim": "#9aa3ad",
    "text_muted": "#6b7680",
    "success": "#59bf40",
    "success_hover": "#6fd655",
    "warning": "#e8b923",
    "danger": "#d94126",
    "danger_hover": "#f2553a",
    "running": "#59bf40",
    "border": "#3d4f61",
    "border_light": "#4f6b84",
}

ICON_SIZE = 96
CARD_HEIGHT = 120
CARD_RADIUS = 10
BTN_WIDTH = 128
BTN_HEIGHT = 36
PRIMARY_BTN_WIDTH = 110
PRIMARY_BTN_HEIGHT = 36
UNINSTALL_BTN = 36
UNINSTALL_ICON = 18
ICON_BTN = UNINSTALL_BTN
HEADER_HEIGHT = 64
DOWNLOAD_PANEL_HEIGHT = 168
DOWNLOAD_SCROLL_HEIGHT = 104

FONT_DISPLAY_PX = 22
FONT_TITLE_PX = 16
FONT_HEADING_PX = 15
FONT_BODY_PX = 13
FONT_CAPTION_PX = 12
FONT_SMALL_PX = 11
FONT_BUTTON_PX = 13

def qcolor(key: str) -> QColor:
    return QColor(COLORS[key])

def _font(pixel_size: int, bold: bool = False) -> QFont:
    f = QFont("Segoe UI")
    f.setPixelSize(pixel_size)
    f.setBold(bold)
    f.setHintingPreference(QFont.HintingPreference.PreferFullHinting)
    f.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
    return f

def font_display() -> QFont:
    return _font(FONT_DISPLAY_PX, True)

def font_title() -> QFont:
    return _font(FONT_TITLE_PX, True)

def font_heading() -> QFont:
    return _font(FONT_HEADING_PX, True)

def font_body() -> QFont:
    return _font(FONT_BODY_PX)

def font_body_bold() -> QFont:
    return _font(FONT_BODY_PX, True)

def font_caption() -> QFont:
    return _font(FONT_CAPTION_PX)

def font_small() -> QFont:
    return _font(FONT_SMALL_PX)

def font_button() -> QFont:
    return _font(FONT_BUTTON_PX, True)

def btn_style(
    bg: str,
    hover: str,
    fg: str,
    disabled_bg: str | None = None,
    radius: int = 8,
    align: str = "center",
) -> str:
    dis = disabled_bg or COLORS["border"]
    return f"""
    QPushButton {{
        background-color: {bg};
        color: {fg};
        border: none;
        border-radius: {radius}px;
        padding: 0 12px;
        outline: none;
        text-align: {align};
    }}
    QPushButton:hover {{
        background-color: {hover};
    }}
    QPushButton:pressed {{
        background-color: {hover};
    }}
    QPushButton:focus {{
        outline: none;
        border: none;
    }}
    QPushButton:disabled {{
        background-color: {dis};
        color: {COLORS["text_muted"]};
    }}
    """

def app_stylesheet() -> str:
    c = COLORS
    return f"""
    QMainWindow {{
        background-color: {c["bg_dark"]};
    }}
    QDialog {{
        background-color: {c["bg_dark"]};
        color: {c["text"]};
    }}
    QWidget#centralRoot {{
        background-color: {c["bg_dark"]};
    }}
    QWidget#libraryWrap, QWidget#downloadsWrap {{
        background-color: {c["bg_dark"]};
    }}
    QFrame#appHeader {{
        background-color: {c["bg_medium"]};
        border: none;
        border-radius: 0;
    }}
    QLabel {{
        background: transparent;
    }}
    QLineEdit {{
        background-color: {c["bg_panel"]};
        border: 1px solid {c["border"]};
        border-radius: 8px;
        padding: 5px 12px;
        color: {c["text"]};
        selection-background-color: {c["accent"]};
        selection-color: {c["bg_medium"]};
    }}
    QLineEdit:focus {{
        border: 1px solid {c["border_light"]};
    }}
    QFrame#libraryPanel {{
        background: transparent;
        border: none;
    }}
    QScrollArea#libraryScroll {{
        background: transparent;
        border: none;
    }}
    QWidget#libraryScrollInner {{
        background-color: {c["bg_panel"]};
        border: none;
    }}
    QScrollBar:vertical {{
        background: transparent;
        border: none;
        width: 14px;
        margin: 12px 4px 12px 0;
    }}
    QScrollBar::handle:vertical {{
        background: {c["border"]};
        border: none;
        border-radius: 7px;
        min-height: 40px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: {c["border_light"]};
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0;
        width: 0;
        background: none;
        border: none;
    }}
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
        background: none;
    }}
    QFrame#downloadPanel {{
        background-color: {c["bg_panel"]};
        border: 1px solid {c["border"]};
        border-radius: {CARD_RADIUS}px;
    }}
    QFrame#downloadRow {{
        background-color: {c["bg_card"]};
        border: 1px solid {c["border"]};
        border-radius: 8px;
    }}
    QProgressBar {{
        background-color: {c["border"]};
        border: none;
        border-radius: 8px;
        max-height: 16px;
        min-height: 16px;
    }}
    QProgressBar::chunk {{
        background-color: {c["accent"]};
        border-radius: 8px;
    }}
    """
