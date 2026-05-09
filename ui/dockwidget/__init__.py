"""Dock widget components for qfit workflow dock shells."""

from .stepper_bar import STEPPER_LABELS, STEPPER_STATES, StepperBar
from .workflow_shell_presenter import WorkflowShellPresenter

WizardShellPresenter = WorkflowShellPresenter
"""Compatibility alias for pre-#805 wizard shell presenter imports."""

__all__ = [
    "STEPPER_LABELS",
    "STEPPER_STATES",
    "StepperBar",
    "WorkflowShellPresenter",
    "WizardShellPresenter",
]
