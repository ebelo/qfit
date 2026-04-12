from __future__ import annotations


def build_filtered_visual_apply_status(filtered_count: int) -> str:
    return "Applied filters and styling ({count} matching activities)".format(
        count=filtered_count
    )
