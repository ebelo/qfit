from __future__ import annotations

from typing import Protocol

from ._qt_compat import import_qt_module

_qtcore = import_qt_module("qgis.PyQt.QtCore", "PyQt5.QtCore", ("Qt",))
_qtwidgets = import_qt_module(
    "qgis.PyQt.QtWidgets",
    "PyQt5.QtWidgets",
    ("QDockWidget", "QWidget"),
)

Qt = _qtcore.Qt
QDockWidget = _qtwidgets.QDockWidget
QWidget = _qtwidgets.QWidget

WORKFLOW_DOCK_OBJECT_NAME = "qfitWizardDockWidget"
WORKFLOW_DOCK_TITLE = "qfit"
WORKFLOW_DOCK_ALLOWED_AREAS = Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea
WORKFLOW_DOCK_FEATURES = (
    QDockWidget.DockWidgetClosable
    | QDockWidget.DockWidgetMovable
    | QDockWidget.DockWidgetFloatable
)

WIZARD_DOCK_OBJECT_NAME = WORKFLOW_DOCK_OBJECT_NAME
"""Compatibility alias for pre-#805 wizard dock callers."""
WIZARD_DOCK_TITLE = WORKFLOW_DOCK_TITLE
"""Compatibility alias for pre-#805 wizard dock callers."""
WIZARD_DOCK_ALLOWED_AREAS = WORKFLOW_DOCK_ALLOWED_AREAS
"""Compatibility alias for pre-#805 wizard dock callers."""
WIZARD_DOCK_FEATURES = WORKFLOW_DOCK_FEATURES
"""Compatibility alias for pre-#805 wizard dock callers."""


class WorkflowShellCompositionLike(Protocol):
    """Small structural protocol for dock-hostable workflow compositions."""

    shell: QWidget


WizardShellCompositionLike = WorkflowShellCompositionLike
"""Compatibility alias for pre-#805 wizard dock callers."""


class WorkflowDockWidget(QDockWidget):
    """QDockWidget host for the local-first workflow shell composition.

    The visible dock is converging on the local-first workflow surface while
    preserving stable Qt object names and thin wizard-named import aliases for
    older callers during #805.
    """

    def __init__(
        self,
        composition: WorkflowShellCompositionLike,
        *,
        parent=None,
        title: str = WORKFLOW_DOCK_TITLE,
    ) -> None:
        super().__init__(parent)
        self.composition: WorkflowShellCompositionLike | None = None
        self.setObjectName(WORKFLOW_DOCK_OBJECT_NAME)
        self.setWindowTitle(title)
        self.setFeatures(WORKFLOW_DOCK_FEATURES)
        self.setAllowedAreas(WORKFLOW_DOCK_ALLOWED_AREAS)
        self.set_composition(composition)

    def set_composition(self, composition: WorkflowShellCompositionLike) -> None:
        """Install or replace the hosted workflow composition shell."""

        shell = _composition_shell(composition)
        self.setWidget(shell)
        self.composition = composition


WizardDockWidget = WorkflowDockWidget
"""Compatibility alias for pre-#805 wizard dock callers."""


def build_workflow_dock_widget(
    composition: WorkflowShellCompositionLike,
    *,
    parent=None,
    title: str = WORKFLOW_DOCK_TITLE,
) -> WorkflowDockWidget:
    """Build the dock-level container for a reusable workflow composition."""

    return WorkflowDockWidget(composition, parent=parent, title=title)


build_wizard_dock_widget = build_workflow_dock_widget
"""Compatibility alias for pre-#805 wizard dock callers."""


def _composition_shell(composition: WorkflowShellCompositionLike):
    shell = getattr(composition, "shell", None)
    if shell is None:
        raise ValueError("Workflow dock compositions must expose a shell widget")
    return shell


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
