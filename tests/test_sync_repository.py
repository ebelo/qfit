import tempfile
import unittest
import sqlite3
from pathlib import Path
from unittest.mock import patch

from tests import _path  # noqa: F401
from qfit.activities.domain.models import Activity
from qfit.sync_repository import ActivitySyncState, SyncRepository


class SyncRepositoryTests(unittest.TestCase):
    def _activity(self, **overrides):
        payload = {
            "source": "strava",
            "source_activity_id": "42",
            "name": "Morning Ride",
            "activity_type": "Ride",
            "sport_type": "Ride",
            "start_date": "2026-03-20T06:00:00Z",
            "distance_m": 12345.6,
            "geometry_source": "summary_polyline",
            "geometry_points": [(46.5, 6.6), (46.6, 6.7)],
            "details_json": {"normalized_at": "volatile", "device_name": "Edge"},
        }
        payload.update(overrides)
        return Activity(**payload)

    def test_upsert_and_reload_round_trip(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = SyncRepository(str(Path(tmpdir) / "qfit.sqlite"))
            repo.ensure_schema()

            result = repo.upsert_activities([self._activity()], sync_metadata={"provider": "strava"})
            self.assertEqual(result.inserted, 1)
            self.assertEqual(result.updated, 0)
            self.assertEqual(result.unchanged, 0)
            self.assertEqual(result.total_count, 1)

            activities = repo.load_all_activities()
            self.assertEqual(len(activities), 1)
            self.assertEqual(activities[0].source_activity_id, "42")
            self.assertEqual(activities[0].geometry_points, [[46.5, 6.6], [46.6, 6.7]])
            self.assertEqual(activities[0].details_json["device_name"], "Edge")

    def test_volatile_detail_keys_do_not_force_updates(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = SyncRepository(str(Path(tmpdir) / "qfit.sqlite"))
            repo.ensure_schema()

            repo.upsert_activities([self._activity(details_json={"normalized_at": "one", "device_name": "Edge"})])
            result = repo.upsert_activities(
                [self._activity(details_json={"normalized_at": "two", "device_name": "Edge"})]
            )

            self.assertEqual(result.inserted, 0)
            self.assertEqual(result.updated, 0)
            self.assertEqual(result.unchanged, 1)

    def test_meaningful_changes_are_reported_as_updates(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = SyncRepository(str(Path(tmpdir) / "qfit.sqlite"))
            repo.ensure_schema()

            repo.upsert_activities([self._activity(distance_m=1000.0)])
            result = repo.upsert_activities([self._activity(distance_m=2000.0)])

            self.assertEqual(result.inserted, 0)
            self.assertEqual(result.updated, 1)
            self.assertEqual(result.unchanged, 0)

    def test_sync_state_is_written(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = SyncRepository(str(Path(tmpdir) / "qfit.sqlite"))
            repo.ensure_schema()
            repo.upsert_activities(
                [self._activity()],
                sync_metadata={
                    "provider": "strava",
                    "fetched_count": 1,
                    "stream_stats": {"downloaded": 1},
                    "rate_limit": {"short_remaining": 100},
                    "is_full_sync": True,
                    "before_epoch": 200,
                    "after_epoch": 100,
                },
            )

            rows = repo._connect().execute("SELECT * FROM sync_state").fetchall()
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0][0], "strava")

    def test_load_activity_sync_state_returns_completed_metadata(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = SyncRepository(str(Path(tmpdir) / "qfit.sqlite"))
            repo.ensure_schema()
            repo.upsert_activities(
                [
                    self._activity(source_activity_id="old", start_date="2026-03-19T06:00:00Z"),
                    self._activity(source_activity_id="new", start_date="2026-03-20T06:00:00Z"),
                ],
                sync_metadata={
                    "provider": "strava",
                    "is_full_sync": True,
                    "before_epoch": 200,
                    "after_epoch": 100,
                },
            )

            state = repo.load_activity_sync_state(provider="strava")

            self.assertIsInstance(state, ActivitySyncState)
            self.assertTrue(state.has_completed_sync)
            self.assertTrue(repo.has_completed_activity_sync(provider="strava"))
            self.assertEqual(state.provider, "strava")
            self.assertIsNotNone(state.last_full_sync_at)
            self.assertEqual(state.last_before_epoch, 200)
            self.assertEqual(state.last_after_epoch, 100)
            self.assertEqual(state.stored_activity_count, 2)
            self.assertEqual(state.latest_activity_start_date, "2026-03-20T06:00:00Z")

    def test_load_activity_sync_state_returns_none_before_completed_sync(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = SyncRepository(str(Path(tmpdir) / "qfit.sqlite"))

            self.assertIsNone(repo.load_activity_sync_state(provider="strava"))
            self.assertFalse(repo.has_completed_activity_sync(provider="strava"))

            repo.ensure_schema()
            self.assertIsNone(repo.load_activity_sync_state(provider="strava"))

    def test_load_activity_sync_state_only_suppresses_missing_schema_errors(self):
        repo = SyncRepository(":memory:")

        with patch.object(
            repo,
            "_connect",
            side_effect=sqlite3.OperationalError("database is locked"),
        ):
            with self.assertRaises(sqlite3.OperationalError):
                repo.load_activity_sync_state(provider="strava")

    def test_load_activity_sync_state_returns_none_for_existing_uninitialized_database(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "empty.sqlite"
            db_path.touch()
            repo = SyncRepository(str(db_path))

            self.assertIsNone(repo.load_activity_sync_state(provider="strava"))

    def test_ensure_schema_creates_activity_registry_indexes_idempotently(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = SyncRepository(str(Path(tmpdir) / "qfit.sqlite"))

            repo.ensure_schema()
            repo.ensure_schema()

            index_rows = repo._connect().execute("PRAGMA index_list('activity_registry')").fetchall()
            index_names = {row[1] for row in index_rows}

            self.assertTrue({
                "idx_activity_registry_start_date",
                "idx_activity_registry_type",
                "idx_activity_registry_source_start_date",
                "idx_activity_registry_start_date_local",
                "idx_activity_registry_sport_type",
                "idx_activity_registry_distance_m",
                "idx_activity_registry_last_synced_at",
            }.issubset(index_names))


class SyncUnchangedBehaviorTests(unittest.TestCase):
    """Verify that re-syncing identical activities does not rewrite rows."""

    def _activity(self, **overrides):
        payload = {
            "source": "strava",
            "source_activity_id": "100",
            "name": "Evening Run",
            "activity_type": "Run",
            "sport_type": "Run",
            "start_date": "2026-03-20T18:00:00Z",
            "distance_m": 5000.0,
            "geometry_source": "summary_polyline",
            "geometry_points": [(46.2, 6.1)],
            "details_json": {"device_name": "Forerunner"},
        }
        payload.update(overrides)
        return Activity(**payload)

    def test_unchanged_rows_not_rewritten(self):
        """Re-upserting the same activity leaves last_synced_at unchanged in the row."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = SyncRepository(str(Path(tmpdir) / "qfit.sqlite"))
            repo.ensure_schema()

            repo.upsert_activities([self._activity()])
            conn = repo._connect()
            row_before = conn.execute(
                "SELECT last_synced_at, first_seen_at FROM activity_registry WHERE source_activity_id = '100'"
            ).fetchone()
            conn.close()

            # Re-upsert the same activity — should be unchanged, no row write
            result = repo.upsert_activities([self._activity()])
            self.assertEqual(result.unchanged, 1)
            self.assertEqual(result.inserted, 0)
            self.assertEqual(result.updated, 0)

            conn = repo._connect()
            row_after = conn.execute(
                "SELECT last_synced_at, first_seen_at FROM activity_registry WHERE source_activity_id = '100'"
            ).fetchone()
            conn.close()

            # Row was not rewritten: timestamps match exactly
            self.assertEqual(row_before[0], row_after[0])
            self.assertEqual(row_before[1], row_after[1])

    def test_first_seen_at_preserved_on_update(self):
        """When a row is updated, first_seen_at stays at the original insert time."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = SyncRepository(str(Path(tmpdir) / "qfit.sqlite"))
            repo.ensure_schema()

            repo.upsert_activities([self._activity(distance_m=1000.0)])
            conn = repo._connect()
            original_first_seen = conn.execute(
                "SELECT first_seen_at FROM activity_registry WHERE source_activity_id = '100'"
            ).fetchone()[0]
            conn.close()

            # Update with different distance
            repo.upsert_activities([self._activity(distance_m=2000.0)])
            conn = repo._connect()
            updated_first_seen = conn.execute(
                "SELECT first_seen_at FROM activity_registry WHERE source_activity_id = '100'"
            ).fetchone()[0]
            conn.close()

            self.assertEqual(original_first_seen, updated_first_seen)

    def test_last_synced_at_updated_on_real_change(self):
        """When a row is genuinely updated, last_synced_at advances."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = SyncRepository(str(Path(tmpdir) / "qfit.sqlite"))
            repo.ensure_schema()

            repo.upsert_activities([self._activity(distance_m=1000.0)])
            conn = repo._connect()
            ts_before = conn.execute(
                "SELECT last_synced_at FROM activity_registry WHERE source_activity_id = '100'"
            ).fetchone()[0]
            conn.close()

            result = repo.upsert_activities([self._activity(distance_m=2000.0)])
            self.assertEqual(result.updated, 1)

            conn = repo._connect()
            ts_after = conn.execute(
                "SELECT last_synced_at FROM activity_registry WHERE source_activity_id = '100'"
            ).fetchone()[0]
            conn.close()

            self.assertGreaterEqual(ts_after, ts_before)

    def test_counters_correct_for_mixed_batch(self):
        """A batch with new, changed, and unchanged activities reports correct counters."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = SyncRepository(str(Path(tmpdir) / "qfit.sqlite"))
            repo.ensure_schema()

            # Seed two activities
            repo.upsert_activities([
                self._activity(source_activity_id="A", distance_m=100.0),
                self._activity(source_activity_id="B", distance_m=200.0),
            ])

            # Re-sync: A unchanged, B updated, C new
            result = repo.upsert_activities([
                self._activity(source_activity_id="A", distance_m=100.0),   # unchanged
                self._activity(source_activity_id="B", distance_m=999.0),   # updated
                self._activity(source_activity_id="C", distance_m=300.0),   # new
            ])

            self.assertEqual(result.unchanged, 1)
            self.assertEqual(result.updated, 1)
            self.assertEqual(result.inserted, 1)
            self.assertEqual(result.total_count, 3)

    def test_volatile_keys_do_not_affect_unchanged_detection(self):
        """Changing only volatile detail keys keeps the row unchanged."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = SyncRepository(str(Path(tmpdir) / "qfit.sqlite"))
            repo.ensure_schema()

            repo.upsert_activities([self._activity(
                details_json={"device_name": "Edge", "stream_enriched_at": "t1", "stream_cache": "c1"}
            )])
            result = repo.upsert_activities([self._activity(
                details_json={"device_name": "Edge", "stream_enriched_at": "t2", "stream_cache": "c2"}
            )])

            self.assertEqual(result.unchanged, 1)
            self.assertEqual(result.updated, 0)

    def test_detailed_route_status_is_persisted_and_treated_as_meaningful(self):
        """Detailed-route status should be stored and should trigger updates when it changes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = SyncRepository(str(Path(tmpdir) / "qfit.sqlite"))
            repo.ensure_schema()

            repo.upsert_activities([self._activity(details_json={"device_name": "Edge", "detailed_route_status": "cached"})])
            stored = repo.load_all_activities()[0]
            self.assertEqual(stored.details_json["detailed_route_status"], "cached")

            result = repo.upsert_activities(
                [self._activity(details_json={"device_name": "Edge", "detailed_route_status": "downloaded"})]
            )

            self.assertEqual(result.updated, 1)
            self.assertEqual(result.unchanged, 0)

    def test_non_volatile_detail_change_triggers_update(self):
        """Changing a non-volatile detail key triggers an update."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = SyncRepository(str(Path(tmpdir) / "qfit.sqlite"))
            repo.ensure_schema()

            repo.upsert_activities([self._activity(details_json={"device_name": "Edge"})])
            result = repo.upsert_activities([self._activity(details_json={"device_name": "Fenix"})])

            self.assertEqual(result.updated, 1)
            self.assertEqual(result.unchanged, 0)

    def test_sync_stats_json_records_counters(self):
        """sync_state.last_sync_stats_json contains the correct counters."""
        import json

        with tempfile.TemporaryDirectory() as tmpdir:
            repo = SyncRepository(str(Path(tmpdir) / "qfit.sqlite"))
            repo.ensure_schema()

            repo.upsert_activities([self._activity()])
            repo.upsert_activities(
                [self._activity()],
                sync_metadata={"provider": "strava", "fetched_count": 1},
            )

            conn = repo._connect()
            stats_raw = conn.execute(
                "SELECT last_sync_stats_json FROM sync_state WHERE provider = 'strava'"
            ).fetchone()[0]
            conn.close()

            stats = json.loads(stats_raw)
            self.assertEqual(stats["unchanged"], 1)
            self.assertEqual(stats["inserted"], 0)
            self.assertEqual(stats["updated"], 0)
            self.assertEqual(stats["stored_total"], 1)

    def test_full_sync_prunes_missing_activities_for_same_provider(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = SyncRepository(str(Path(tmpdir) / "qfit.sqlite"))
            repo.ensure_schema()

            repo.upsert_activities([
                self._activity(source_activity_id="A", distance_m=100.0),
                self._activity(source_activity_id="B", distance_m=200.0),
            ])

            result = repo.upsert_activities(
                [self._activity(source_activity_id="A", distance_m=100.0)],
                sync_metadata={"provider": "strava", "is_full_sync": True},
            )

            self.assertEqual(result.total_count, 1)
            stored_ids = [activity.source_activity_id for activity in repo.load_all_activities()]
            self.assertEqual(stored_ids, ["A"])

    def test_incremental_sync_keeps_missing_activities(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = SyncRepository(str(Path(tmpdir) / "qfit.sqlite"))
            repo.ensure_schema()

            repo.upsert_activities([
                self._activity(source_activity_id="A", distance_m=100.0),
                self._activity(source_activity_id="B", distance_m=200.0),
            ])

            result = repo.upsert_activities(
                [self._activity(source_activity_id="A", distance_m=100.0)],
                sync_metadata={"provider": "strava", "is_full_sync": False},
            )

            self.assertEqual(result.total_count, 2)
            stored_ids = sorted(activity.source_activity_id for activity in repo.load_all_activities())
            self.assertEqual(stored_ids, ["A", "B"])

    def test_full_sync_prune_uses_temp_table_for_large_id_sets(self):
        repo = SyncRepository(":memory:")

        class RecordingCursor:
            def __init__(self):
                self.execute_calls = []
                self.executemany_calls = []

            def execute(self, sql, params=()):
                self.execute_calls.append((sql, tuple(params) if isinstance(params, list) else params))
                return self

            def executemany(self, sql, seq_of_params):
                self.executemany_calls.append((sql, list(seq_of_params)))
                return self

        cursor = RecordingCursor()
        activities = [
            self._activity(source_activity_id=str(index), distance_m=float(index))
            for index in range(1100)
        ]

        repo._prune_missing_activities(
            cursor,
            activities,
            sync_metadata={"provider": "strava", "is_full_sync": True},
        )

        self.assertEqual(cursor.execute_calls[0][0], "CREATE TEMP TABLE IF NOT EXISTS incoming_sync_ids (source_activity_id TEXT PRIMARY KEY)")
        self.assertEqual(cursor.execute_calls[1][0], "DELETE FROM incoming_sync_ids")
        insert_sql, insert_rows = cursor.executemany_calls[0]
        self.assertEqual(insert_sql, "INSERT INTO incoming_sync_ids (source_activity_id) VALUES (?)")
        self.assertEqual(len(insert_rows), 1100)
        delete_sql, delete_params = cursor.execute_calls[2]
        self.assertIn("NOT EXISTS", delete_sql)
        self.assertEqual(delete_params, ("strava",))


if __name__ == "__main__":
    unittest.main()
