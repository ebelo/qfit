from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime
from typing import Iterable, Sequence

from .activity_classification import (
    ACTIVITY_LABEL_FIELDS,
    canonical_activity_label,
    normalize_activity_type,
)


@dataclass(frozen=True)
class ActivitySummary:
    count: int
    total_distance_km: float
    total_moving_time_s: int
    detailed_count: int
    by_type: dict[str, int]
    latest_date: str | None

DEFAULT_SORT_LABEL = "Start date (newest first)"
SORT_OPTIONS = (
    DEFAULT_SORT_LABEL,
    "Start date (oldest first)",
    "Distance (longest first)",
    "Distance (shortest first)",
    "Moving time (longest first)",
    "Name (A–Z)",
)
DETAILED_ROUTE_FILTER_ANY = "any"
DETAILED_ROUTE_FILTER_PRESENT = "present"
DETAILED_ROUTE_FILTER_MISSING = "missing"


def _normalize_detailed_route_filter(detailed_route_filter: str | None, *, detailed_only: bool = False) -> str:
    if detailed_route_filter in {
        DETAILED_ROUTE_FILTER_ANY,
        DETAILED_ROUTE_FILTER_PRESENT,
        DETAILED_ROUTE_FILTER_MISSING,
    }:
        return detailed_route_filter
    if detailed_only:
        return DETAILED_ROUTE_FILTER_PRESENT
    return DETAILED_ROUTE_FILTER_ANY


def _has_detailed_route(activity) -> bool:
    return (getattr(activity, "geometry_source", None) or "").strip().lower() == "stream"


class ActivityQuery:
    def __init__(
        self,
        activity_type: str | None = "All",
        date_from: str | None = None,
        date_to: str | None = None,
        min_distance_km: float | int | None = None,
        max_distance_km: float | int | None = None,
        search_text: str | None = None,
        detailed_only: bool = False,
        detailed_route_filter: str | None = None,
        sort_label: str | None = DEFAULT_SORT_LABEL,
    ):
        self.activity_type = activity_type or "All"
        self.date_from = date_from or None
        self.date_to = date_to or None
        self.min_distance_km = _safe_float(min_distance_km)
        self.max_distance_km = _safe_float(max_distance_km)
        self.search_text = (search_text or "").strip()
        self.detailed_only = bool(detailed_only)
        self.detailed_route_filter = _normalize_detailed_route_filter(
            detailed_route_filter,
            detailed_only=self.detailed_only,
        )
        self.sort_label = sort_label or DEFAULT_SORT_LABEL


def filter_activities(activities: Iterable[object], query: ActivityQuery) -> list[object]:
    results = []
    search_text = query.search_text.casefold()
    date_from = _parse_iso_date(query.date_from)
    date_to = _parse_iso_date(query.date_to)

    for activity in activities:
        if query.activity_type and query.activity_type != "All":
            query_norm = normalize_activity_type(query.activity_type)
            if not any(
                normalize_activity_type(getattr(activity, field, None)) == query_norm
                for field in ACTIVITY_LABEL_FIELDS
            ):
                continue

        activity_date = _activity_date(activity)
        if date_from is not None and (activity_date is None or activity_date < date_from):
            continue
        if date_to is not None and (activity_date is None or activity_date > date_to):
            continue

        distance_km = _distance_km(activity)
        if query.min_distance_km is not None and query.min_distance_km > 0:
            if distance_km is None or distance_km < query.min_distance_km:
                continue
        if query.max_distance_km is not None and query.max_distance_km > 0:
            if distance_km is None or distance_km > query.max_distance_km:
                continue

        if search_text:
            haystack = " ".join(
                part
                for part in [
                    getattr(activity, "name", None),
                    getattr(activity, "activity_type", None),
                    getattr(activity, "sport_type", None),
                ]
                if part
            ).casefold()
            if search_text not in haystack:
                continue

        if query.detailed_route_filter == DETAILED_ROUTE_FILTER_PRESENT and not _has_detailed_route(activity):
            continue
        if query.detailed_route_filter == DETAILED_ROUTE_FILTER_MISSING and _has_detailed_route(activity):
            continue

        results.append(activity)

    return results


