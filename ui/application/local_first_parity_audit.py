from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from .local_first_control_moves import (
    LOCAL_FIRST_CONTROL_MOVES,
    LOCAL_FIRST_WIDGET_MOVES,
)

ISSUE_805_REQUIRED_AREAS = (
    "mapbox_background_map",
    "activity_visualization_options",
    "map_filters",
    "data_storage_settings",
    "analysis_controls",
    "atlas_export_controls",
    "connection_settings_controls",
)

_CONTROL_MOVE_AREAS = {
    "activity_preview": "activity_visualization_options",
    "backfill_routes": "data_storage_settings",
    "map_filters": "map_filters",
    "atlas_pdf": "atlas_export_controls",
    "strava_credentials": "connection_settings_controls",
    "basemap": "mapbox_background_map",
    "storage": "data_storage_settings",
}

_WIDGET_MOVE_AREAS = {
    "activity_style": "activity_visualization_options",
    "analysis_temporal": "analysis_controls",
}


@dataclass(frozen=True)
class LocalFirstParitySurface:
    """One audited local-first surface for a #805 acceptance area."""

    key: str
    issue_area: str
    local_first_page: str
    surface_type: str
    required_widget_attrs: tuple[str, ...] = ()
    optional_widget_attrs: tuple[str, ...] = ()
    action_names: tuple[str, ...] = ()


_ACTION_SURFACES = (
    LocalFirstParitySurface(
        key="data_actions",
        issue_area="data_storage_settings",
        local_first_page="data",
        surface_type="page_actions",
        action_names=(
            "syncRequested",
            "storeRequested",
            "syncRoutesRequested",
            "clearDatabaseRequested",
            "loadActivitiesRequested",
        ),
    ),
    LocalFirstParitySurface(
        key="map_actions",
        issue_area="map_filters",
        local_first_page="map",
        surface_type="page_actions",
        action_names=("loadLayersRequested", "applyFiltersRequested"),
    ),
    LocalFirstParitySurface(
        key="analysis_actions",
        issue_area="analysis_controls",
        local_first_page="analysis",
        surface_type="page_actions",
        action_names=(
            "runAnalysisRequested",
            "clearAnalysisRequested",
            "analysisModeChanged",
        ),
    ),
    LocalFirstParitySurface(
        key="atlas_actions",
        issue_area="atlas_export_controls",
        local_first_page="atlas",
        surface_type="page_actions",
        action_names=("exportAtlasRequested", "atlasDocumentSettingsChanged"),
    ),
    LocalFirstParitySurface(
        key="settings_configuration_action",
        issue_area="connection_settings_controls",
        local_first_page="settings",
        surface_type="page_actions",
        action_names=("configureRequested",),
    ),
)


def build_issue805_local_first_parity_surfaces() -> tuple[LocalFirstParitySurface, ...]:
    """Return the audited local-first surfaces for the #805 checklist."""

    surfaces: list[LocalFirstParitySurface] = []
    for move in LOCAL_FIRST_WIDGET_MOVES:
        surfaces.append(
            LocalFirstParitySurface(
                key=move.key,
                issue_area=_issue_area_for_move(
                    _WIDGET_MOVE_AREAS,
                    move.key,
                    "LOCAL_FIRST_WIDGET_MOVES",
                ),
                local_first_page=_content_attr_page(move.content_attr),
                surface_type="widget_move",
                required_widget_attrs=move.required_widget_attrs,
                optional_widget_attrs=_flatten_optional_widgets(move),
            )
        )
    for move in LOCAL_FIRST_CONTROL_MOVES:
        surfaces.append(
            LocalFirstParitySurface(
                key=move.key,
                issue_area=_issue_area_for_move(
                    _CONTROL_MOVE_AREAS,
                    move.key,
                    "LOCAL_FIRST_CONTROL_MOVES",
                ),
                local_first_page=_content_attr_page(move.content_attr),
                surface_type="control_move",
                required_widget_attrs=move.required_widget_attrs,
            )
        )
    surfaces.extend(_ACTION_SURFACES)
    return tuple(surfaces)


def issue805_local_first_coverage_by_area() -> dict[str, tuple[str, ...]]:
    """Map #805 issue areas to the local-first surfaces that cover them."""

    coverage: defaultdict[str, list[str]] = defaultdict(list)
    for surface in build_issue805_local_first_parity_surfaces():
        coverage[surface.issue_area].append(surface.key)
    return {
        area: tuple(coverage[area])
        for area in ISSUE_805_REQUIRED_AREAS
    }


def missing_issue805_local_first_areas() -> tuple[str, ...]:
    """Return #805 areas that still lack an audited local-first surface."""

    coverage = issue805_local_first_coverage_by_area()
    return tuple(area for area in ISSUE_805_REQUIRED_AREAS if not coverage[area])


def _issue_area_for_move(
    area_map: dict[str, str],
    key: str,
    inventory_name: str,
) -> str:
    try:
        return area_map[key]
    except KeyError as exc:
        raise ValueError(
            f"No #805 parity area mapping for {inventory_name} key {key!r}"
        ) from exc


def _content_attr_page(content_attr: str) -> str:
    pages = {
        "sync_content": "data",
        "map_content": "map",
        "analysis_content": "analysis",
        "atlas_content": "atlas",
        "settings_content": "settings",
    }
    try:
        return pages[content_attr]
    except KeyError as exc:
        raise ValueError(
            f"No local-first page mapping for content_attr {content_attr!r}"
        ) from exc


def _flatten_optional_widgets(move) -> tuple[str, ...]:
    optional_widgets: list[str] = []
    for group in move.optional_widget_groups:
        optional_widgets.extend(group)
    optional_widgets.extend(move.optional_widget_attrs)
    optional_widgets.extend(move.show_widget_attrs_after_move)
    return tuple(optional_widgets)


__all__ = [
    "ISSUE_805_REQUIRED_AREAS",
    "LocalFirstParitySurface",
    "build_issue805_local_first_parity_surfaces",
    "issue805_local_first_coverage_by_area",
    "missing_issue805_local_first_areas",
]
