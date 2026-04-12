from __future__ import annotations


def build_filtered_visual_apply_status(filtered_count: int) -> str:
    return "Applied filters and styling ({count} matching activities)".format(
        count=filtered_count
    )


def append_visual_apply_temporal_note(status: str, temporal_note: str) -> str:
    if not temporal_note:
        return status
    return "{status}. {temporal_note}.".format(
        status=status, temporal_note=temporal_note
    )
