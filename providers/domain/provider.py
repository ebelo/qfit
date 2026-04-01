"""Provider protocol for activity sources.

Defines the contract that all activity providers (Strava, GPX, …) must
implement, as well as the common error type they should raise.
"""

from typing import Dict, List, Optional, Protocol, runtime_checkable

from ...activities.domain.models import Activity
from ...detailed_route_strategy import DEFAULT_DETAILED_ROUTE_STRATEGY


class ProviderError(RuntimeError):
    """Raised by an :class:`ActivityProvider` when a fetch or auth operation fails."""


@runtime_checkable
class ActivityProvider(Protocol):
    """Protocol for objects that can fetch fitness activities.

    Any class that exposes ``source_name``, ``last_stream_enrichment_stats``,
    ``last_rate_limit``, and :meth:`fetch_activities` with the matching
    signature satisfies this protocol — no explicit inheritance required.
    """

    source_name: str
    last_stream_enrichment_stats: Dict
    last_rate_limit: Optional[Dict]

    def fetch_activities(
        self,
        per_page: int = 200,
        max_pages: int = 0,
        before: Optional[float] = None,
        after: Optional[float] = None,
        use_detailed_streams: bool = False,
        max_detailed_activities: Optional[int] = None,
        detailed_route_strategy: str = DEFAULT_DETAILED_ROUTE_STRATEGY,
    ) -> List[Activity]:
        ...
