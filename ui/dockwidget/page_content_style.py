from __future__ import annotations

from qfit.ui.tokens import (
    COLOR_DANGER,
    COLOR_MUTED,
    COLOR_WARN,
    SPACING_M,
    SPACING_S,
    pill_tone_palette,
)

from ._qt_compat import import_qt_module

_qtwidgets = import_qt_module(
    "qgis.PyQt.QtWidgets",
    "PyQt5.QtWidgets",
    ("QSizePolicy",),
)
_qtcore = import_qt_module(
    "qgis.PyQt.QtCore",
    "PyQt5.QtCore",
    ("Qt",),
)

QSizePolicy = _qtwidgets.QSizePolicy
Qt = _qtcore.Qt

PAGE_CONTENT_MARGINS = (0, 0, 0, 0)
LOCAL_FIRST_PAGE_MARGINS = (SPACING_M, SPACING_M, SPACING_M, SPACING_M)
LOCAL_FIRST_PAGE_SPACING = SPACING_M
PANEL_CONTENT_SPACING = SPACING_S

_INSTRUCTION_LABEL_QSS = f"QLabel {{ color: {COLOR_MUTED}; }}"
_FEEDBACK_LABEL_QSS = (
    "QLabel { "
    f"color: {COLOR_MUTED}; "
    "font-style: italic; "
    "padding: 1px 0; "
    "}"
)
_WARNING_LABEL_QSS = f"QLabel {{ color: {COLOR_WARN}; }}"
_ERROR_LABEL_QSS = f"QLabel {{ color: {COLOR_DANGER}; }}"


def style_detail_label(label) -> None:
    """Apply muted regular styling to instruction or helper text."""

    label.setStyleSheet(_INSTRUCTION_LABEL_QSS)


def style_feedback_label(label) -> None:
    """Apply muted italic styling to generated tool feedback text."""

    label.setStyleSheet(_FEEDBACK_LABEL_QSS)


def style_warning_label(label) -> None:
    """Apply regular warning styling to inline non-blocking problem text."""

    label.setStyleSheet(_WARNING_LABEL_QSS)


def style_error_label(label) -> None:
    """Apply regular error styling to inline blocking problem text."""

    label.setStyleSheet(_ERROR_LABEL_QSS)


def style_summary_label(label) -> None:
    """Compatibility wrapper for existing summary labels that are feedback.

    Deprecated: prefer ``style_feedback_label`` for new code.
    """

    style_feedback_label(label)


def configure_fluid_text_label(label) -> None:
    """Allow presentation text to wrap instead of widening the dock."""

    if hasattr(label, "setWordWrap"):
        label.setWordWrap(True)
    if hasattr(label, "setMinimumWidth"):
        label.setMinimumWidth(0)
    if hasattr(label, "setSizePolicy"):
        label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)


def configure_top_aligned_panel_layout(
    layout,
    *,
    margins: tuple[int, int, int, int] = PAGE_CONTENT_MARGINS,
    spacing: int = PANEL_CONTENT_SPACING,
) -> None:
    """Apply qfit panel spacing and top anchoring to a vertical layout."""

    if hasattr(layout, "setContentsMargins"):
        layout.setContentsMargins(*margins)
    if hasattr(layout, "setSpacing"):
        layout.setSpacing(spacing)
    align_top = getattr(Qt, "AlignTop", None)
    if align_top is not None and hasattr(layout, "setAlignment"):
        layout.setAlignment(align_top)


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
    "style_feedback_label",
    "style_warning_label",
    "style_error_label",
    "configure_top_aligned_panel_layout",
    "configure_fluid_text_label",
    "LOCAL_FIRST_PAGE_MARGINS",
    "LOCAL_FIRST_PAGE_SPACING",
    "PAGE_CONTENT_MARGINS",
    "PANEL_CONTENT_SPACING",
    "style_status_pill",
    "style_summary_label",
]
