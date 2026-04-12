from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

from ..domain.activity_classification import ordered_canonical_activity_labels, preferred_activity_field


@dataclass(frozen=True)
class ActivityTypeOptionsResult:
    options: list[str]
    selected_value: str


def build_activity_type_options(
    label_pairs: Iterable[tuple[str | None, str | None]],
    *,
    current_value: str | None = "All",
) -> ActivityTypeOptionsResult:
    values = sorted(ordered_canonical_activity_labels(label_pairs))
    options = ["All", *values]
    normalized_current = current_value or "All"
    selected_value = normalized_current if normalized_current in options else "All"
    return ActivityTypeOptionsResult(options=options, selected_value=selected_value)


def build_activity_type_options_from_activities(
    activities: Sequence[object],
    *,
    current_value: str | None = "All",
) -> ActivityTypeOptionsResult:
    return build_activity_type_options(
        (
            (getattr(activity, "activity_type", None), getattr(activity, "sport_type", None))
            for activity in activities
        ),
        current_value=current_value,
    )


def build_activity_type_options_from_records(
    records: Iterable[object],
    field_names: Iterable[str],
    *,
    current_value: str | None = "All",
) -> ActivityTypeOptionsResult | None:
    available_fields = {str(name) for name in field_names}
    if preferred_activity_field(available_fields) is None:
        return None

    return build_activity_type_options(
        (
            (
                record["activity_type"] if "activity_type" in available_fields else None,
                record["sport_type"] if "sport_type" in available_fields else None,
            )
            for record in records
        ),
        current_value=current_value,
    )
