from __future__ import annotations

from .background_map_messages import (
    build_background_map_cleared_status,
    build_background_map_failure_status,
    build_background_map_loaded_status,
    build_styled_background_map_failure_status,
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


def build_visual_apply_result_status(
    has_layers: bool,
    apply_subset_filters: bool,
    filtered_count: int,
    wants_background: bool,
    background_loaded: bool,
    temporal_note: str,
) -> str:
    status = build_visual_apply_status(
        has_layers=has_layers,
        apply_subset_filters=apply_subset_filters,
        filtered_count=filtered_count,
        wants_background=wants_background,
        background_loaded=background_loaded,
    )
    return append_visual_apply_temporal_note(status, temporal_note)


def build_visual_apply_background_failure_result_status(
    has_layers: bool,
    temporal_note: str,
) -> str:
    if not has_layers:
        status = build_background_map_failure_status()
    else:
        status = build_styled_background_map_failure_status()
    return append_visual_apply_temporal_note(status, temporal_note)


def append_visual_apply_temporal_note(status: str, temporal_note: str) -> str:
    if not temporal_note:
        return status
    return "{status}. {temporal_note}.".format(
        status=status, temporal_note=temporal_note
    )
