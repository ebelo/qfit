from .workflow_shell_presenter import (
    DockWorkflowProgress,
    WorkflowShellPresenter,
)

DockWizardProgress = DockWorkflowProgress
"""Compatibility alias for pre-#805 wizard shell presenter imports."""
WizardShellPresenter = WorkflowShellPresenter
"""Compatibility alias for pre-#805 wizard shell presenter imports."""

__all__ = [
    "DockWizardProgress",
    "WizardShellPresenter",
]
