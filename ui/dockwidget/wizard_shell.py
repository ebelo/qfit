from __future__ import annotations

from .workflow_shell import FooterStatusBar as FooterStatusBar  # noqa: F401
from .workflow_shell import STEPPER_LABELS as STEPPER_LABELS  # noqa: F401
from .workflow_shell import WorkflowShell

WizardShell = WorkflowShell
"""Compatibility alias for pre-#805 wizard shell imports."""

__all__ = ["WizardShell"]
