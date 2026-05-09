from __future__ import annotations

from dataclasses import dataclass

from .application.local_first_backing_controls import (
    configure_local_first_backing_controls,
    configure_local_first_spinbox_unit_copy,
)
from .application.local_first_analysis_controls import (
    configure_local_first_analysis_mode_backing_controls,
)


@dataclass(frozen=True)
class DockStartupResult:
    performed_steps: tuple[str, ...]


class DockStartupCoordinator:
    """Coordinate top-level dock-widget startup without owning page policy."""

    def __init__(self, dock_widget):
        self.dock_widget = dock_widget

    def run(self) -> DockStartupResult:
        dock = self.dock_widget
        performed_steps: list[str] = []

        dock.setFeatures(dock.DEFAULT_DOCK_FEATURES)
        performed_steps.append("set_features")

        dock.setAllowedAreas(dock.STARTUP_ALLOWED_AREAS)
        performed_steps.append("set_allowed_areas")

        dock._ensure_wizard_settings()
        performed_steps.append("ensure_wizard_settings")

        configure_local_first_backing_controls(dock)
        performed_steps.append("configure_local_first_backing_controls")

        dock._remove_stale_qfit_layers()
        performed_steps.append("remove_stale_qfit_layers")

        dock._apply_contextual_help()
        performed_steps.append("apply_contextual_help")

        configure_local_first_spinbox_unit_copy(dock)
        performed_steps.append("configure_local_first_spinbox_unit_copy")

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

        configure_local_first_analysis_mode_backing_controls(dock)
        performed_steps.append("configure_analysis_mode_options")

        dock._load_settings()
        performed_steps.append("load_settings")

        dock._set_default_dates()
        performed_steps.append("set_default_dates")

        dock._wire_events()
        performed_steps.append("wire_events")

        dock._refresh_conditional_control_visibility()
        performed_steps.append("refresh_conditional_control_visibility")

        dock._refresh_activity_preview()
        performed_steps.append("refresh_activity_preview")

        dock._update_connection_status()
        performed_steps.append("update_connection_status")

        return DockStartupResult(performed_steps=tuple(performed_steps))
