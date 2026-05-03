from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum

from ...sync_repository import ActivitySyncState

DEFAULT_INCREMENTAL_OVERLAP_SECONDS = 3 * 24 * 60 * 60


class ActivitySyncMode(str, Enum):
    """User-visible reasons for fetching activity summaries."""

    INITIAL_IMPORT = "initial_import"
    INCREMENTAL_UPDATE = "incremental_update"
    HISTORICAL_BACKFILL = "historical_backfill"


@dataclass(frozen=True)
class ActivitySyncPlan:
    """Fetch bounds selected for one activity-sync run."""

    mode: ActivitySyncMode
    before_epoch: int | None = None
    after_epoch: int | None = None
    overlap_seconds: int = 0

    @property
    def is_bounded(self) -> bool:
        return self.before_epoch is not None or self.after_epoch is not None


def plan_activity_sync(
    sync_state: ActivitySyncState | None,
    *,
    requested_mode: ActivitySyncMode | str | None = None,
    incremental_overlap_seconds: int = DEFAULT_INCREMENTAL_OVERLAP_SECONDS,
    backfill_before_epoch: int | None = None,
    backfill_after_epoch: int | None = None,
) -> ActivitySyncPlan:
    """Choose the fetch mode and provider bounds for an activity-sync run."""

    mode = _normalize_mode(requested_mode) or _default_mode(sync_state)
    if mode == ActivitySyncMode.INCREMENTAL_UPDATE:
        return ActivitySyncPlan(
            mode=mode,
            after_epoch=_incremental_after_epoch(
                sync_state,
                overlap_seconds=incremental_overlap_seconds,
            ),
            overlap_seconds=max(int(incremental_overlap_seconds), 0),
        )
    if mode == ActivitySyncMode.HISTORICAL_BACKFILL:
        return ActivitySyncPlan(
            mode=mode,
            before_epoch=backfill_before_epoch,
            after_epoch=backfill_after_epoch,
        )
    return ActivitySyncPlan(mode=ActivitySyncMode.INITIAL_IMPORT)


def _default_mode(sync_state: ActivitySyncState | None) -> ActivitySyncMode:
    if sync_state and sync_state.has_completed_sync and sync_state.latest_activity_start_date:
        return ActivitySyncMode.INCREMENTAL_UPDATE
    return ActivitySyncMode.INITIAL_IMPORT


def _incremental_after_epoch(
    sync_state: ActivitySyncState | None,
    *,
    overlap_seconds: int,
) -> int | None:
    if sync_state is None or not sync_state.latest_activity_start_date:
        return None
    start_epoch = _parse_activity_start_epoch(sync_state.latest_activity_start_date)
    if start_epoch is None:
        return None
    return max(start_epoch - max(int(overlap_seconds), 0), 0)


def _parse_activity_start_epoch(value: str) -> int | None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return int(parsed.timestamp())


def _normalize_mode(mode: ActivitySyncMode | str | None) -> ActivitySyncMode | None:
    if mode is None:
        return None
    if isinstance(mode, ActivitySyncMode):
        return mode
    try:
        return ActivitySyncMode(str(mode))
    except ValueError:
        return None
