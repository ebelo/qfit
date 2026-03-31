"""Compatibility wrapper for activity-domain classification helpers.

The canonical provider-neutral activity classification logic now lives in
:mod:`qfit.activities.domain.activity_classification`.
"""

from .activities.domain.activity_classification import (
    ACTIVITY_LABEL_FIELDS,
    activity_prefers_pace,
    canonical_activity_label,
    normalize_activity_type,
    ordered_canonical_activity_labels,
    preferred_activity_field,
    resolve_activity_family,
)

__all__ = [
    "ACTIVITY_LABEL_FIELDS",
    "activity_prefers_pace",
    "canonical_activity_label",
    "normalize_activity_type",
    "ordered_canonical_activity_labels",
    "preferred_activity_field",
    "resolve_activity_family",
]
