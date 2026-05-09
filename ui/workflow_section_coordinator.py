from __future__ import annotations

from .application.local_first_backing_controls import (
    configure_local_first_backing_controls,
    configure_local_first_spinbox_unit_copy,
)


class WorkflowSectionCoordinator:
    """Compatibility shim for the retired workflow-section startup coordinator.

    Production startup now calls the local-first backing-control helpers directly.
    Keep this wrapper temporarily for older imports while #805 continues to retire
    the intermediate workflow-section path.
    """

    def __init__(self, dock_widget):
        self.dock_widget = dock_widget

    def configure_starting_sections(self) -> None:
        configure_local_first_backing_controls(self.dock_widget)

    def configure_spinbox_unit_copy(self) -> None:
        configure_local_first_spinbox_unit_copy(self.dock_widget)


__all__ = ["WorkflowSectionCoordinator"]
