from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from ..domain.activity_query import ActivityQuery, filter_activities


@dataclass(frozen=True)
class ActivitySelectionState:
    """Reusable application model for the current effective activity subset."""

    query: ActivityQuery = field(default_factory=ActivityQuery)
    filtered_count: int = 0

    @classmethod
    def from_activities(
        cls,
        activities: Iterable[object],
        query: ActivityQuery | None = None,
    ) -> "ActivitySelectionState":
        normalized_query = query if query is not None else ActivityQuery()
        return cls(
            query=normalized_query,
            filtered_count=len(filter_activities(activities, normalized_query)),
        )

