from __future__ import annotations

COLOR_BG = "#f3f3f3"
COLOR_PANEL = "#fafafa"
COLOR_GROUP_BORDER = "#c4c4c4"
COLOR_TEXT = "#202124"
COLOR_MUTED = "#6b6f76"
COLOR_ACCENT = "#589632"
COLOR_ACCENT_DARK = "#3f6e22"
COLOR_LINK = "#1a5fb4"
COLOR_DANGER = "#c01c28"
COLOR_WARN = "#b67204"
COLOR_INPUT_BORDER = "#b0b4ba"
COLOR_INPUT_BG = "#ffffff"
COLOR_SEPARATOR = "#dcdcdc"
COLOR_HOVER = "#e8e8e8"
COLOR_TITLE_BAR = "#e4e4e7"

PILL_TONES: dict[str, tuple[str, str]] = {
    "ok": ("#dcefd0", "#2e6318"),
    "info": ("#d6e7f7", "#124c8c"),
    "warn": ("#fbe7c3", "#7a4f00"),
    "danger": ("#f6d4d4", "#8a121b"),
    "muted": ("#eef0f2", "#6b6f76"),
    "neutral": ("#e4e4e7", "#3f3f46"),
}

PRIMARY_BTN_QSS = """
QPushButton[role="primary"] {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 #68ad3e, stop:1 #4e8a2b);
    color: white; font-weight: 600;
    border: 1px solid #3f6e22; border-radius: 2px;
    padding: 4px 12px; min-height: 22px;
}
QPushButton[role="primary"]:hover { background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 #72ba45, stop:1 #579530); }
QPushButton[role="primary"]:disabled { background: #b0c9a0; border-color: #8aaa78; }
""".strip()


def pill_tone_palette(tone: str) -> tuple[str, str]:
    """Return the background/foreground palette for a named pill tone."""

    try:
        return PILL_TONES[tone]
    except KeyError as exc:
        known = ", ".join(sorted(PILL_TONES))
        raise ValueError(f"Unknown pill tone {tone!r}; expected one of: {known}") from exc


__all__ = [
    "COLOR_ACCENT",
    "COLOR_ACCENT_DARK",
    "COLOR_BG",
    "COLOR_DANGER",
    "COLOR_GROUP_BORDER",
    "COLOR_HOVER",
    "COLOR_INPUT_BG",
    "COLOR_INPUT_BORDER",
    "COLOR_LINK",
    "COLOR_MUTED",
    "COLOR_PANEL",
    "COLOR_SEPARATOR",
    "COLOR_TEXT",
    "COLOR_TITLE_BAR",
    "COLOR_WARN",
    "PILL_TONES",
    "PRIMARY_BTN_QSS",
    "pill_tone_palette",
]
