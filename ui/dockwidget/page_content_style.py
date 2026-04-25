from __future__ import annotations

from qfit.ui.tokens import COLOR_MUTED, pill_tone_palette

_DETAIL_LABEL_QSS = f"QLabel {{ color: {COLOR_MUTED}; }}"
_SUMMARY_LABEL_QSS = (
    "QLabel { "
    f"color: {COLOR_MUTED}; "
    "padding: 1px 0; "
    "}"
)


def style_detail_label(label) -> None:
    """Apply muted explanatory text styling to a wizard page detail label."""

    label.setStyleSheet(_DETAIL_LABEL_QSS)


def style_summary_label(label) -> None:
    """Apply consistent compact summary styling for wizard page status facts."""

    label.setStyleSheet(_SUMMARY_LABEL_QSS)


def style_status_pill(label, *, active: bool) -> None:
    """Render a wizard page status label as an ok/warn token pill."""

    tone = "ok" if active else "warn"
    label.setProperty("tone", tone)
    label.setStyleSheet(_status_pill_stylesheet(tone, object_name=label.objectName()))


def _status_pill_stylesheet(tone: str, *, object_name: str) -> str:
    background, foreground = pill_tone_palette(tone)
    return (
        f"QLabel#{object_name} {{ "
        f"background: {background}; "
        f"color: {foreground}; "
        "border: 0; "
        "border-radius: 8px; "
        "padding: 1px 6px; "
        "font-weight: 600; "
        "}"
    )


__all__ = [
    "style_detail_label",
    "style_status_pill",
    "style_summary_label",
]
