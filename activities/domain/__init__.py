"""Provider-neutral activity domain core for qfit."""

from .activity_classification import (
    ACTIVITY_LABEL_FIELDS,
    activity_prefers_pace,
    canonical_activity_label,
    normalize_activity_type,
    ordered_canonical_activity_labels,
    preferred_activity_field,
    resolve_activity_family,
)
from .activity_query import (
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
from .models import Activity
