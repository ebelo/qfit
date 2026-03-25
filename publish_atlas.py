from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from math import atan, exp, log, pi, tan
from typing import Iterable

from .activity_query import format_duration
from .polyline_utils import decode_polyline

DEFAULT_ATLAS_MARGIN_PERCENT = 8.0
DEFAULT_MIN_EXTENT_DEGREES = 0.01
DEFAULT_ATLAS_TARGET_ASPECT_RATIO = 0.0
MIN_ALLOWED_ATLAS_MARGIN_PERCENT = 0.0
MIN_ALLOWED_ATLAS_MIN_EXTENT_DEGREES = 0.0001
MIN_ALLOWED_ATLAS_TARGET_ASPECT_RATIO = 0.1
WEB_MERCATOR_EPSG = "EPSG:3857"
WEB_MERCATOR_HALF_WORLD_M = 20037508.342789244
WEB_MERCATOR_MAX_LAT = 85.05112878
_LABEL_MOVING_TIME = "Moving time"


@dataclass(frozen=True)
class AtlasPageSettings:
    margin_percent: float = DEFAULT_ATLAS_MARGIN_PERCENT
    min_extent_degrees: float = DEFAULT_MIN_EXTENT_DEGREES
    target_aspect_ratio: float | None = None


@dataclass(frozen=True)
class AtlasDocumentSummary:
    activity_count: int = 0
    activity_date_start: str | None = None
    activity_date_end: str | None = None
    date_range_label: str | None = None
    total_distance_m: float = 0.0
    total_distance_label: str | None = None
    total_moving_time_s: int = 0
    total_duration_label: str | None = None
    total_elevation_gain_m: float = 0.0
    total_elevation_gain_label: str | None = None
    activity_types_label: str | None = None
    cover_summary: str | None = None


@dataclass(frozen=True)
class AtlasTocEntry:
    page_number: int
    page_number_label: str
    page_sort_key: str
    page_name: str
    page_title: str
    page_subtitle: str
    page_date: str | None
    page_toc_label: str | None
    toc_entry_label: str
    page_distance_label: str | None
    page_duration_label: str | None
    page_stats_summary: str | None
    profile_available: bool
    page_profile_summary: str | None


@dataclass(frozen=True)
class AtlasCoverHighlight:
    highlight_order: int
    highlight_key: str
    highlight_label: str
    highlight_value: str


@dataclass(frozen=True)
class AtlasPageDetailItem:
    page_number: int
    page_sort_key: str
    page_name: str
    page_title: str
    detail_order: int
    detail_key: str
    detail_label: str
    detail_value: str


@dataclass(frozen=True)
class AtlasProfileSample:
    page_number: int
    page_sort_key: str
    page_name: str
    page_title: str
    page_date: str | None
    source: str | None
    source_activity_id: str | None
    activity_type: str
    profile_point_index: int
    profile_point_count: int
    profile_point_ratio: float
    distance_m: float
    distance_label: str | None
    altitude_m: float
    profile_distance_m: float