def sort_activities(activities: Sequence[object], sort_label: str | None) -> list[object]:
    sort_label = sort_label or DEFAULT_SORT_LABEL
    items = list(activities)

    if sort_label == "Start date (oldest first)":
        return sorted(items, key=lambda activity: (_sort_datetime(activity) is None, _sort_datetime(activity) or datetime.min))
    if sort_label == "Distance (longest first)":
        return sorted(items, key=lambda activity: _distance_sort_value(activity), reverse=True)
    if sort_label == "Distance (shortest first)":
        return sorted(items, key=lambda activity: (_distance_sort_value(activity) is None, _distance_sort_value(activity) or float("inf")))
    if sort_label == "Moving time (longest first)":
        return sorted(items, key=lambda activity: _moving_time_sort_value(activity), reverse=True)
    if sort_label == "Name (A–Z)":
        return sorted(items, key=lambda activity: ((getattr(activity, "name", None) or "").casefold(), _sort_datetime(activity) or datetime.min), reverse=False)

    return sorted(items, key=lambda activity: (_sort_datetime(activity) or datetime.min, (getattr(activity, "name", None) or "").casefold()), reverse=True)


def summarize_activities(activities: Sequence[object]) -> ActivitySummary:
    total_distance_km = 0.0
    total_moving_time_s = 0
    detailed_count = 0
    by_type = Counter()
    latest_date = None

    for activity in activities:
        distance_km = _distance_km(activity)
        if distance_km is not None:
            total_distance_km += distance_km
        moving_time_s = getattr(activity, "moving_time_s", None)
        if isinstance(moving_time_s, (int, float)):
            total_moving_time_s += int(moving_time_s)
        if getattr(activity, "geometry_source", None) == "stream":
            detailed_count += 1
        activity_type = canonical_activity_label(
            getattr(activity, "activity_type", None),
            getattr(activity, "sport_type", None),
        ) or "Unknown"
        by_type[activity_type] += 1
        activity_date = _activity_date(activity)
        if activity_date is not None and (latest_date is None or activity_date > latest_date):
            latest_date = activity_date

    return ActivitySummary(
        count=len(activities),
        total_distance_km=round(total_distance_km, 1),
        total_moving_time_s=total_moving_time_s,
        detailed_count=detailed_count,
        by_type=dict(sorted(by_type.items())),
        latest_date=latest_date.isoformat() if latest_date is not None else None,
    )


def build_preview_lines(activities: Sequence[object], limit: int = 8) -> list[str]:
    lines = []
    for activity in list(activities)[: max(limit, 0)]:
        date_label = _activity_date(activity).isoformat() if _activity_date(activity) is not None else "unknown date"
        activity_type = canonical_activity_label(
            getattr(activity, "activity_type", None),
            getattr(activity, "sport_type", None),
        ) or "Activity"
        distance_km = _distance_km(activity)
        distance_label = "? km" if distance_km is None else f"{distance_km:.1f} km"
        moving_time_label = format_duration(getattr(activity, "moving_time_s", None))
        detail_label = "detailed" if getattr(activity, "geometry_source", None) == "stream" else "summary"
        name = getattr(activity, "name", None) or "Untitled activity"
        lines.append(f"{date_label} — {name} · {activity_type} · {distance_label} · {moving_time_label} · {detail_label}")
    return lines


