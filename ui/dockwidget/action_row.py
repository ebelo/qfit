from __future__ import annotations

from collections.abc import Iterable

from qfit.ui.tokens import (
    COLOR_ACCENT,
    COLOR_ACCENT_DARK,
    COLOR_HOVER,
    COLOR_MUTED,
    COLOR_SEPARATOR,
    COLOR_TEXT,
)

from ._qt_compat import import_qt_module

_qtcore = import_qt_module("qgis.PyQt.QtCore", "PyQt5.QtCore", ("Qt",))
_qtwidgets = import_qt_module(
    "qgis.PyQt.QtWidgets",
    "PyQt5.QtWidgets",
    ("QHBoxLayout", "QSizePolicy", "QToolButton", "QWidget"),
)

Qt = _qtcore.Qt
QHBoxLayout = _qtwidgets.QHBoxLayout
QSizePolicy = _qtwidgets.QSizePolicy
QToolButton = _qtwidgets.QToolButton
QWidget = _qtwidgets.QWidget


class WizardActionRow(QWidget):
    """Compact action container for one wizard page CTA area."""

    def __init__(self, buttons: Iterable[QToolButton] = (), parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("qfitWizardActionRow")
        self._layout = self._build_layout()
        for button in buttons:
            self.add_button(button)

    def add_button(self, button: QToolButton) -> None:
        """Append an action button and let Qt re-parent it into the row."""

        self._layout.addWidget(button)

    def outer_layout(self):
        """Expose the row layout for adapter wiring and pure tests."""

        return self._layout

    def _build_layout(self):
        layout = QHBoxLayout(self)
        if hasattr(layout, "setObjectName"):
            layout.setObjectName("qfitWizardActionRowLayout")
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(8)
        return layout


def build_wizard_action_row(
    *buttons: QToolButton,
    parent=None,
    object_name: str = "qfitWizardActionRow",
) -> WizardActionRow:
    """Build a scoped action row for wizard page buttons."""

    row = WizardActionRow(buttons, parent=parent)
    row.setObjectName(object_name)
    return row


def style_primary_action_button(
    button: QToolButton,
    *,
    action_name: str,
) -> QToolButton:
    """Mark a wizard button as the one primary CTA for its page."""

    button.setProperty("primaryAction", action_name)
    button.setProperty("wizardActionRole", "primary")
    _apply_button_chrome(button, primary=True)
    return button


def style_secondary_action_button(
    button: QToolButton,
    *,
    action_name: str,
) -> QToolButton:
    """Mark a wizard button as a secondary page action."""

    button.setProperty("secondaryAction", action_name)
    button.setProperty("wizardActionRole", "secondary")
    _apply_button_chrome(button, primary=False)
    return button


def set_wizard_action_availability(
    button: QToolButton,
    *,
    enabled: bool,
    tooltip: str = "",
) -> QToolButton:
    """Apply a wizard-specific availability state to an action button.

    The tooltip is only shown while the action is blocked; available actions
    clear it so stale prerequisite copy does not linger after state refreshes.
    """

    button.setEnabled(enabled)
    action_availability = "available" if enabled else "blocked"
    button.setProperty("wizardActionAvailability", action_availability)
    button.setToolTip("" if enabled else tooltip)
    return button


def _apply_button_chrome(button: QToolButton, *, primary: bool) -> None:
    if hasattr(button, "setToolButtonStyle"):
        button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
    if hasattr(button, "setSizePolicy"):
        button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    if hasattr(button, "setCursor"):
        button.setCursor(Qt.PointingHandCursor)
    if hasattr(button, "setStyleSheet"):
        button.setStyleSheet(_button_stylesheet(primary=primary))


def _button_stylesheet(*, primary: bool) -> str:
    if primary:
        return (
            "QToolButton { "
            f"background: {COLOR_ACCENT}; "
            "color: white; "
            f"border: 1px solid {COLOR_ACCENT_DARK}; "
            "border-radius: 6px; "
            "padding: 5px 10px; "
            "font-weight: 700; "
            "} "
            f"QToolButton:hover:enabled {{ background: {COLOR_ACCENT_DARK}; }} "
            "QToolButton:disabled { "
            f"background: {COLOR_SEPARATOR}; "
            f"border-color: {COLOR_SEPARATOR}; "
            f"color: {COLOR_MUTED}; "
            "}"
        )
    return (
        "QToolButton { "
        "background: transparent; "
        f"color: {COLOR_TEXT}; "
        f"border: 1px solid {COLOR_SEPARATOR}; "
        "border-radius: 6px; "
        "padding: 5px 10px; "
        "font-weight: 500; "
        "} "
        f"QToolButton:hover:enabled {{ background: {COLOR_HOVER}; }} "
        f"QToolButton:disabled {{ color: {COLOR_MUTED}; }}"
    )


__all__ = [
    "WizardActionRow",
    "build_wizard_action_row",
    "set_wizard_action_availability",
    "style_primary_action_button",
    "style_secondary_action_button",
]
