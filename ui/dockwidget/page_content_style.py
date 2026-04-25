from __future__ import annotations

from qfit.ui.tokens import COLOR_MUTED
from qfit.ui.widgets.pill import set_pill_tone

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

    set_pill_tone(
        label,
        "ok" if active else "warn",
        object_name=label.objectName(),
    )


__all__ = [
    "style_detail_label",
    "style_status_pill",
    "style_summary_label",
]
