"""Service for processing fetch task completion into structured results.

Wraps the raw callback parameters from :class:`FetchTask` into a
:class:`FetchResult` dataclass and delegates metadata/status building to
:class:`SyncController` — all independent of the UI layer.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class FetchResult:
    """Structured outcome from a completed activity fetch."""

    activities: list = field(default_factory=list)
    error: str | None = None
    cancelled: bool = False
    metadata: dict = field(default_factory=dict)
    status_text: str = ""

    @property
    def ok(self) -> bool:
        """``True`` when the fetch succeeded with activities."""
        return not self.cancelled and self.error is None

    @property
    def activity_count(self) -> int:
        return len(self.activities)

    @property
    def detailed_count(self) -> int:
        return self.metadata.get("detailed_count", 0)

    @property
    def today_str(self) -> str:
        return self.metadata.get("today_str", "")

    @property
    def count_label_text(self) -> str:
        """Text suitable for the activity-count UI label."""
        return (
            "{count} activities loaded (last sync: {sync_date}, "
            "detailed tracks: {detailed})"
        ).format(
            count=self.activity_count,
            sync_date=self.today_str,
            detailed=self.detailed_count,
        )


class FetchResultService:
    """Processes raw fetch-task callbacks into structured :class:`FetchResult` objects.

    Keeps metadata building and status-text generation out of the UI layer,
    matching the pattern established by :class:`AtlasExportService` and
    :class:`LoadWorkflowService`.
    """

    def __init__(self, sync_controller) -> None:
        self.sync_controller = sync_controller

    def build_result(
        self,
        activities,
        error,
        cancelled,
        provider,
    ) -> FetchResult:
        """Wrap raw :class:`FetchTask` callback parameters into a :class:`FetchResult`.

        Parameters match the keyword arguments emitted by
        :meth:`FetchTask.finished`.
        """
        if cancelled:
            return FetchResult(cancelled=True, status_text="Fetch cancelled.")

        if error is not None:
            return FetchResult(
                error=error,
                status_text="Strava fetch failed",
            )

        metadata = self.sync_controller.build_sync_metadata(activities, provider)
        status_text = self.sync_controller.fetch_status_text(
            provider, len(activities), metadata["detailed_count"],
        )
        return FetchResult(
            activities=activities,
            metadata=metadata,
            status_text=status_text,
        )
