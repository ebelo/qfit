from __future__ import annotations

from collections.abc import Iterable

from qfit.ui.tokens import (
    COLOR_ACCENT,
    COLOR_ACCENT_DARK,
    COLOR_DANGER,
    COLOR_MUTED,
    COLOR_SEPARATOR,
    pill_tone_palette,
)

from ._qt_compat import import_qt_module

_qtcore = import_qt_module("qgis.PyQt.QtCore", "PyQt5.QtCore", ("Qt",))
_qtwidgets = import_qt_module(
    "qgis.PyQt.QtWidgets",
    "PyQt5.QtWidgets",
    ("QBoxLayout", "QHBoxLayout", "QSizePolicy", "QToolButton", "QWidget"),
)

Qt = _qtcore.Qt
QBoxLayout = _qtwidgets.QBoxLayout
QHBoxLayout = _qtwidgets.QHBoxLayout
QSizePolicy = _qtwidgets.QSizePolicy
QToolButton = _qtwidgets.QToolButton
QWidget = _qtwidgets.QWidget

ACTION_ROW_NARROW_WIDTH = 360
COLOR_DANGER_BG = pill_tone_palette("danger")[0]
WORKFLOW_ACTION_ROLE_PROPERTY = "workflowActionRole"
WIZARD_ACTION_ROLE_PROPERTY = "wizardActionRole"
WORKFLOW_ACTION_AVAILABILITY_PROPERTY = "workflowActionAvailability"
WIZARD_ACTION_AVAILABILITY_PROPERTY = "wizardActionAvailability"


class WorkflowActionRow(QWidget):
    """Compact action container for one workflow page CTA area."""

    def __init__(self, buttons: Iterable[QToolButton] = (), parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("qfitWizardActionRow")
        self._responsive_mode = "wide"
        self._layout = self._build_layout()
        self.setProperty("responsiveMode", "wide")
        for button in buttons:
            self.add_button(button)

    def add_button(self, button: QToolButton) -> None:
        """Append an action button and let Qt re-parent it into the row."""

        _allow_button_shrink(button)
        self._layout.addWidget(button)

    def set_responsive_width(self, width: int) -> None:
        """Stack page CTA rows when narrow docks cannot fit full labels."""

        narrow = int(width) < ACTION_ROW_NARROW_WIDTH
        mode = "narrow" if narrow else "wide"
        if mode == self._responsive_mode:
            return
        self._responsive_mode = mode
        self.setProperty("responsiveMode", mode)
        if hasattr(self._layout, "setDirection"):
            self._layout.setDirection(
                QBoxLayout.TopToBottom if narrow else QBoxLayout.LeftToRight
            )
        self._layout.setSpacing(6 if narrow else 8)

    def resizeEvent(self, event) -> None:  # noqa: N802
        """Keep the action row liquid as the dock width changes."""

        size = event.size() if hasattr(event, "size") else None
        if size is not None and hasattr(size, "width"):
            self.set_responsive_width(size.width())
        elif hasattr(self, "width"):
            self.set_responsive_width(self.width())
        parent_resize = getattr(super(), "resizeEvent", None)
        if parent_resize is not None:
            parent_resize(event)

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


def build_workflow_action_row(
    *buttons: QToolButton,
    parent=None,
    object_name: str = "qfitWizardActionRow",
) -> WorkflowActionRow:
    """Build a scoped action row for workflow page buttons."""

    row = WorkflowActionRow(buttons, parent=parent)
    row.setObjectName(object_name)
    return row


def style_primary_action_button(
    button: QToolButton,
    *,
    action_name: str,
) -> QToolButton:
    """Mark a workflow button as the one primary CTA for its page."""

    button.setProperty("primaryAction", action_name)
    set_workflow_action_role(button, role="primary")
    _apply_button_chrome(button, role="primary")
    return button


def style_secondary_action_button(
    button: QToolButton,
    *,
    action_name: str,
) -> QToolButton:
    """Mark a workflow button as a secondary page action."""

    button.setProperty("secondaryAction", action_name)
    set_workflow_action_role(button, role="secondary")
    _apply_button_chrome(button, role="secondary")
    return button


def style_destructive_action_button(
    button: QToolButton,
    *,
    action_name: str,
) -> QToolButton:
    """Mark a workflow button as a destructive page action."""

    button.setProperty("destructiveAction", action_name)
    set_workflow_action_role(button, role="destructive")
    _apply_button_chrome(button, role="destructive")
    return button


def set_workflow_action_role(
    button: QToolButton,
    *,
    role: str,
) -> QToolButton:
    """Tag a workflow action with canonical metadata plus legacy aliases."""

    button.setProperty(WORKFLOW_ACTION_ROLE_PROPERTY, role)
    # Keep the old dynamic property until the QSS/tests that still target the
    # pre-#805 wizard naming are fully retired.
    button.setProperty(WIZARD_ACTION_ROLE_PROPERTY, role)
    return button


def set_workflow_action_availability(
    button: QToolButton,
    *,
    enabled: bool,
    tooltip: str = "",
) -> QToolButton:
    """Apply a workflow-specific availability state to an action button.

    The tooltip is only shown while the action is blocked; available actions
    clear it so stale prerequisite copy does not linger after state refreshes.
    """

    button.setEnabled(enabled)
    action_availability = "available" if enabled else "blocked"
    button.setProperty(WORKFLOW_ACTION_AVAILABILITY_PROPERTY, action_availability)
    # Compatibility alias for remaining wizard-named selectors during #805.
    button.setProperty(WIZARD_ACTION_AVAILABILITY_PROPERTY, action_availability)
    button.setToolTip("" if enabled else tooltip)
    return button


WizardActionRow = WorkflowActionRow
build_wizard_action_row = build_workflow_action_row
set_wizard_action_role = set_workflow_action_role
set_wizard_action_availability = set_workflow_action_availability


def _allow_button_shrink(button: QToolButton) -> None:
    if hasattr(button, "setMinimumWidth"):
        button.setMinimumWidth(0)
    if hasattr(button, "setSizePolicy"):
        button.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)


def _apply_button_chrome(button: QToolButton, *, role: str = "primary") -> None:
    if hasattr(button, "setToolButtonStyle"):
        button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
    _allow_button_shrink(button)
    if hasattr(button, "setCursor"):
        button.setCursor(Qt.PointingHandCursor)
    if hasattr(button, "setStyleSheet"):
        button.setStyleSheet(_button_stylesheet(role=role))


def _button_stylesheet(*, role: str) -> str:
    if role == "primary":
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
    if role == "destructive":
        return (
            "QToolButton { "
            "background: transparent; "
            f"color: {COLOR_DANGER}; "
            "border: 1px solid transparent; "
            "border-radius: 6px; "
            "padding: 5px 10px; "
            "font-weight: 700; "
            "} "
            f"QToolButton:hover:enabled {{ background: {COLOR_DANGER_BG}; }} "
            f"QToolButton:disabled {{ color: {COLOR_MUTED}; }}"
        )
    if role == "secondary":
        return ""
    raise ValueError(f"Unknown workflow action button role: {role!r}")


__all__ = [
    "WorkflowActionRow",
    "WizardActionRow",
    "build_workflow_action_row",
    "build_wizard_action_row",
    "set_workflow_action_availability",
    "set_workflow_action_role",
    "set_wizard_action_availability",
    "set_wizard_action_role",
    "style_destructive_action_button",
    "style_primary_action_button",
    "style_secondary_action_button",
]
