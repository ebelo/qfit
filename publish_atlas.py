from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable

from .activity_query import format_duration
from .polyline_utils import decode_polyline

DEFAULT_ATLAS_MARGIN_PERCENT = 8.0
DEFAULT_MIN_EXTENT_DEGREES = 0.01


@dataclass(frozen=True)
class AtlasPagePlan:
    source: str | None
    source_activity_id: str | None
    name: str
    activity_type: str
    start_date: str | None
    distance_m: float | None
    moving_time_s: int | None
    geometry_source: str
    page_name: str
    page_title: str
    page_subtitle: str
    min_lon: float
    min_lat: float
    max_lon: float
    max_lat: float
    extent_width_deg: float
    extent_height_deg: float


def build_atlas_page_plans(
    records: Iterable[dict],
    margin_percent: float = DEFAULT_ATLAS_MARGIN_PERCENT,
    min_extent_degrees: float = DEFAULT_MIN_EXTENT_DEGREES,
) -> list[AtlasPagePlan]:
    plans = []
    for record in records:
        bounds, geometry_source = activity_bounds(record, min_extent_degrees=min_extent_degrees)
        if bounds is None:
            continue

        min_lon, min_lat, max_lon, max_lat = expand_bounds(
            bounds,
            margin_percent=margin_percent,
            min_extent_degrees=min_extent_degrees,
        )
        page_title = (record.get("name") or "Untitled activity").strip()
        page_name = build_page_name(record)
        page_subtitle = build_page_subtitle(record)
        plans.append(
            AtlasPagePlan(
                source=record.get("source"),
                source_activity_id=record.get("source_activity_id"),
                name=page_title,
                activity_type=(record.get("activity_type") or "Activity").strip() or "Activity",
                start_date=record.get("start_date"),
                distance_m=_safe_float(record.get("distance_m")),
                moving_time_s=_safe_int(record.get("moving_time_s")),
                geometry_source=geometry_source,
                page_name=page_name,
                page_title=page_title,
                page_subtitle=page_subtitle,
                min_lon=min_lon,
                min_lat=min_lat,
                max_lon=max_lon,
                max_lat=max_lat,
                extent_width_deg=max_lon - min_lon,
                extent_height_deg=max_lat - min_lat,
            )
        )
    return plans


def activity_bounds(record: dict, min_extent_degrees: float = DEFAULT_MIN_EXTENT_DEGREES) -> tuple[tuple[float, float, float, float] | None, str]:
    points = record.get("geometry_points") or []
    if len(points) >= 2:
        return bounds_from_points(points, min_extent_degrees=min_extent_degrees), (record.get("geometry_source") or "stream")

    polyline_points = decode_polyline(record.get("summary_polyline"))
    if len(polyline_points) >= 2:
        return bounds_from_points(polyline_points, min_extent_degrees=min_extent_degrees), (record.get("geometry_source") or "summary_polyline")

    start_lat = _safe_float(record.get("start_lat"))
    start_lon = _safe_float(record.get("start_lon"))
    end_lat = _safe_float(record.get("end_lat"))
    end_lon = _safe_float(record.get("end_lon"))
    if None not in (start_lat, start_lon, end_lat, end_lon):
        return bounds_from_points([(start_lat, start_lon), (end_lat, end_lon)], min_extent_degrees=min_extent_degrees), (record.get("geometry_source") or "start_end")

    return None, record.get("geometry_source") or "unknown"


def bounds_from_points(points: Iterable[tuple[float, float]], min_extent_degrees: float = DEFAULT_MIN_EXTENT_DEGREES) -> tuple[float, float, float, float]:
    lats = []
    lons = []
    for lat, lon in points:
        lat_value = _safe_float(lat)
        lon_value = _safe_float(lon)
        if lat_value is None or lon_value is None:
            continue
        lats.append(lat_value)
        lons.append(lon_value)

    if not lats or not lons:
        raise ValueError("points must contain at least one valid coordinate pair")

    min_lat = min(lats)
    max_lat = max(lats)
    min_lon = min(lons)
    max_lon = max(lons)
    return ensure_minimum_extent((min_lon, min_lat, max_lon, max_lat), min_extent_degrees=min_extent_degrees)


def ensure_minimum_extent(
    bounds: tuple[float, float, float, float],
    min_extent_degrees: float = DEFAULT_MIN_EXTENT_DEGREES,
) -> tuple[float, float, float, float]:
    min_lon, min_lat, max_lon, max_lat = bounds
    width = max(max_lon - min_lon, 0.0)
    height = max(max_lat - min_lat, 0.0)

    if width < min_extent_degrees:
        expand = (min_extent_degrees - width) / 2.0
        min_lon -= expand
        max_lon += expand
    if height < min_extent_degrees:
        expand = (min_extent_degrees - height) / 2.0
        min_lat -= expand
        max_lat += expand

    return min_lon, min_lat, max_lon, max_lat


def expand_bounds(
    bounds: tuple[float, float, float, float],
    margin_percent: float = DEFAULT_ATLAS_MARGIN_PERCENT,
    min_extent_degrees: float = DEFAULT_MIN_EXTENT_DEGREES,
) -> tuple[float, float, float, float]:
    min_lon, min_lat, max_lon, max_lat = ensure_minimum_extent(bounds, min_extent_degrees=min_extent_degrees)
    margin_ratio = max(float(margin_percent or 0.0), 0.0) / 100.0
    width = max(max_lon - min_lon, min_extent_degrees)
    height = max(max_lat - min_lat, min_extent_degrees)
    pad_x = width * margin_ratio
    pad_y = height * margin_ratio
    return min_lon - pad_x, min_lat - pad_y, max_lon + pad_x, max_lat + pad_y


def build_page_name(record: dict) -> str:
    title = (record.get("name") or "Untitled activity").strip()
    activity_date = format_activity_date(record.get("start_date_local") or record.get("start_date"))
    if activity_date:
        return f"{activity_date} · {title}"
    return title


def build_page_subtitle(record: dict) -> str:
    parts = []
    activity_type = (record.get("activity_type") or "Activity").strip() or "Activity"
    parts.append(activity_type)

    distance_m = _safe_float(record.get("distance_m"))
    if distance_m is not None:
        parts.append(f"{distance_m / 1000.0:.1f} km")

    moving_time_s = _safe_int(record.get("moving_time_s"))
    if moving_time_s is not None:
        parts.append(format_duration(moving_time_s))

    return " · ".join(parts)


def format_activity_date(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        return str(value)[:10] or None


def _safe_float(value) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
