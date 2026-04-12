from __future__ import annotations

from .background_map_messages import (
    build_background_map_cleared_status,
    build_background_map_loaded_status,
    build_styled_background_map_loaded_status,
    build_styled_visual_apply_status,
)


def build_filtered_visual_apply_status(filtered_count: int) -> str:
    return "Applied filters and styling ({count} matching activities)".format(
        count=filtered_count
    )


def build_visual_apply_status(
    has_layers: bool,
    apply_subset_filters: bool,
    filtered_count: int,
    wants_background: bool,
    background_loaded: bool,
) -> str:
    if apply_subset_filters and has_layers:
        return build_filtered_visual_apply_status(filtered_count)
    if has_layers and wants_background and background_loaded:
        return build_styled_background_map_loaded_status()
    if has_layers:
        return build_styled_visual_apply_status()
    if wants_background and background_loaded:
        return build_background_map_loaded_status()
    return build_background_map_cleared_status()


def append_visual_apply_temporal_note(status: str, temporal_note: str) -> str:
    if not temporal_note:
        return status
    return "{status}. {temporal_note}.".format(
        status=status, temporal_note=temporal_note
    )
