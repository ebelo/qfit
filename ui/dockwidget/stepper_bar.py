from __future__ import annotations

from importlib import import_module
from typing import Sequence

from qfit.ui.application.dock_workflow_sections import WIZARD_WORKFLOW_STEPS
from qfit.ui.application.stepper_presenter import (
    STEPPER_STATE_CURRENT,
    STEPPER_STATE_DONE,
    STEPPER_STATE_LOCKED,
    STEPPER_STATE_UPCOMING,
)
from qfit.ui.tokens import COLOR_ACCENT, COLOR_HOVER, COLOR_MUTED, COLOR_SEPARATOR, COLOR_TEXT

STEPPER_LABELS = tuple(section.title for section in WIZARD_WORKFLOW_STEPS)
STEPPER_STATES = frozenset(
    {
        STEPPER_STATE_DONE,
        STEPPER_STATE_CURRENT,
        STEPPER_STATE_UPCOMING,
        STEPPER_STATE_LOCKED,
    }
)


def _import_qt_module(qgis_module: str, pyqt_module: str, required_attributes: Sequence[str]):
    try:
        module = import_module(qgis_module)
    except ModuleNotFoundError as exc:
        if not str(exc).startswith("No module named 'qgis"):
            raise
        return import_module(pyqt_module)
    if all(hasattr(module, attribute) for attribute in required_attributes):
        return module
    # Some pure tests temporarily register tiny qgis.PyQt stubs. Fall back to
    # PyQt5 when those stubs do not provide every widget API needed here.
    return import_module(pyqt_module)


_qtcore = _import_qt_module("qgis.PyQt.QtCore", "PyQt5.QtCore", ("Qt", "pyqtSignal"))
_qtwidgets = _import_qt_module(
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


class StepperBar(QWidget):
    """Compact clickable five-step wizard stepper for the future dock shell."""

    stepRequested = pyqtSignal(int)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._buttons: list[QToolButton] = []
        self._connectors: list[QFrame] = []
        self._states = ["locked"] * len(STEPPER_LABELS)
        self._build_layout()
        self.setFixedHeight(36)
        self.setObjectName("qfitStepperBar")
        self.set_state(["current", "locked", "locked", "locked", "locked"])

    def set_state(self, states: Sequence[str]) -> None:
        """Apply one render state per wizard step."""

        validated_states = _validate_states(states)
        self._states = list(validated_states)
        for index, (button, state) in enumerate(zip(self._buttons, self._states, strict=True)):
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

    def _build_layout(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 10, 2)
        layout.setSpacing(4)
        for index, label in enumerate(STEPPER_LABELS):
            button = QToolButton(self)
            button.setObjectName(f"qfitStepperStep{index + 1}")
            button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
            button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            button.clicked.connect(lambda _checked=False, step_index=index: self._request_step(step_index))
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

    def _configure_button(self, button: QToolButton, index: int, state: str) -> None:
        button.setText(_button_text(index, state))
        button.setProperty("stepIndex", index)
        button.setProperty("wizardState", state)
        button.setEnabled(state != "locked")
        button.setCursor(Qt.ForbiddenCursor if state == "locked" else Qt.PointingHandCursor)
        button.setToolTip(STEPPER_LABELS[index])
        button.setStyleSheet(_button_stylesheet(state))

    def _configure_connectors(self) -> None:
        for index, connector in enumerate(self._connectors):
            previous_step_is_done = self._states[index] == "done"
            color = COLOR_ACCENT if previous_step_is_done else COLOR_SEPARATOR
            connector.setProperty("wizardState", "done" if previous_step_is_done else "upcoming")
            connector.setStyleSheet(f"QFrame#{connector.objectName()} {{ border: 0; background: {color}; }}")

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


def _button_text(index: int, state: str) -> str:
    prefix = "✓" if state == "done" else str(index + 1)
    return f"{prefix}  {STEPPER_LABELS[index]}"


def _button_stylesheet(state: str) -> str:
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
        "border-radius: 8px; "
        "padding: 2px 6px; "
        f"font-weight: {font_weight}; "
        "font-size: 9.5pt; "
        "} "
        f"QToolButton:hover:enabled {{ background: {COLOR_HOVER}; color: {COLOR_TEXT}; }}"    )


__all__ = ["STEPPER_LABELS", "STEPPER_STATES", "StepperBar"]
