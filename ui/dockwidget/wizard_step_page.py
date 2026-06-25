"""Compatibility re-exports for pre-#805 wizard step-page imports."""

from __future__ import annotations

# Workflow names remain direct aliases but are intentionally excluded from star exports.
from .step_page import (  # noqa: F401
    DockWorkflowPageSpec as DockWorkflowPageSpec,
    DockWizardPageSpec,
    StepPage as StepPage,
    WorkflowStepPage as WorkflowStepPage,
    WizardStepPage,
    apply_wizard_step_page_statuses,
    apply_workflow_step_page_statuses as apply_workflow_step_page_statuses,
    build_default_wizard_page_specs,
    build_default_workflow_page_specs as build_default_workflow_page_specs,
    build_wizard_step_pages,
    build_workflow_step_pages as build_workflow_step_pages,
    install_wizard_step_pages,
    install_workflow_step_pages as install_workflow_step_pages,
)

__all__ = [
    "DockWizardPageSpec",
    "WizardStepPage",
    "apply_wizard_step_page_statuses",
    "build_default_wizard_page_specs",
    "build_wizard_step_pages",
    "install_wizard_step_pages",
]
