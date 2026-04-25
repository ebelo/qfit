from __future__ import annotations

from importlib import import_module

from .tokens import pill_tone_palette

DEFAULT_PILL_OBJECT_NAME = "qfitPill"
DEFAULT_PILL_TONE = "muted"


def build_pill_stylesheet(
    tone: str,
    *,
    object_name: str = DEFAULT_PILL_OBJECT_NAME,
) -> str:
    """Build scoped QSS for a compact status pill."""

    background, foreground = pill_tone_palette(tone)
    return (
        f"QLabel#{object_name} {{ "
        f"background: {background}; "
        f"color: {foreground}; "
        "border: 0; "
        "border-radius: 8px; "
        "padding: 1px 6px; "
        "font-size: 10.5pt; "
        "font-weight: 600; "
        "}}"
    )


def configure_pill(
    widget,
    *,
    tone: str = DEFAULT_PILL_TONE,
    object_name: str = DEFAULT_PILL_OBJECT_NAME,
) -> None:
    """Apply shared pill object name, alignment, sizing, and tone styling."""

    qtcore = _import_qtcore()
    widget.setObjectName(object_name)
    widget.setAlignment(qtcore.Qt.AlignCenter)
    widget.setMinimumHeight(18)
    set_pill_tone(widget, tone, object_name=object_name)


def set_pill_tone(
    widget,
    tone: str,
    *,
    object_name: str | None = None,
) -> None:
    """Apply one of the shared pill tone palettes to an existing QLabel-like widget."""

    if object_name is None:
        object_name = widget.objectName() or DEFAULT_PILL_OBJECT_NAME
    widget.setProperty("tone", tone)
    widget.setStyleSheet(build_pill_stylesheet(tone, object_name=object_name))


def pill_tone(widget) -> str:
    """Return the active pill tone property for a configured pill widget."""

    return str(widget.property("tone") or "")


def make_pill(text: str = "", tone: str = DEFAULT_PILL_TONE, parent=None):
    """Create a QLabel-backed pill widget using the shared wizard design tokens."""

    widgets = _import_qtwidgets()
    label = widgets.QLabel(text, parent)
    configure_pill(label, tone=tone)
    return label


class Pill:  # noqa: N801
    """Constructor-style pill factory from the wizard spec.

    ``Pill(...)`` returns a configured QLabel-compatible widget while keeping
    Qt imports lazy so pure tests that temporarily stub ``qgis.PyQt`` remain
    safe. Use ``pill_tone(widget)`` and ``set_pill_tone(widget, tone)`` for the
    tone-specific API shared by returned widgets.
    """

    def __new__(cls, text: str = "", tone: str = DEFAULT_PILL_TONE, parent=None):
        return make_pill(text=text, tone=tone, parent=parent)


def _import_qtcore():
    try:
        return import_module("qgis.PyQt.QtCore")
    except ModuleNotFoundError as exc:
        if exc.name not in {"qgis", "qgis.PyQt", "qgis.PyQt.QtCore"}:
            raise
        return import_module("PyQt5.QtCore")


def _import_qtwidgets():
    try:
        return import_module("qgis.PyQt.QtWidgets")
    except ModuleNotFoundError as exc:
        if exc.name not in {"qgis", "qgis.PyQt", "qgis.PyQt.QtWidgets"}:
            raise
        return import_module("PyQt5.QtWidgets")


__all__ = [
    "DEFAULT_PILL_OBJECT_NAME",
    "DEFAULT_PILL_TONE",
    "Pill",
    "build_pill_stylesheet",
    "configure_pill",
    "make_pill",
    "pill_tone",
    "set_pill_tone",
]
