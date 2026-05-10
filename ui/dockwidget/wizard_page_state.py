"""Compatibility re-exports for pre-#805 wizard page-state imports."""

from __future__ import annotations

from .workflow_page_state import (
    DockWorkflowActionCallbacks,
    WorkflowPageStateSnapshots,
    build_workflow_page_states_from_facts,
    completed_prefix_facts,
    connect_optional_signal,
)

WizardActionCallbacks = DockWorkflowActionCallbacks
"""Compatibility alias for pre-#805 wizard page-state callers."""
WizardPageStateSnapshots = WorkflowPageStateSnapshots
"""Compatibility alias for pre-#805 wizard page-state callers."""
build_wizard_page_states_from_facts = build_workflow_page_states_from_facts
"""Compatibility alias for pre-#805 wizard page-state callers."""

__all__ = [
    "DockWorkflowActionCallbacks",
    "WorkflowPageStateSnapshots",
    "WizardActionCallbacks",
    "WizardPageStateSnapshots",
    "build_workflow_page_states_from_facts",
    "build_wizard_page_states_from_facts",
    "completed_prefix_facts",
    "connect_optional_signal",
]
