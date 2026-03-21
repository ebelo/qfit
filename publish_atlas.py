from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from math import atan, exp, log, pi, tan
from typing import Iterable

from .activity_query import format_duration
from .polyline_utils import decode_polyline

DEFAULT_ATLAS_MARGIN_PERCENT = 8.0
DEFAULT_MIN_EXTENT_DEGREES = 0.01
MIN_ALLOWED_ATLAS_MARGIN_PERCENT = 0.0
MIN_ALLOWED_ATLAS_MIN_EXTENT_DEGREES = 0.0001
WEB_MERCATOR_EPSG = "EPSG:3857"
WEB_MERCATOR_HALF_WORLD_M = 20037508.342789244
WEB_MERCATOR_MAX_LAT = 85.05112878


@dataclass(frozen=True)
class AtlasPageSettings:
    margin_percent: float = DEFAULT_ATLAS_MARGIN_PERCENT
    min_extent_degrees: float = DEFAULT_MIN_EXTENT_DEGREES


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
    page_number: int
    page_sort_key: str
    page_name: str
    page_title: str
    page_subtitle: str
    page_date: str | None
    page_distance_label: str | None
    page_duration_label: str | None
    min_lon: float
    min_lat: float
    max_lon: float
    max_lat: float
    extent_width_deg: float
    extent_height_deg: float
    center_x_3857: float
    center_y_3857: float
    extent_width_m: float
    extent_height_m: float


def normalize_atlas_page_settings(
    margin_percent: float | None = None,
    min_extent_degrees: float | None = None,
) -> AtlasPageSettings:
    normalized_margin = _safe_float(margin_percent)
    if normalized_margin is None:
        normalized_margin = DEFAULT_ATLAS_MARGIN_PERCENT
    normalized_margin = max(normalized_margin, MIN_ALLOWED_ATLAS_MARGIN_PERCENT)

    normalized_min_extent = _safe_float(min_extent_degrees)
    if normalized_min_extent is None:
        normalized_min_extent = DEFAULT_MIN_EXTENT_DEGREES
    normalized_min_extent = max(normalized_min_extent, MIN_ALLOWED_ATLAS_MIN_EXTENT_DEGREES)

    return AtlasPageSettings(
        margin_percent=normalized_margin,
        min_extent_degrees=normalized_min_extent,
    )


def build_atlas_page_plans(
    records: Iterable[dict],
    margin_percent: float = DEFAULT_ATLAS_MARGIN_PERCENT,
    min_extent_degrees: float = DEFAULT_MIN_EXTENT_DEGREES,
    settings: AtlasPageSettings | None = None,
) -> list[AtlasPagePlan]:
    atlas_settings = settings or normalize_atlas_page_settings(
        margin_percent=margin_percent,
        min_extent_degrees=min_extent_degrees,
    )
    candidates = []
    for record in records:
        bounds, geometry_source = activity_bounds(
            record,
            min_extent_degrees=atlas_settings.min_extent_degrees,
        )
        if bounds is None:
            continue
        candidates.append((atlas_sort_key(record), record, geometry_source, bounds))

    plans = []
    for page_number, (sort_key, record, geometry_source, bounds) in enumerate(sorted(candidates, key=lambda item: item[0]), start=1):
        min_lon, min_lat, max_lon, max_lat = expand_bounds(
            bounds,
            margin_percent=atlas_settings.margin_percent,
            min_extent_degrees=atlas_settings.min_extent_degrees,
        )
        projected_bounds = lonlat_bounds_to_web_mercator(min_lon, min_lat, max_lon, max_lat)
        center_x_3857 = (projected_bounds[0] + projected_bounds[2]) / 2.0
        center_y_3857 = (projected_bounds[1] + projected_bounds[3]) / 2.0
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
                page_number=page_number,
                page_sort_key=sort_key,
                page_name=page_name,
                page_title=page_title,
                page_subtitle=page_subtitle,
                page_date=format_activity_date(record.get("start_date_local") or record.get("start_date")),
                page_distance_label=format_distance_label(record.get("distance_m")),
                page_duration_label=format_duration_label(record.get("moving_time_s")),
                min_lon=min_lon,
                min_lat=min_lat,
                max_lon=max_lon,
                max_lat=max_lat,
                extent_width_deg=max_lon - min_lon,
                extent_height_deg=max_lat - min_lat,
                center_x_3857=center_x_3857,
                center_y_3857=center_y_3857,
                extent_width_m=projected_bounds[2] - projected_bounds[0],
                extent_height_m=projected_bounds[3] - projected_bounds[1],
            )
        )
    return plans


