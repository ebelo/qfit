from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from ..domain.activity_query import (
    ActivityQuery,
    build_preview_lines,
    filter_activities,
    format_summary_text,
    sort_activities,
    summarize_activities,
)
from .activity_selection_state import ActivitySelectionState


_FETCH_PREVIEW_EMPTY_TEXT = "Fetch activities to preview your latest synced activities."


@dataclass(frozen=True)
class ActivityPreviewRequest:
    activities: Sequence[object]
    activity_type: str | None = "All"
    date_from: str | None = None
    date_to: str | None = None
    min_distance_km: float | int | None = None
    max_distance_km: float | int | None = None
    search_text: str | None = None
    detailed_route_filter: str | None = None
    preview_limit: int = 10


@dataclass(frozen=True)
class ActivityPreviewResult:
    selection_state: ActivitySelectionState
    fetched_activities: list[object]
    query_summary_text: str
    preview_text: str


def build_activity_preview_request(
    *,
    activities: Sequence[object],
    activity_type: str | None = "All",
    date_from: str | None = None,
    date_to: str | None = None,
    min_distance_km: float | int | None = None,
    max_distance_km: float | int | None = None,
    search_text: str | None = None,
    detailed_route_filter: str | None = None,
    preview_limit: int = 10,
) -> ActivityPreviewRequest:
    return ActivityPreviewRequest(
        activities=activities,
        activity_type=activity_type,
        date_from=date_from,
        date_to=date_to,
        min_distance_km=min_distance_km,
        max_distance_km=max_distance_km,
        search_text=search_text,
        detailed_route_filter=detailed_route_filter,
        preview_limit=preview_limit,
    )


def build_activity_query(request: ActivityPreviewRequest) -> ActivityQuery:
    return ActivityQuery(
        activity_type=request.activity_type or "All",
        date_from=request.date_from,
        date_to=request.date_to,
        min_distance_km=request.min_distance_km,
        max_distance_km=request.max_distance_km,
        search_text=request.search_text,
        detailed_route_filter=request.detailed_route_filter,
    )


def build_activity_preview_query(request: ActivityPreviewRequest) -> ActivityQuery:
    return build_activity_query(request)


def build_filtered_activity_preview_activities(
    activities: Sequence[object],
    query: ActivityQuery,
) -> list[object]:
    return filter_activities(activities, query)


def build_activity_preview_filtered_activities(
    request: ActivityPreviewRequest,
) -> list[object]:
    return build_filtered_activity_preview_activities(
        request.activities,
        build_activity_preview_query(request),
    )


def build_activity_selection_state(request: ActivityPreviewRequest) -> ActivitySelectionState:
    return ActivitySelectionState.from_activities(
        request.activities,
        build_activity_preview_query(request),
    )


def build_activity_preview_selection_state(
    request: ActivityPreviewRequest,
) -> ActivitySelectionState:
    return build_activity_selection_state(request)


def build_activity_preview(request: ActivityPreviewRequest) -> ActivityPreviewResult:
    selection_state = build_activity_preview_selection_state(request)

    if not request.activities:
        return ActivityPreviewResult(
            selection_state=selection_state,
            fetched_activities=[],
            query_summary_text=_FETCH_PREVIEW_EMPTY_TEXT,
            preview_text="",
        )

    fetched_activities = sort_activities(request.activities)
    summary = summarize_activities(fetched_activities)
    query_summary_text = format_summary_text(summary)
    if selection_state.filtered_count != len(request.activities):
        query_summary_text = (
            f"{query_summary_text}\n"
            f"Visualize filters currently match {selection_state.filtered_count} activities."
        )

    preview_lines = build_preview_lines(fetched_activities, limit=request.preview_limit)
    if len(fetched_activities) > len(preview_lines):
        preview_lines.append(
            "… and {count} more".format(count=len(fetched_activities) - len(preview_lines))
        )

    return ActivityPreviewResult(
        selection_state=selection_state,
        fetched_activities=fetched_activities,
        query_summary_text=query_summary_text,
        preview_text="\n".join(preview_lines),
    )
