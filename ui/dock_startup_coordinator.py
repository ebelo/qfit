from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DockStartupResult:
    performed_steps: tuple[str, ...]


class DockStartupCoordinator:
    """Coordinate top-level dock-widget startup without moving lower-level UI methods."""

    def __init__(self, dock_widget, *, workflow_section_coordinator):
        self.dock_widget = dock_widget
        self.workflow_section_coordinator = workflow_section_coordinator

    def run(self) -> DockStartupResult:
        dock = self.dock_widget
        performed_steps: list[str] = []

        dock.setFeatures(dock.DEFAULT_DOCK_FEATURES)
        performed_steps.append("set_features")

        dock.setAllowedAreas(dock.STARTUP_ALLOWED_AREAS)
        performed_steps.append("set_allowed_areas")

        self.workflow_section_coordinator.configure_starting_sections()
        performed_steps.append("configure_starting_sections")

        dock._remove_stale_qfit_layers()
        performed_steps.append("remove_stale_qfit_layers")

        dock._apply_contextual_help()
        performed_steps.append("apply_contextual_help")

        dock._configure_background_preset_options()
        performed_steps.append("configure_background_preset_options")

        dock._configure_detailed_route_filter_options()
        performed_steps.append("configure_detailed_route_filter_options")

        dock._configure_detailed_route_strategy_options()
        performed_steps.append("configure_detailed_route_strategy_options")

        dock._configure_preview_sort_options()
        performed_steps.append("configure_preview_sort_options")

        dock._configure_temporal_mode_options()
        performed_steps.append("configure_temporal_mode_options")

        dock._configure_analysis_mode_options()
        performed_steps.append("configure_analysis_mode_options")

        dock._load_settings()
        performed_steps.append("load_settings")

        dock._set_default_dates()
        performed_steps.append("set_default_dates")

        dock._wire_events()
        performed_steps.append("wire_events")

        self.workflow_section_coordinator.configure_workflow_sections()
        performed_steps.append("configure_workflow_sections")

        dock._refresh_activity_preview()
        performed_steps.append("refresh_activity_preview")

        dock._update_connection_status()
        performed_steps.append("update_connection_status")

        return DockStartupResult(performed_steps=tuple(performed_steps))