def atlas_sort_key(record: dict) -> str:
    activity_date = format_sortable_activity_datetime(record.get("start_date_local") or record.get("start_date"))
    title = normalize_sort_text(record.get("name") or "Untitled activity")
    source = normalize_sort_text(record.get("source") or "")
    source_activity_id = normalize_sort_text(record.get("source_activity_id") or "")
    return "|".join([activity_date, title, source, source_activity_id])


def format_sortable_activity_datetime(value: str | None) -> str:
    if not value:
        return "9999-12-31T23:59:59"
    text = str(value).strip()
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).isoformat()
    except ValueError:
        if len(text) >= 19:
            return text[:19]
        return text or "9999-12-31T23:59:59"


def normalize_sort_text(value: str | None) -> str:
    text = (value or "").strip().casefold()
    return " ".join(text.split())


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


def lonlat_to_web_mercator(lon: float, lat: float) -> tuple[float, float]:
    lon_value = _safe_float(lon)
    lat_value = _safe_float(lat)
    if lon_value is None or lat_value is None:
        raise ValueError("lon and lat must be valid numeric values")

    clamped_lon = max(min(lon_value, 180.0), -180.0)
    clamped_lat = max(min(lat_value, WEB_MERCATOR_MAX_LAT), -WEB_MERCATOR_MAX_LAT)
    x = WEB_MERCATOR_HALF_WORLD_M * clamped_lon / 180.0
    y = WEB_MERCATOR_HALF_WORLD_M * log(tan(pi / 4.0 + (clamped_lat * pi / 180.0) / 2.0)) / pi
    return x, y


def web_mercator_to_lonlat(x: float, y: float) -> tuple[float, float]:
    x_value = _safe_float(x)
    y_value = _safe_float(y)
    if x_value is None or y_value is None:
        raise ValueError("x and y must be valid numeric values")

    clamped_x = max(min(x_value, WEB_MERCATOR_HALF_WORLD_M), -WEB_MERCATOR_HALF_WORLD_M)
    clamped_y = max(min(y_value, WEB_MERCATOR_HALF_WORLD_M), -WEB_MERCATOR_HALF_WORLD_M)
    lon = (clamped_x / WEB_MERCATOR_HALF_WORLD_M) * 180.0
    lat = (2.0 * atan(exp((clamped_y / WEB_MERCATOR_HALF_WORLD_M) * pi)) - pi / 2.0) * 180.0 / pi
    return lon, lat


def lonlat_bounds_to_web_mercator(
    min_lon: float,
    min_lat: float,
    max_lon: float,
    max_lat: float,
) -> tuple[float, float, float, float]:
    min_x, min_y = lonlat_to_web_mercator(min_lon, min_lat)
    max_x, max_y = lonlat_to_web_mercator(max_lon, max_lat)
    return min(min_x, max_x), min(min_y, max_y), max(min_x, max_x), max(min_y, max_y)


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

    distance_label = format_distance_label(record.get("distance_m"))
    if distance_label:
        parts.append(distance_label)

    duration_label = format_duration_label(record.get("moving_time_s"))
    if duration_label:
        parts.append(duration_label)

    return " · ".join(parts)


def format_activity_date(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        return str(value)[:10] or None


def format_distance_label(value) -> str | None:
    distance_m = _safe_float(value)
    if distance_m is None:
        return None
    return f"{distance_m / 1000.0:.1f} km"


def format_duration_label(value) -> str | None:
    moving_time_s = _safe_int(value)
    if moving_time_s is None:
        return None
    return format_duration(moving_time_s)


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