@dataclass(frozen=True)
class AtlasPagePlan:
    source: str | None
    source_activity_id: str | None
    name: str
    activity_type: str
    start_date: str | None
    distance_m: float | None
    moving_time_s: int | None
    total_elevation_gain_m: float | None
    average_speed_mps: float | None
    geometry_source: str
    page_number: int
    page_sort_key: str
    page_name: str
    page_title: str
    page_subtitle: str
    page_date: str | None
    page_toc_label: str | None
    page_distance_label: str | None
    page_duration_label: str | None
    page_average_speed_label: str | None
    page_average_pace_label: str | None
    page_elevation_gain_label: str | None
    page_stats_summary: str | None
    page_profile_summary: str | None
    document_activity_count: int
    document_date_range_label: str | None
    document_total_distance_label: str | None
    document_total_duration_label: str | None
    document_total_elevation_gain_label: str | None
    document_activity_types_label: str | None
    document_cover_summary: str | None
    profile_available: bool
    profile_point_count: int
    profile_distance_m: float | None
    profile_distance_label: str | None
    profile_min_altitude_m: float | None
    profile_max_altitude_m: float | None
    profile_altitude_range_label: str | None
    profile_relief_m: float | None
    profile_elevation_gain_m: float | None
    profile_elevation_gain_label: str | None
    profile_elevation_loss_m: float | None
    profile_elevation_loss_label: str | None
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
    target_aspect_ratio: float | None = None,
) -> AtlasPageSettings:
    normalized_margin = _safe_float(margin_percent)
    if normalized_margin is None:
        normalized_margin = DEFAULT_ATLAS_MARGIN_PERCENT
    normalized_margin = max(normalized_margin, MIN_ALLOWED_ATLAS_MARGIN_PERCENT)

    normalized_min_extent = _safe_float(min_extent_degrees)
    if normalized_min_extent is None:
        normalized_min_extent = DEFAULT_MIN_EXTENT_DEGREES
    normalized_min_extent = max(normalized_min_extent, MIN_ALLOWED_ATLAS_MIN_EXTENT_DEGREES)

    normalized_target_aspect_ratio = _safe_float(target_aspect_ratio)
    if normalized_target_aspect_ratio is None:
        normalized_target_aspect_ratio = DEFAULT_ATLAS_TARGET_ASPECT_RATIO
    if normalized_target_aspect_ratio <= 0:
        normalized_target_aspect_ratio = None
    else:
        normalized_target_aspect_ratio = max(
            normalized_target_aspect_ratio,
            MIN_ALLOWED_ATLAS_TARGET_ASPECT_RATIO,
        )

    return AtlasPageSettings(
        margin_percent=normalized_margin,
        min_extent_degrees=normalized_min_extent,
        target_aspect_ratio=normalized_target_aspect_ratio,
    )


