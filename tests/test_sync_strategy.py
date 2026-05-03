import unittest

from tests import _path  # noqa: F401
from qfit.activities.application.sync_strategy import (
    ActivitySyncMode,
    DEFAULT_INCREMENTAL_OVERLAP_SECONDS,
    plan_activity_sync,
)
from qfit.sync_repository import ActivitySyncState


class ActivitySyncStrategyTests(unittest.TestCase):
    def test_defaults_to_initial_import_without_completed_sync_state(self):
        plan = plan_activity_sync(None)

        self.assertEqual(plan.mode, ActivitySyncMode.INITIAL_IMPORT)
        self.assertFalse(plan.is_bounded)

    def test_defaults_to_incremental_update_with_completed_sync_state(self):
        state = ActivitySyncState(
            provider="strava",
            last_success_status="ok",
            updated_at="2026-05-03T20:00:00+00:00",
            latest_activity_start_date="2026-05-03T12:00:00Z",
        )

        plan = plan_activity_sync(state)

        self.assertEqual(plan.mode, ActivitySyncMode.INCREMENTAL_UPDATE)
        self.assertEqual(plan.overlap_seconds, DEFAULT_INCREMENTAL_OVERLAP_SECONDS)
        self.assertEqual(plan.after_epoch, 1777550400)
        self.assertIsNone(plan.before_epoch)

    def test_incremental_overlap_can_be_overridden(self):
        state = ActivitySyncState(
            provider="strava",
            last_success_status="ok",
            updated_at="2026-05-03T20:00:00+00:00",
            latest_activity_start_date="2026-05-03T12:00:00+00:00",
        )

        plan = plan_activity_sync(state, incremental_overlap_seconds=3600)

        self.assertEqual(plan.after_epoch, 1777806000)
        self.assertEqual(plan.overlap_seconds, 3600)

    def test_explicit_historical_backfill_preserves_requested_bounds(self):
        state = ActivitySyncState(
            provider="strava",
            last_success_status="ok",
            updated_at="2026-05-03T20:00:00+00:00",
            latest_activity_start_date="2026-05-03T12:00:00Z",
        )

        plan = plan_activity_sync(
            state,
            requested_mode="historical_backfill",
            backfill_before_epoch=200,
            backfill_after_epoch=100,
        )

        self.assertEqual(plan.mode, ActivitySyncMode.HISTORICAL_BACKFILL)
        self.assertEqual(plan.before_epoch, 200)
        self.assertEqual(plan.after_epoch, 100)

    def test_invalid_latest_start_date_keeps_incremental_unbounded_for_caller_safety(self):
        state = ActivitySyncState(
            provider="strava",
            last_success_status="ok",
            updated_at="2026-05-03T20:00:00+00:00",
            latest_activity_start_date="not-a-date",
        )

        plan = plan_activity_sync(state)

        self.assertEqual(plan.mode, ActivitySyncMode.INCREMENTAL_UPDATE)
        self.assertIsNone(plan.after_epoch)

    def test_unrecognized_requested_mode_falls_back_to_state_default(self):
        state = ActivitySyncState(
            provider="strava",
            last_success_status="ok",
            updated_at="2026-05-03T20:00:00+00:00",
            latest_activity_start_date="2026-05-03T12:00:00Z",
        )

        plan = plan_activity_sync(state, requested_mode="future_mode")

        self.assertEqual(plan.mode, ActivitySyncMode.INCREMENTAL_UPDATE)
        self.assertIsNotNone(plan.after_epoch)


if __name__ == "__main__":
    unittest.main()
