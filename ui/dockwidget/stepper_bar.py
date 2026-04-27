from __future__ import annotations

from typing import Sequence

from qfit.ui.application.dock_workflow_sections import WIZARD_WORKFLOW_STEPS
from qfit.ui.application.stepper_presenter import (
    STEPPER_STATE_CURRENT,
    STEPPER_STATE_DONE,
    STEPPER_STATE_LOCKED,
    STEPPER_STATE_UPCOMING,
)
from qfit.ui.tokens import COLOR_ACCENT, COLOR_HOVER, COLOR_MUTED, COLOR_SEPARATOR, COLOR_TEXT

from ._qt_compat import import_qt_module

STEPPER_LABELS = tuple(section.title for section in WIZARD_WORKFLOW_STEPS)
STEPPER_STATES = frozenset(
    {
        STEPPER_STATE_DONE,
        STEPPER_STATE_CURRENT,
        STEPPER_STATE_UPCOMING,
        STEPPER_STATE_LOCKED,
    }
)


_qtcore = import_qt_module("qgis.PyQt.QtCore", "PyQt5.QtCore", ("Qt", "pyqtSignal"))
_qtwidgets = import_qt_module(
    "qgis.PyQt.QtWidgets",
    "PyQt5.QtWidgets",
    ("QFrame", "QHBoxLayout", "QSizePolicy", "QToolButton", "QWidget"),
)

Qt = _qtcore.Qt
pyqtSignal = _qtcore.pyqtSignal
QFrame = _qtwidgets.QFrame
QHBoxLayout = _qtwidgets.QHBoxLayout
QSizePolicy = _qtwidgets.QSizePolicy
QToolButton = _qtwidgets.QToolButton
QWidget = _qtwidgets.QWidget

STEPPER_COMPACT_WIDTH = 520
STEPPER_WIDE_HEIGHT = 36
STEPPER_COMPACT_HEIGHT = 32


class StepperBar(QWidget):
    """Compact clickable five-step wizard stepper for the future dock shell."""

    stepRequested = pyqtSignal(int)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._buttons: list[QToolButton] = []
        self._connectors: list[QFrame] = []
        self._states = ["locked"] * len(STEPPER_LABELS)
        self._compact = False
        self._layout = self._build_layout()
        self.setFixedHeight(STEPPER_WIDE_HEIGHT)
        self.setObjectName("qfitStepperBar")
        self.setProperty("responsiveMode", "wide")
        self.set_state(["current", "locked", "locked", "locked", "locked"])

    def set_responsive_width(self, width: int) -> None:
        """Compact step labels when the dock becomes too narrow for full copy."""

        compact = int(width) < STEPPER_COMPACT_WIDTH
        if compact == self._compact:
            return
        self._compact = compact
        self.setProperty("responsiveMode", "compact" if compact else "wide")
        self.setFixedHeight(STEPPER_COMPACT_HEIGHT if compact else STEPPER_WIDE_HEIGHT)
        self._layout.setContentsMargins(2 if compact else 4, 2, 6 if compact else 10, 2)
        self._layout.setSpacing(2 if compact else 4)
        connector_width = 4 if compact else 8
        for connector in self._connectors:
            connector.setFixedWidth(connector_width)
        self.set_state(self._states)

    def resizeEvent(self, event) -> None:  # noqa: N802
        """Track live Qt resizes so the stepper does not enforce a wide dock."""

        size = event.size() if hasattr(event, "size") else None
        if size is not None and hasattr(size, "width"):
            self.set_responsive_width(size.width())
        elif hasattr(self, "width"):
            self.set_responsive_width(self.width())
        parent_resize = getattr(super(), "resizeEvent", None)
        if parent_resize is not None:
            parent_resize(event)

    def set_state(self, states: Sequence[str]) -> None:
        """Apply one render state per wizard step."""

        validated_states = _validate_states(states)
        self._states = list(validated_states)
        for index, (button, state) in enumerate(zip(self._buttons, self._states)):
            self._configure_button(button, index, state)
        self._configure_connectors()

    def set_current(self, index: int) -> None:
        """Mark one step current and leave all other steps dim/upcoming.

        Use ``set_state`` instead when navigation must preserve completed-step
        history.
        """

        if index < 0 or index >= len(STEPPER_LABELS):
            raise ValueError(f"Stepper index {index} is outside 0..{len(STEPPER_LABELS) - 1}")
        self.set_state(["current" if step_index == index else "upcoming" for step_index in range(len(STEPPER_LABELS))])

    def states(self) -> tuple[str, ...]:
        """Return the currently rendered states in step order."""

        return tuple(self._states)

    def step_buttons(self) -> tuple[QToolButton, ...]:
        """Return the step buttons for adapter wiring and tests."""

        return tuple(self._buttons)

    def _build_layout(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 10, 2)
        layout.setSpacing(4)
        for index, _label in enumerate(STEPPER_LABELS):
            button = QToolButton(self)
            button.setObjectName(f"qfitStepperStep{index + 1}")
            button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
            button.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
            if hasattr(button, "setMinimumWidth"):
                button.setMinimumWidth(0)
            button.clicked.connect(
                lambda _checked=False, step_index=index: self._request_step(step_index)
            )
            self._buttons.append(button)
            layout.addWidget(button)
            if index < len(STEPPER_LABELS) - 1:
                connector = QFrame(self)
                connector.setObjectName(f"qfitStepperConnector{index + 1}")
                connector.setFrameShape(QFrame.HLine)
                connector.setFrameShadow(QFrame.Plain)
                connector.setFixedWidth(8)
                connector.setFixedHeight(1)
                self._connectors.append(connector)
                layout.addWidget(connector)
        return layout

    def _configure_button(self, button: QToolButton, index: int, state: str) -> None:
        button.setText(_button_text(index, state, compact=self._compact))
        button.setProperty("stepIndex", index)
        button.setProperty("wizardState", state)
        button.setProperty("responsiveMode", "compact" if self._compact else "wide")
        button.setEnabled(state != "locked")
        button.setCursor(
            Qt.ForbiddenCursor if state == "locked" else Qt.PointingHandCursor
        )
        button.setToolTip(_button_tooltip(index, state))
        button.setStyleSheet(_button_stylesheet(state, compact=self._compact))

    def _configure_connectors(self) -> None:
        for index, connector in enumerate(self._connectors):
            previous_step_is_done = self._states[index] == "done"
            color = COLOR_ACCENT if previous_step_is_done else COLOR_SEPARATOR
            connector.setProperty(
                "wizardState", "done" if previous_step_is_done else "upcoming"
            )
            connector.setStyleSheet(
                f"QFrame#{connector.objectName()} {{ border: 0; background: {color}; }}"
            )

    def _request_step(self, index: int) -> None:
        if self._states[index] != "locked":
            self.stepRequested.emit(index)


