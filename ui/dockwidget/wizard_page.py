from __future__ import annotations

from .workflow_page import (
    DockWorkflowPageSpec,
    PLACEHOLDER_HINT_RETIRED,
    WORKFLOW_PLACEHOLDER_HINT_PROPERTY,
    WorkflowPage,
    build_default_workflow_page_specs,
    build_workflow_pages,
    install_workflow_pages,
    set_workflow_placeholder_hint_state,
)

DockWizardPageSpec = DockWorkflowPageSpec
"""Compatibility alias for pre-#805 wizard page imports."""
build_default_wizard_page_specs = build_default_workflow_page_specs
"""Compatibility alias for pre-#805 wizard page imports."""
WizardPage = WorkflowPage
"""Compatibility alias for pre-#805 wizard page imports."""
build_wizard_pages = build_workflow_pages
"""Compatibility alias for pre-#805 wizard page imports."""
install_wizard_pages = install_workflow_pages
"""Compatibility alias for pre-#805 wizard page imports."""
WIZARD_PLACEHOLDER_HINT_PROPERTY = "wizardPlaceholderHint"
"""Compatibility alias for pre-#805 wizard placeholder metadata imports."""

__all__ = [
    "DockWorkflowPageSpec",
    "DockWizardPageSpec",
    "PLACEHOLDER_HINT_RETIRED",
    "WIZARD_PLACEHOLDER_HINT_PROPERTY",
    "WORKFLOW_PLACEHOLDER_HINT_PROPERTY",
    "WorkflowPage",
    "WizardPage",
    "build_default_workflow_page_specs",
    "build_default_wizard_page_specs",
    "build_workflow_pages",
    "build_wizard_pages",
    "install_workflow_pages",
    "install_wizard_pages",
    "set_workflow_placeholder_hint_state",
]
