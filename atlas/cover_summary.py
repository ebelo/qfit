from __future__ import annotations

from typing import Iterable

from ..activity_classification import ordered_canonical_activity_labels
from .publish_atlas import (
    build_date_range_label,
    format_distance_label,
    format_duration_label,
    format_elevation_label,
)


def _safe_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def build_cover_summary_from_rows(rows: Iterable[dict]) -> dict:
    """Compute cover-summary strings from plain atlas row dictionaries.

    Keeping this logic pure-Python lets the atlas export tests validate summary
    behaviour without constructing QGIS-shaped feature/layer doubles.
    """

    rows = list(rows)
    if not rows:
        return {}

    activity_count = len(rows)
    page_dates = [str(value) for value in (row.get("page_date") for row in rows) if value]
    total_distance_m = sum(value for value in (_safe_float(row.get("distance_m")) for row in rows) if value is not None)
    total_moving_time_s = sum(value for value in (_safe_int(row.get("moving_time_s")) for row in rows) if value is not None)
    total_elevation_gain_m = sum(
        value for value in (_safe_float(row.get("total_elevation_gain_m")) for row in rows) if value is not None
    )

    extent_xmin = float("inf")
    extent_ymin = float("inf")
    extent_xmax = float("-inf")
    extent_ymax = float("-inf")
    atlas_activity_ids: list[str] = []

    ordered_activity_types = ordered_canonical_activity_labels(
        (row.get("activity_type"), row.get("sport_type"))
        for row in rows
    )

    for row in rows:
        cx = _safe_float(row.get("center_x_3857"))
        cy = _safe_float(row.get("center_y_3857"))
        ew = _safe_float(row.get("extent_width_m"))
        eh = _safe_float(row.get("extent_height_m"))
        if all(value is not None for value in (cx, cy, ew, eh)):
            half_width, half_height = ew / 2.0, eh / 2.0
            extent_xmin = min(extent_xmin, cx - half_width)
            extent_ymin = min(extent_ymin, cy - half_height)
            extent_xmax = max(extent_xmax, cx + half_width)
            extent_ymax = max(extent_ymax, cy + half_height)

        source_activity_id = row.get("source_activity_id")
        if source_activity_id not in (None, ""):
            source_activity_id = str(source_activity_id)
            if source_activity_id not in atlas_activity_ids:
                atlas_activity_ids.append(source_activity_id)

    valid_extent = extent_xmin < extent_xmax and extent_ymin < extent_ymax

    activity_label = "activity" if activity_count == 1 else "activities"
    date_range_label = build_date_range_label(min(page_dates), max(page_dates)) if page_dates else None
    total_distance_label = format_distance_label(total_distance_m) if total_distance_m > 0 else None
    total_duration_label = format_duration_label(total_moving_time_s) if total_moving_time_s > 0 else None
    total_elevation_gain_label = format_elevation_label(total_elevation_gain_m) if total_elevation_gain_m > 0 else None
    activity_types_label = ", ".join(ordered_activity_types) if ordered_activity_types else None

    cover_parts = [f"{activity_count} {activity_label}"]
    for part in [
        date_range_label,
        total_distance_label,
        total_duration_label,
        total_elevation_gain_label,
        activity_types_label,
    ]:
        if part:
            cover_parts.append(part)

    return {
        "document_cover_summary": " · ".join(cover_parts) if cover_parts else "",
        "document_activity_count": str(activity_count),
        "document_date_range_label": date_range_label or "",
        "document_total_distance_label": total_distance_label or "",
        "document_total_duration_label": total_duration_label or "",
        "document_total_elevation_gain_label": total_elevation_gain_label or "",
        "document_activity_types_label": activity_types_label or "",
        "_cover_extent_xmin": extent_xmin if valid_extent else None,
        "_cover_extent_ymin": extent_ymin if valid_extent else None,
        "_cover_extent_xmax": extent_xmax if valid_extent else None,
        "_cover_extent_ymax": extent_ymax if valid_extent else None,
        "_atlas_activity_ids": atlas_activity_ids,
    }