def build_atlas_page_plans(
    records: Iterable[dict],
    margin_percent: float = DEFAULT_ATLAS_MARGIN_PERCENT,
    min_extent_degrees: float = DEFAULT_MIN_EXTENT_DEGREES,
    target_aspect_ratio: float | None = None,
    settings: AtlasPageSettings | None = None,
) -> list[AtlasPagePlan]:
    atlas_settings = settings or normalize_atlas_page_settings(
        margin_percent=margin_percent,
        min_extent_degrees=min_extent_degrees,
        target_aspect_ratio=target_aspect_ratio,
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

    document_summary = build_atlas_document_summary(record for _, record, _, _ in candidates)
    plans = []
    for page_number, (sort_key, record, geometry_source, bounds) in enumerate(sorted(candidates, key=lambda item: item[0]), start=1):
        min_lon, min_lat, max_lon, max_lat = expand_bounds(
            bounds,
            margin_percent=atlas_settings.margin_percent,
            min_extent_degrees=atlas_settings.min_extent_degrees,
        )
        min_lon, min_lat, max_lon, max_lat = fit_bounds_to_target_aspect_ratio(
            min_lon,
            min_lat,
            max_lon,
            max_lat,
            target_aspect_ratio=atlas_settings.target_aspect_ratio,
        )
        projected_bounds = lonlat_bounds_to_web_mercator(min_lon, min_lat, max_lon, max_lat)
        center_x_3857 = (projected_bounds[0] + projected_bounds[2]) / 2.0
        center_y_3857 = (projected_bounds[1] + projected_bounds[3]) / 2.0
        page_title = (record.get("name") or "Untitled activity").strip()
        page_name = build_page_name(record)
        page_subtitle = build_page_subtitle(record)
        profile_summary = build_profile_summary(record)
        plans.append(
            AtlasPagePlan(
                source=record.get("source"),
                source_activity_id=record.get("source_activity_id"),
                name=page_title,
                activity_type=(record.get("activity_type") or "Activity").strip() or "Activity",
                start_date=record.get("start_date"),
                distance_m=_safe_float(record.get("distance_m")),
                moving_time_s=_safe_int(record.get("moving_time_s")),
                total_elevation_gain_m=_safe_float(record.get("total_elevation_gain_m")),
                average_speed_mps=_safe_float(record.get("average_speed_mps")),
                geometry_source=geometry_source,
                page_number=page_number,
                page_sort_key=sort_key,
                page_name=page_name,
                page_title=page_title,
                page_subtitle=page_subtitle,
                page_date=format_activity_date(record.get("start_date_local") or record.get("start_date")),
                page_toc_label=build_page_toc_label(record),
                page_distance_label=format_distance_label(record.get("distance_m")),
                page_duration_label=format_duration_label(record.get("moving_time_s")),
                page_average_speed_label=format_speed_label(record.get("average_speed_mps")),
                page_average_pace_label=format_pace_label(
                    record.get("distance_m"),
                    record.get("moving_time_s"),
                    activity_type=record.get("activity_type"),
                ),
                page_elevation_gain_label=format_elevation_label(record.get("total_elevation_gain_m")),
                page_stats_summary=build_page_stats_summary(record),
                page_profile_summary=build_page_profile_summary(record),
                document_activity_count=document_summary.activity_count,
                document_date_range_label=document_summary.date_range_label,
                document_total_distance_label=document_summary.total_distance_label,
                document_total_duration_label=document_summary.total_duration_label,
                document_total_elevation_gain_label=document_summary.total_elevation_gain_label,
                document_activity_types_label=document_summary.activity_types_label,
                document_cover_summary=document_summary.cover_summary,
                profile_available=profile_summary.available,
                profile_point_count=profile_summary.point_count,
                profile_distance_m=profile_summary.distance_m,
                profile_distance_label=format_distance_label(profile_summary.distance_m),
                profile_min_altitude_m=profile_summary.min_altitude_m,
                profile_max_altitude_m=profile_summary.max_altitude_m,
                profile_altitude_range_label=format_altitude_range_label(
                    profile_summary.min_altitude_m,
                    profile_summary.max_altitude_m,
                ),
                profile_relief_m=profile_summary.relief_m,
                profile_elevation_gain_m=profile_summary.elevation_gain_m,
                profile_elevation_gain_label=format_elevation_label(profile_summary.elevation_gain_m),
                profile_elevation_loss_m=profile_summary.elevation_loss_m,
                profile_elevation_loss_label=format_elevation_label(profile_summary.elevation_loss_m),
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


def build_atlas_toc_entries(
    records: Iterable[dict],
    margin_percent: float = DEFAULT_ATLAS_MARGIN_PERCENT,
    min_extent_degrees: float = DEFAULT_MIN_EXTENT_DEGREES,
    target_aspect_ratio: float | None = None,
    settings: AtlasPageSettings | None = None,
    plans: list[AtlasPagePlan] | None = None,
) -> list[AtlasTocEntry]:
    entries = []
    resolved_plans = plans if plans is not None else build_atlas_page_plans(
        records,
        margin_percent=margin_percent,
        min_extent_degrees=min_extent_degrees,
        target_aspect_ratio=target_aspect_ratio,
        settings=settings,
    )
    for plan in resolved_plans:
        page_number_label = str(plan.page_number)
        toc_entry_label = f"{page_number_label}. {plan.page_toc_label or plan.page_name}"
        entries.append(
            AtlasTocEntry(
                page_number=plan.page_number,
                page_number_label=page_number_label,
                page_sort_key=plan.page_sort_key,
                page_name=plan.page_name,
                page_title=plan.page_title,
                page_subtitle=plan.page_subtitle,
                page_date=plan.page_date,
                page_toc_label=plan.page_toc_label,
                toc_entry_label=toc_entry_label,
                page_distance_label=plan.page_distance_label,
                page_duration_label=plan.page_duration_label,
                page_stats_summary=plan.page_stats_summary,
                profile_available=plan.profile_available,
                page_profile_summary=plan.page_profile_summary,
            )
        )
    return entries


def build_atlas_cover_highlights(records: Iterable[dict]) -> list[AtlasCoverHighlight]:
    return build_atlas_cover_highlights_from_summary(build_atlas_document_summary(records))


def build_atlas_page_detail_items(
    records: Iterable[dict],
    margin_percent: float = DEFAULT_ATLAS_MARGIN_PERCENT,
    min_extent_degrees: float = DEFAULT_MIN_EXTENT_DEGREES,
    target_aspect_ratio: float | None = None,
    settings: AtlasPageSettings | None = None,
    plans: list[AtlasPagePlan] | None = None,
) -> list[AtlasPageDetailItem]:
    items: list[AtlasPageDetailItem] = []
    resolved_plans = plans if plans is not None else build_atlas_page_plans(
        records,
        margin_percent=margin_percent,
        min_extent_degrees=min_extent_degrees,
        target_aspect_ratio=target_aspect_ratio,
        settings=settings,
    )
    for plan in resolved_plans:
        page_items: list[tuple[str, str, str | None]] = [
            ("distance", "Distance", plan.page_distance_label),
            ("moving_time", _LABEL_MOVING_TIME, plan.page_duration_label),
            ("average_speed", "Average speed", plan.page_average_speed_label),
            ("average_pace", "Average pace", plan.page_average_pace_label),
            ("elevation_gain", "Climbing", plan.page_elevation_gain_label),
            ("stats_summary", "Summary", plan.page_stats_summary),
            ("profile_summary", "Profile", plan.page_profile_summary),
        ]
        detail_order = 0
        for detail_key, detail_label, detail_value in page_items:
            if not detail_value:
                continue
            detail_order += 1
            items.append(
                AtlasPageDetailItem(
                    page_number=plan.page_number,
                    page_sort_key=plan.page_sort_key,
                    page_name=plan.page_name,
                    page_title=plan.page_title,
                    detail_order=detail_order,
                    detail_key=detail_key,
                    detail_label=detail_label,
                    detail_value=detail_value,
                )
            )
    return items


def build_atlas_profile_samples(
    records: Iterable[dict],
    margin_percent: float = DEFAULT_ATLAS_MARGIN_PERCENT,
    min_extent_degrees: float = DEFAULT_MIN_EXTENT_DEGREES,
    target_aspect_ratio: float | None = None,
    settings: AtlasPageSettings | None = None,
    plans: list[AtlasPagePlan] | None = None,
) -> list[AtlasProfileSample]:
    record_list = list(records)
    record_by_sort_key = {atlas_sort_key(record): record for record in record_list}
    samples = []
    resolved_plans = plans if plans is not None else build_atlas_page_plans(
        record_list,
        margin_percent=margin_percent,
        min_extent_degrees=min_extent_degrees,
        target_aspect_ratio=target_aspect_ratio,
        settings=settings,
    )
    for plan in resolved_plans:
        profile_points = extract_profile_points(record_by_sort_key.get(plan.page_sort_key) or {})
        profile_point_count = len(profile_points)
        if profile_point_count < 2:
            continue
        total_distance_m = profile_points[-1][0]
        denominator = max(1, profile_point_count - 1)
        for index, (distance_m, altitude_m) in enumerate(profile_points):
            samples.append(
                AtlasProfileSample(
                    page_number=plan.page_number,
                    page_sort_key=plan.page_sort_key,
                    page_name=plan.page_name,
                    page_title=plan.page_title,
                    page_date=plan.page_date,
                    source=plan.source,
                    source_activity_id=plan.source_activity_id,
                    activity_type=plan.activity_type,
                    profile_point_index=index,
                    profile_point_count=profile_point_count,
                    profile_point_ratio=float(index) / float(denominator),
                    distance_m=distance_m,
                    distance_label=format_distance_label(distance_m),
                    altitude_m=altitude_m,
                    profile_distance_m=total_distance_m,
                )
            )
    return samples


def build_atlas_document_summary(records: Iterable[dict]) -> AtlasDocumentSummary:
    record_list = list(records)
    activity_dates = [
        activity_date
        for activity_date in (
            format_activity_date(record.get("start_date_local") or record.get("start_date"))
            for record in record_list
        )
        if activity_date
    ]
    total_distance_m = sum(distance_m for distance_m in (_safe_float(record.get("distance_m")) for record in record_list) if distance_m is not None)
    total_moving_time_s = sum(moving_time_s for moving_time_s in (_safe_int(record.get("moving_time_s")) for record in record_list) if moving_time_s is not None)
    total_elevation_gain_m = sum(
        elevation_gain_m
        for elevation_gain_m in (_safe_float(record.get("total_elevation_gain_m")) for record in record_list)
        if elevation_gain_m is not None
    )

    ordered_activity_types: list[str] = []
    for record in record_list:
        activity_type = (record.get("activity_type") or "").strip()
        if not activity_type:
            continue
        if any(existing.casefold() == activity_type.casefold() for existing in ordered_activity_types):
            continue
        ordered_activity_types.append(activity_type)

    return _assemble_document_summary(
        activity_count=len(record_list),
        activity_dates=activity_dates,
        total_distance_m=total_distance_m,
        total_moving_time_s=total_moving_time_s,
        total_elevation_gain_m=total_elevation_gain_m,
        ordered_activity_types=ordered_activity_types,
    )


def build_atlas_document_summary_from_plans(plans: list[AtlasPagePlan]) -> AtlasDocumentSummary:
    if not plans:
        return AtlasDocumentSummary()

    activity_dates = [plan.page_date for plan in plans if plan.page_date]
    total_distance_m = sum(plan.distance_m for plan in plans if plan.distance_m is not None)
    total_moving_time_s = sum(plan.moving_time_s for plan in plans if plan.moving_time_s is not None)
    total_elevation_gain_m = sum(plan.total_elevation_gain_m for plan in plans if plan.total_elevation_gain_m is not None)

    ordered_activity_types: list[str] = []
    for plan in plans:
        activity_type = (plan.activity_type or "").strip()
        if not activity_type:
            continue
        if any(existing.casefold() == activity_type.casefold() for existing in ordered_activity_types):
            continue
        ordered_activity_types.append(activity_type)

    return _assemble_document_summary(
        activity_count=len(plans),
        activity_dates=activity_dates,
        total_distance_m=total_distance_m,
        total_moving_time_s=total_moving_time_s,
        total_elevation_gain_m=total_elevation_gain_m,
        ordered_activity_types=ordered_activity_types,
    )


def build_atlas_cover_highlights_from_summary(summary: AtlasDocumentSummary) -> list[AtlasCoverHighlight]:
    if summary.activity_count <= 0:
        return []

    highlights: list[AtlasCoverHighlight] = []

    def add_highlight(key: str, label: str, value: str | None):
        if not value:
            return
        highlights.append(
            AtlasCoverHighlight(
                highlight_order=len(highlights) + 1,
                highlight_key=key,
                highlight_label=label,
                highlight_value=value,
            )
        )

    activity_label = "activity" if summary.activity_count == 1 else "activities"
    add_highlight("activity_count", "Activities", f"{summary.activity_count} {activity_label}")
    add_highlight("date_range", "Date range", summary.date_range_label)
    add_highlight("total_distance", "Distance", summary.total_distance_label)
    add_highlight("total_duration", _LABEL_MOVING_TIME, summary.total_duration_label)
    add_highlight("total_elevation_gain", "Climbing", summary.total_elevation_gain_label)
    add_highlight("activity_types", "Activity types", summary.activity_types_label)
    return highlights


def _assemble_document_summary(
    activity_count: int,
    activity_dates: list[str],
    total_distance_m: float,
    total_moving_time_s: int,
    total_elevation_gain_m: float,
    ordered_activity_types: list[str],
) -> AtlasDocumentSummary:
    activity_date_start = min(activity_dates) if activity_dates else None
    activity_date_end = max(activity_dates) if activity_dates else None
    summary = AtlasDocumentSummary(
        activity_count=activity_count,
        activity_date_start=activity_date_start,
        activity_date_end=activity_date_end,
        date_range_label=build_date_range_label(activity_date_start, activity_date_end),
        total_distance_m=total_distance_m,
        total_distance_label=format_distance_label(total_distance_m) if total_distance_m > 0 else None,
        total_moving_time_s=total_moving_time_s,
        total_duration_label=format_duration_label(total_moving_time_s) if total_moving_time_s > 0 else None,
        total_elevation_gain_m=total_elevation_gain_m,
        total_elevation_gain_label=format_elevation_label(total_elevation_gain_m) if total_elevation_gain_m > 0 else None,
        activity_types_label=", ".join(ordered_activity_types) if ordered_activity_types else None,
    )
    return AtlasDocumentSummary(
        activity_count=summary.activity_count,
        activity_date_start=summary.activity_date_start,
        activity_date_end=summary.activity_date_end,
        date_range_label=summary.date_range_label,
        total_distance_m=summary.total_distance_m,
        total_distance_label=summary.total_distance_label,
        total_moving_time_s=summary.total_moving_time_s,
        total_duration_label=summary.total_duration_label,
        total_elevation_gain_m=summary.total_elevation_gain_m,
        total_elevation_gain_label=summary.total_elevation_gain_label,
        activity_types_label=summary.activity_types_label,
        cover_summary=build_cover_summary(summary),
    )


def build_date_range_label(start_date: str | None, end_date: str | None) -> str | None:
    if start_date and end_date:
        if start_date == end_date:
            return start_date
        return f"{start_date} → {end_date}"
    return start_date or end_date


def build_cover_summary(summary: AtlasDocumentSummary) -> str | None:
    parts = []

    if summary.activity_count > 0:
        activity_label = "activity" if summary.activity_count == 1 else "activities"
        parts.append(f"{summary.activity_count} {activity_label}")

    if summary.date_range_label:
        parts.append(summary.date_range_label)

    if summary.total_distance_label:
        parts.append(summary.total_distance_label)

    if summary.total_duration_label:
        parts.append(summary.total_duration_label)

    if summary.total_elevation_gain_label:
        parts.append(f"↑ {summary.total_elevation_gain_label}")

    if summary.activity_types_label:
        parts.append(summary.activity_types_label)

    if not parts:
        return None
    return " · ".join(parts)


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


def fit_bounds_to_target_aspect_ratio(
    min_lon: float,
    min_lat: float,
    max_lon: float,
    max_lat: float,
    target_aspect_ratio: float | None,
) -> tuple[float, float, float, float]:
    ratio = _safe_float(target_aspect_ratio)
    if ratio is None or ratio <= 0:
        return min_lon, min_lat, max_lon, max_lat

    min_x, min_y, max_x, max_y = lonlat_bounds_to_web_mercator(min_lon, min_lat, max_lon, max_lat)
    width = max(max_x - min_x, 0.0)
    height = max(max_y - min_y, 0.0)
    if width <= 0 or height <= 0:
        return min_lon, min_lat, max_lon, max_lat

    current_ratio = width / height
    if abs(current_ratio - ratio) < 1e-9:
        return min_lon, min_lat, max_lon, max_lat

    center_x = (min_x + max_x) / 2.0
    center_y = (min_y + max_y) / 2.0
    if current_ratio < ratio:
        width = height * ratio
    else:
        height = width / ratio

    adjusted_min_x = center_x - (width / 2.0)
    adjusted_max_x = center_x + (width / 2.0)
    adjusted_min_y = center_y - (height / 2.0)
    adjusted_max_y = center_y + (height / 2.0)
    adjusted_min_lon, adjusted_min_lat = web_mercator_to_lonlat(adjusted_min_x, adjusted_min_y)
    adjusted_max_lon, adjusted_max_lat = web_mercator_to_lonlat(adjusted_max_x, adjusted_max_y)
    return adjusted_min_lon, adjusted_min_lat, adjusted_max_lon, adjusted_max_lat


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


def build_page_toc_label(record: dict) -> str | None:
    parts = []

    activity_date = format_activity_date(record.get("start_date_local") or record.get("start_date"))
    if activity_date:
        parts.append(activity_date)

    title = (record.get("name") or "Untitled activity").strip()
    if title:
        parts.append(title)

    distance_label = format_distance_label(record.get("distance_m"))
    if distance_label:
        parts.append(distance_label)

    duration_label = format_duration_label(record.get("moving_time_s"))
    if duration_label:
        parts.append(duration_label)

    if not parts:
        return None
    return " · ".join(parts)


def build_page_stats_summary(record: dict) -> str | None:
    parts = []

    distance_label = format_distance_label(record.get("distance_m"))
    if distance_label:
        parts.append(distance_label)

    duration_label = format_duration_label(record.get("moving_time_s"))
    if duration_label:
        parts.append(duration_label)

    pace_label = format_pace_label(
        record.get("distance_m"),
        record.get("moving_time_s"),
        activity_type=record.get("activity_type"),
    )
    speed_label = format_speed_label(record.get("average_speed_mps"))
    effort_label = pace_label or speed_label
    if effort_label:
        parts.append(effort_label)

    elevation_gain_label = format_elevation_label(record.get("total_elevation_gain_m"))
    if elevation_gain_label:
        parts.append(f"↑ {elevation_gain_label}")

    if not parts:
        return None
    return " · ".join(parts)


def build_page_profile_summary(record: dict) -> str | None:
    profile_summary = build_profile_summary(record)
    if not profile_summary.available:
        return None

    parts = []
    distance_label = format_distance_label(profile_summary.distance_m)
    if distance_label:
        parts.append(distance_label)

    altitude_range_label = format_altitude_range_label(
        profile_summary.min_altitude_m,
        profile_summary.max_altitude_m,
    )
    if altitude_range_label:
        parts.append(altitude_range_label)

    relief_label = format_elevation_label(profile_summary.relief_m)
    if relief_label:
        parts.append(f"relief {relief_label}")

    gain_label = format_elevation_label(profile_summary.elevation_gain_m)
    if gain_label:
        parts.append(f"↑ {gain_label}")

    loss_label = format_elevation_label(profile_summary.elevation_loss_m)
    if loss_label:
        parts.append(f"↓ {loss_label}")

    if not parts:
        return None
    return " · ".join(parts)


@dataclass(frozen=True)
class AtlasProfileSummary:
    available: bool = False
    point_count: int = 0
    distance_m: float | None = None
    min_altitude_m: float | None = None
    max_altitude_m: float | None = None
    relief_m: float | None = None
    elevation_gain_m: float | None = None
    elevation_loss_m: float | None = None


def extract_profile_points(record: dict) -> list[tuple[float, float]]:
    details_json = record.get("details_json") or {}
    stream_metrics = details_json.get("stream_metrics") if isinstance(details_json, dict) else None
    if not isinstance(stream_metrics, dict):
        return []

    altitude_values = stream_metrics.get("altitude")
    distance_values = stream_metrics.get("distance")
    if not isinstance(altitude_values, list) or not isinstance(distance_values, list):
        return []

    profile_points = []
    for distance_value, altitude_value in zip(distance_values, altitude_values):
        distance_m = _safe_float(distance_value)
        altitude_m = _safe_float(altitude_value)
        if distance_m is None or altitude_m is None:
            continue
        profile_points.append((distance_m, altitude_m))
    return profile_points


def build_profile_summary(record: dict) -> AtlasProfileSummary:
    profile_points = extract_profile_points(record)
    if len(profile_points) < 2:
        return AtlasProfileSummary()

    profile_distance_m = profile_points[-1][0] - profile_points[0][0]
    if profile_distance_m <= 0:
        return AtlasProfileSummary()

    altitudes = [altitude for _, altitude in profile_points]
    elevation_gain_m = 0.0
    elevation_loss_m = 0.0
    for (_, previous_altitude), (_, current_altitude) in zip(profile_points, profile_points[1:]):
        delta = current_altitude - previous_altitude
        if delta > 0:
            elevation_gain_m += delta
        elif delta < 0:
            elevation_loss_m += abs(delta)

    min_altitude_m = min(altitudes)
    max_altitude_m = max(altitudes)
    return AtlasProfileSummary(
        available=True,
        point_count=len(profile_points),
        distance_m=profile_distance_m,
        min_altitude_m=min_altitude_m,
        max_altitude_m=max_altitude_m,
        relief_m=max_altitude_m - min_altitude_m,
        elevation_gain_m=elevation_gain_m,
        elevation_loss_m=elevation_loss_m,
    )


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


def format_speed_label(value) -> str | None:
    speed_mps = _safe_float(value)
    if speed_mps is None or speed_mps <= 0:
        return None
    return f"{speed_mps * 3.6:.1f} km/h"


def format_pace_label(distance_value, moving_time_value, activity_type: str | None = None) -> str | None:
    if not _activity_type_prefers_pace(activity_type):
        return None

    distance_m = _safe_float(distance_value)
    moving_time_s = _safe_int(moving_time_value)
    if distance_m is None or moving_time_s is None or distance_m <= 0 or moving_time_s <= 0:
        return None

    pace_seconds = moving_time_s / (distance_m / 1000.0)
    pace_minutes = int(pace_seconds // 60)
    pace_remainder_seconds = int(round(pace_seconds - (pace_minutes * 60)))
    if pace_remainder_seconds == 60:
        pace_minutes += 1
        pace_remainder_seconds = 0
    return f"{pace_minutes}m {pace_remainder_seconds:02d}s/km"


def format_elevation_label(value) -> str | None:
    elevation_m = _safe_float(value)
    if elevation_m is None:
        return None
    return f"{round(elevation_m):.0f} m"


def format_altitude_range_label(min_value, max_value) -> str | None:
    min_altitude_m = _safe_float(min_value)
    max_altitude_m = _safe_float(max_value)
    if min_altitude_m is None or max_altitude_m is None:
        return None
    return f"{round(min_altitude_m):.0f}–{round(max_altitude_m):.0f} m"


def _activity_type_prefers_pace(activity_type: str | None) -> bool:
    normalized = normalize_sort_text(activity_type or "")
    return any(token in normalized for token in ("run", "walk", "hike"))


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
