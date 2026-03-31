"""Compatibility wrapper for activity-domain query helpers.

The canonical provider-neutral activity query/summary logic now lives in
:mod:`qfit.activities.domain.activity_query`.
"""

from .activities.domain.activity_query import (
    DEFAULT_SORT_LABEL,
    SORT_OPTIONS,
    ActivityQuery,
    ActivitySummary,
    build_preview_lines,
    build_subset_string,
    filter_activities,
    format_duration,
    format_summary_text,
    sort_activities,
    summarize_activities,
)

__all__ = [
    "DEFAULT_SORT_LABEL",
    "SORT_OPTIONS",
    "ActivityQuery",
    "ActivitySummary",
    "build_preview_lines",
    "build_subset_string",
    "filter_activities",
    "format_duration",
    "format_summary_text",
    "sort_activities",
    "summarize_activities",
]