def _validate_states(states: Sequence[str]) -> tuple[str, ...]:
    values = tuple(states)
    if len(values) != len(STEPPER_LABELS):
        raise ValueError(f"StepperBar requires {len(STEPPER_LABELS)} states; got {len(values)}")
    invalid_states = sorted(set(values) - STEPPER_STATES)
    if invalid_states:
        known = ", ".join(sorted(STEPPER_STATES))
        raise ValueError(f"Unknown stepper state(s): {', '.join(invalid_states)}; expected one of: {known}")
    return values


def _button_text(index: int, state: str, *, compact: bool = False) -> str:
    prefix = "✓" if state == "done" else str(index + 1)
    if compact:
        return prefix
    return f"{prefix}  {STEPPER_LABELS[index]}"


def _button_tooltip(index: int, state: str) -> str:
    label = STEPPER_LABELS[index]
    if state == "locked":
        if index == 0:
            return "This step is not yet available."
        prerequisite_index = index - 1
        if label == "Atlas PDF":
            prerequisite_index = 2
        previous_label = STEPPER_LABELS[prerequisite_index]
        return f"Complete {previous_label} before opening {label}."
    return label


def _button_stylesheet(state: str, *, compact: bool = False) -> str:
    if state == "done":
        background = "transparent"
        color = COLOR_TEXT
        border = "0"
        font_weight = "500"
    elif state == "current":
        background = COLOR_ACCENT
        color = "white"
        border = f"1px solid {COLOR_ACCENT}"
        font_weight = "700"
    elif state == "locked":
        background = "transparent"
        color = COLOR_MUTED
        border = "0"
        font_weight = "400"
    else:
        background = "transparent"
        color = COLOR_MUTED
        border = f"1px solid {COLOR_SEPARATOR}"
        font_weight = "400"
    return (
        "QToolButton { "
        f"background: {background}; "
        f"color: {color}; "
        f"border: {border}; "
        f"border-radius: {'6px' if compact else '8px'}; "
        f"padding: {'2px 4px' if compact else '2px 6px'}; "
        f"font-weight: {font_weight}; "
        f"font-size: {'9pt' if compact else '9.5pt'}; "
        "} "
        f"QToolButton:hover:enabled {{ background: {COLOR_HOVER}; color: {COLOR_TEXT}; }}"    )


__all__ = ["STEPPER_LABELS", "STEPPER_STATES", "StepperBar", "import_qt_module"]
