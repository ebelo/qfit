from __future__ import annotations

from .workflow_shell_presenter import (
    DockWizardProgress,
    DockWorkflowProgress,
    WorkflowShellPresenter,
)

WizardShellPresenter = WorkflowShellPresenter
"""Compatibility alias for pre-#805 wizard shell presenter imports."""

__all__ = [
    "DockWorkflowProgress",
    "DockWizardProgress",
    "WorkflowShellPresenter",
    "WizardShellPresenter",
]
