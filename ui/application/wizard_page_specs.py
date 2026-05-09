from __future__ import annotations

from collections.abc import Sequence

from .dock_workflow_sections import DockWorkflowSection, WIZARD_WORKFLOW_STEPS
from .workflow_page_specs import (
    DockWorkflowPageSpec,
    build_default_workflow_page_specs,
)

DockWizardPageSpec = DockWorkflowPageSpec
"""Compatibility alias for pre-#805 wizard-named page spec callers."""


def build_default_wizard_page_specs(
    *,
    workflow_steps: Sequence[DockWorkflowSection] | None = None,
) -> tuple[DockWizardPageSpec, ...]:
    """Compatibility wrapper for the workflow-named page spec builder."""

    steps = WIZARD_WORKFLOW_STEPS if workflow_steps is None else tuple(workflow_steps)
    return build_default_workflow_page_specs(workflow_steps=steps)


__all__ = ["DockWizardPageSpec", "build_default_wizard_page_specs"]
