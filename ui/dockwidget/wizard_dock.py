from __future__ import annotations

from .workflow_dock import (
    WORKFLOW_DOCK_ALLOWED_AREAS,
    WORKFLOW_DOCK_FEATURES,
    WORKFLOW_DOCK_OBJECT_NAME,
    WORKFLOW_DOCK_TITLE,
    WorkflowDockWidget,
    WorkflowShellCompositionLike,
    build_workflow_dock_widget,
)

WIZARD_DOCK_OBJECT_NAME = WORKFLOW_DOCK_OBJECT_NAME
"""Compatibility alias for pre-#805 wizard dock imports."""
WIZARD_DOCK_TITLE = WORKFLOW_DOCK_TITLE
"""Compatibility alias for pre-#805 wizard dock imports."""
WIZARD_DOCK_ALLOWED_AREAS = WORKFLOW_DOCK_ALLOWED_AREAS
"""Compatibility alias for pre-#805 wizard dock imports."""
WIZARD_DOCK_FEATURES = WORKFLOW_DOCK_FEATURES
"""Compatibility alias for pre-#805 wizard dock imports."""
WizardDockWidget = WorkflowDockWidget
"""Compatibility alias for pre-#805 wizard dock imports."""
WizardShellCompositionLike = WorkflowShellCompositionLike
"""Compatibility alias for pre-#805 wizard dock imports."""
build_wizard_dock_widget = build_workflow_dock_widget
"""Compatibility alias for pre-#805 wizard dock imports."""

__all__ = [
    "WORKFLOW_DOCK_ALLOWED_AREAS",
    "WORKFLOW_DOCK_FEATURES",
    "WORKFLOW_DOCK_OBJECT_NAME",
    "WORKFLOW_DOCK_TITLE",
    "WorkflowDockWidget",
    "WorkflowShellCompositionLike",
    "WIZARD_DOCK_ALLOWED_AREAS",
    "WIZARD_DOCK_FEATURES",
    "WIZARD_DOCK_OBJECT_NAME",
    "WIZARD_DOCK_TITLE",
    "WizardDockWidget",
    "WizardShellCompositionLike",
    "build_workflow_dock_widget",
    "build_wizard_dock_widget",
]
