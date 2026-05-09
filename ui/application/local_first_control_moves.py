from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LocalFirstControlMove:
    """Legacy-backed control group that is explicitly surfaced in local-first UI."""

    key: str
    content_attr: str
    group_attr: str
    installed_attr: str
    installed_target_attr: str
    title: str | None = None
    show_after_move: bool = True
    layout_getter_attr: str = "outer_layout"
    parent_panel_attr: str | None = None


LOCAL_FIRST_CONTROL_MOVES: tuple[LocalFirstControlMove, ...] = (
    LocalFirstControlMove(
        key="advanced_fetch",
        content_attr="sync_content",
        group_attr="advancedFetchGroupBox",
        installed_attr="_local_first_advanced_fetch_controls_installed",
        installed_target_attr="_local_first_advanced_fetch_controls_installed_target",
    ),
    LocalFirstControlMove(
        key="activity_preview",
        content_attr="sync_content",
        group_attr="previewGroupBox",
        installed_attr="_local_first_activity_preview_controls_installed",
        installed_target_attr="_local_first_activity_preview_controls_installed_target",
        title="Fetched activity preview",
    ),
    LocalFirstControlMove(
        key="backfill_routes",
        content_attr="sync_content",
        group_attr="backfillMissingDetailedRoutesButton",
        installed_attr="_local_first_backfill_controls_installed",
        installed_target_attr="_local_first_backfill_controls_installed_target",
        show_after_move=False,
    ),
    LocalFirstControlMove(
        key="map_filters",
        content_attr="map_content",
        group_attr="filterGroupBox",
        installed_attr="_local_first_filter_controls_installed",
        installed_target_attr="_local_first_filter_controls_installed_target",
        title="Map filters",
        layout_getter_attr="filter_controls_layout",
        parent_panel_attr="filter_controls_panel",
    ),
    LocalFirstControlMove(
        key="atlas_pdf",
        content_attr="atlas_content",
        group_attr="atlasPdfGroupBox",
        installed_attr="_local_first_atlas_pdf_controls_installed",
        installed_target_attr="_local_first_atlas_pdf_controls_installed_target",
        title="PDF output",
    ),
    LocalFirstControlMove(
        key="basemap",
        content_attr="connection_content",
        group_attr="backgroundGroupBox",
        installed_attr="_local_first_basemap_controls_installed",
        installed_target_attr="_local_first_basemap_controls_installed_target",
        title="Mapbox basemap",
    ),
    LocalFirstControlMove(
        key="storage",
        content_attr="connection_content",
        group_attr="outputGroupBox",
        installed_attr="_local_first_storage_controls_installed",
        installed_target_attr="_local_first_storage_controls_installed_target",
        title="Data storage",
    ),
)


def local_first_control_move_for_key(key: str) -> LocalFirstControlMove:
    """Return the local-first control move spec for a supported control area."""

    for move in LOCAL_FIRST_CONTROL_MOVES:
        if move.key == key:
            return move
    raise KeyError(key)


def local_first_control_move_keys() -> tuple[str, ...]:
    """Return stable audit keys for legacy-backed local-first control moves."""

    return tuple(move.key for move in LOCAL_FIRST_CONTROL_MOVES)


__all__ = [
    "LOCAL_FIRST_CONTROL_MOVES",
    "LocalFirstControlMove",
    "local_first_control_move_for_key",
    "local_first_control_move_keys",
]
