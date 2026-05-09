from __future__ import annotations

from typing import Any

from qfit.activities.domain.activity_query import (
    DETAILED_ROUTE_FILTER_ANY,
    DETAILED_ROUTE_FILTER_MISSING,
    DETAILED_ROUTE_FILTER_PRESENT,
)

ALL_ACTIVITY_TYPES = "All"


def build_local_first_filter_description(request: Any) -> str | None:
    """Describe active local-first map filters without depending on dock widgets."""

    parts = tuple(_filter_description_parts(request))
    if not parts:
        return None
    return " · ".join(parts)


def _filter_description_parts(request: Any) -> list[str]:
    parts: list[str] = []
    activity_type = _normalised_text(getattr(request, "activity_type", None))
    if activity_type and activity_type != ALL_ACTIVITY_TYPES:
        parts.append(f"type: {activity_type}")

    search_text = _normalised_text(getattr(request, "search_text", None))
    if search_text:
        parts.append(f"search: {_quote(search_text)}")

    date_part = _date_range_part(
        _normalised_text(getattr(request, "date_from", None)),
        _normalised_text(getattr(request, "date_to", None)),
    )
    if date_part is not None:
        parts.append(date_part)

    distance_part = _distance_range_part(
        getattr(request, "min_distance_km", None),
        getattr(request, "max_distance_km", None),
    )
    if distance_part is not None:
        parts.append(distance_part)

    route_part = _route_filter_part(
        _normalised_text(getattr(request, "detailed_route_filter", None))
    )
    if route_part is not None:
        parts.append(route_part)

    return parts


def _date_range_part(date_from: str | None, date_to: str | None) -> str | None:
    if date_from and date_to:
        return f"dates: {date_from}–{date_to}"
    if date_from:
        return f"dates: from {date_from}"
    if date_to:
        return f"dates: until {date_to}"
    return None


def _distance_range_part(
    min_distance_km: float | int | None,
    max_distance_km: float | int | None,
) -> str | None:
    minimum = _positive_number(min_distance_km)
    maximum = _positive_number(max_distance_km)
    if minimum is not None and maximum is not None:
        return f"distance: {_format_km(minimum)}–{_format_km(maximum)} km"
    if minimum is not None:
        return f"distance: ≥ {_format_km(minimum)} km"
    if maximum is not None:
        return f"distance: ≤ {_format_km(maximum)} km"
    return None


def _route_filter_part(value: str | None) -> str | None:
    if value in (None, "", DETAILED_ROUTE_FILTER_ANY):
        return None
    if value == DETAILED_ROUTE_FILTER_PRESENT:
        return "routes: detailed only"
    if value == DETAILED_ROUTE_FILTER_MISSING:
        return "routes: missing details"
    return f"routes: {value}"


def _normalised_text(value: Any) -> str | None:
    if value is None:
        return None
    stripped = str(value).strip()
    return stripped or None


def _positive_number(value: float | int | None) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number <= 0:
        return None
    return number


def _format_km(value: float) -> str:
    if value.is_integer():
        return str(int(value))
    return f"{value:g}"


def _quote(value: str) -> str:
    return f"“{value}”"


__all__ = ["build_local_first_filter_description"]