def build_subset_string(query: ActivityQuery) -> str:
    clauses = []
    if query.activity_type and query.activity_type != "All":
        normalized = _escape_sql_literal(normalize_activity_type(query.activity_type))
        type_matches = [
            f"{_sql_normalize_expr(field_name)} = '{normalized}'"
            for field_name in reversed(ACTIVITY_LABEL_FIELDS)
        ]
        clauses.append(f"({' OR '.join(type_matches)})")
    if query.date_from:
        clauses.append(f'"start_date" >= \'{_escape_sql_literal(query.date_from)}T00:00:00\'')
    if query.date_to:
        clauses.append(f'"start_date" <= \'{_escape_sql_literal(query.date_to)}T23:59:59\'')
    if query.min_distance_km is not None and query.min_distance_km > 0:
        clauses.append(f'"distance_m" >= {query.min_distance_km * 1000.0}')
    if query.max_distance_km is not None and query.max_distance_km > 0:
        clauses.append(f'"distance_m" <= {query.max_distance_km * 1000.0}')
    if query.search_text:
        search_text = _escape_sql_literal(query.search_text.lower())
        search_clauses = [f"lower(coalesce(\"{field_name}\", '')) LIKE '%{search_text}%'" for field_name in ("name", *reversed(ACTIVITY_LABEL_FIELDS))]
        clauses.append(f"({' OR '.join(search_clauses)})")
    if query.detailed_route_filter == DETAILED_ROUTE_FILTER_PRESENT:
        clauses.append("LOWER(COALESCE(\"geometry_source\", '')) = 'stream'")
    elif query.detailed_route_filter == DETAILED_ROUTE_FILTER_MISSING:
        clauses.append("LOWER(COALESCE(\"geometry_source\", '')) <> 'stream'")
    return " AND ".join(clauses)


def format_duration(value: int | float | None) -> str:
    if value is None:
        return "?"
    total_seconds = max(int(value), 0)
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours}h {minutes:02d}m"
    if minutes:
        return f"{minutes}m {seconds:02d}s"
    return f"{seconds}s"


def format_summary_text(summary: ActivitySummary) -> str:
    if not summary.count:
        return "0 activities match the current filters."

    top_types = ", ".join(f"{name}: {count}" for name, count in list(summary.by_type.items())[:3])
    latest_date = summary.latest_date or "unknown"
    return (
        "{count} activities · {distance:.1f} km · {duration} moving · detailed tracks: {detailed} · latest: {latest}"
        "\nTop activity types: {top_types}"
    ).format(
        count=summary.count,
        distance=summary.total_distance_km,
        duration=format_duration(summary.total_moving_time_s),
        detailed=summary.detailed_count,
        latest=latest_date,
        top_types=top_types or "n/a",
    )


def _activity_date(activity: object) -> date | None:
    return _parse_iso_date(getattr(activity, "start_date_local", None) or getattr(activity, "start_date", None))


def _parse_iso_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        try:
            return date.fromisoformat(str(value)[:10])
        except ValueError:
            return None


def _sort_datetime(activity: object) -> datetime | None:
    value = getattr(activity, "start_date_local", None) or getattr(activity, "start_date", None)
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _distance_km(activity: object) -> float | None:
    distance_m = getattr(activity, "distance_m", None)
    if not isinstance(distance_m, (int, float)):
        return None
    return float(distance_m) / 1000.0


def _distance_sort_value(activity: object) -> float:
    distance_m = getattr(activity, "distance_m", None)
    if not isinstance(distance_m, (int, float)):
        return -1.0
    return float(distance_m)


def _moving_time_sort_value(activity: object) -> int:
    value = getattr(activity, "moving_time_s", None)
    if not isinstance(value, (int, float)):
        return -1
    return int(value)


def _sql_normalize_expr(field: str) -> str:
    """SQL expression approximating normalize_activity_type for a column."""
    return f"LOWER(REPLACE(REPLACE(REPLACE(\"{field}\", ' ', ''), '-', ''), '_', ''))"


def _escape_sql_literal(value: str) -> str:
    return str(value).replace("'", "''")


def _safe_float(value: float | int | str | None) -> float | None:
    if value in (None, ""):
        return None
    return float(value)
