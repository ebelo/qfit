import tempfile
import unittest
import sqlite3
import json
from pathlib import Path
from unittest.mock import patch

from tests import _path  # noqa: F401
from qfit.activities.application.sync_strategy import (
    ActivitySyncMode,
    plan_activity_sync,
)
from qfit.activities.domain.models import Activity
from qfit.sync_repository import (
    ActivityDetailPayloadError,
    ActivitySyncState,
    DetailedRouteCoverage,
    SyncRepository,
)


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
            self.assertEqual(result.inserted_keys, (("strava", "42"),))
            self.assertEqual(result.updated_keys, ())
            self.assertEqual(result.unchanged_keys, ())
            self.assertEqual(result.removed_keys, ())
            self.assertEqual(result.changed_keys, (("strava", "42"),))
            self.assertTrue(result.has_derived_changes)

            activities = repo.load_all_activities()
            self.assertEqual(len(activities), 1)
            self.assertEqual(activities[0].source_activity_id, "42")
            self.assertEqual(activities[0].geometry_points, [[46.5, 6.6], [46.6, 6.7]])
            self.assertEqual(activities[0].details_json["device_name"], "Edge")

    def test_compressed_detail_payload_round_trips_without_registry_duplication(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = SyncRepository(str(Path(tmpdir) / "qfit.sqlite"))
            repo.ensure_schema()
            activity = self._activity(
                geometry_source="stream",
                details_json={
                    "device_name": "Edge",
                    "stream_metrics": {
                        "distance": [0.0, 100.0],
                        "altitude": [450.0, 455.0],
                    },
                },
            )

            repo.upsert_activities([activity], compress_detail_payloads=True)

            with repo._connect() as connection:
                registry = connection.execute(
                    "SELECT geometry_points_json, details_json FROM activity_registry"
                ).fetchone()
                payload = connection.execute(
                    "SELECT encoding, point_count, length(payload_zlib) FROM activity_detail_payloads"
                ).fetchone()
            self.assertEqual(registry["geometry_points_json"], "[]")
            self.assertNotIn("stream_metrics", json.loads(registry["details_json"]))
            self.assertEqual(payload["encoding"], "json+zlib-v1")
            self.assertEqual(payload["point_count"], 2)
            self.assertGreater(payload["length(payload_zlib)"], 0)

            stored = repo.load_all_activities()[0]
            self.assertEqual(stored.geometry_points, [[46.5, 6.6], [46.6, 6.7]])
            self.assertEqual(
                stored.details_json["stream_metrics"]["altitude"],
                [450.0, 455.0],
            )

    def test_compressed_detail_reimport_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = SyncRepository(str(Path(tmpdir) / "qfit.sqlite"))
            repo.ensure_schema()
            activity = self._activity(
                geometry_source="stream",
                details_json={
                    "bulk_imported_at": "first",
                    "stream_metrics": {"distance": [0.0, 100.0]},
                },
            )
            repo.upsert_activities([activity], compress_detail_payloads=True)
            changed_timestamp = self._activity(
                geometry_source="stream",
                details_json={
                    "bulk_imported_at": "second",
                    "stream_metrics": {"distance": [0.0, 100.0]},
                },
            )

            result = repo.upsert_activities(
                [changed_timestamp],
                compress_detail_payloads=True,
            )

            self.assertEqual(result.unchanged, 1)
            self.assertEqual(result.updated, 0)
            self.assertEqual(result.unchanged_keys, (("strava", "42"),))
            self.assertEqual(result.changed_keys, ())
            self.assertFalse(result.has_derived_changes)

    def test_full_sync_reports_pruned_activity_keys(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = SyncRepository(str(Path(tmpdir) / "qfit.sqlite"))
            repo.ensure_schema()
            repo.upsert_activities(
                [
                    self._activity(source_activity_id="keep"),
                    self._activity(source_activity_id="remove"),
                ],
                sync_metadata={"provider": "strava", "is_full_sync": True},
            )

            result = repo.upsert_activities(
                [self._activity(source_activity_id="keep")],
                sync_metadata={"provider": "strava", "is_full_sync": True},
            )

            self.assertEqual(result.unchanged_keys, (("strava", "keep"),))
            self.assertEqual(result.removed_keys, (("strava", "remove"),))
            self.assertEqual(result.changed_keys, (("strava", "remove"),))
            self.assertTrue(result.has_derived_changes)

    def test_derived_dirty_journal_survives_unchanged_retry_until_cleared(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = SyncRepository(str(Path(tmpdir) / "qfit.sqlite"))
            repo.ensure_schema()

            inserted = repo.upsert_activities([self._activity()])
            pending_insert = repo.with_pending_derived_changes(inserted)
            self.assertEqual(
                pending_insert.pending_derived_keys,
                (("strava", "42"),),
            )

            unchanged = repo.upsert_activities([self._activity()])
            pending_retry = repo.with_pending_derived_changes(unchanged)
            self.assertEqual(unchanged.changed_keys, ())
            self.assertEqual(pending_retry.changed_keys, (("strava", "42"),))
            self.assertTrue(pending_retry.has_derived_changes)

            repo.clear_derived_dirty()
            clean = repo.with_pending_derived_changes(unchanged)
            self.assertEqual(clean.changed_keys, ())
            self.assertFalse(clean.has_derived_changes)

            self.assertIsNone(repo.load_derived_publication_signature())
            repo.record_derived_publication_signature("settings-v1")
            self.assertEqual(
                repo.load_derived_publication_signature(),
                "settings-v1",
            )

    def test_corrupt_detail_payload_is_reported_and_bulk_reimport_repairs_it(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = SyncRepository(str(Path(tmpdir) / "qfit.sqlite"))
            repo.ensure_schema()
            activity = self._activity(
                geometry_source="stream",
                details_json={
                    "stream_metrics": {
                        "distance": [0.0, 100.0],
                        "altitude": [450.0, 455.0],
                    },
                },
            )
            repo.upsert_activities([activity], compress_detail_payloads=True)
            with repo._connect() as connection:
                connection.execute(
                    "UPDATE activity_detail_payloads SET payload_zlib = ?",
                    (b"not-zlib",),
                )
                connection.commit()

            with self.assertRaises(ActivityDetailPayloadError):
                repo.load_all_activities()
            lower_fidelity = self._activity(
                geometry_source="summary_polyline",
                geometry_points=[(46.5, 6.6)],
            )
            with self.assertRaises(ActivityDetailPayloadError):
                repo.upsert_activities([lower_fidelity])

            repaired = repo.upsert_activities(
                [activity],
                compress_detail_payloads=True,
            )

            self.assertEqual(repaired.updated, 1)
            stored = repo.load_all_activities()[0]
            self.assertEqual(stored.geometry_points, [[46.5, 6.6], [46.6, 6.7]])
            self.assertEqual(
                stored.details_json["stream_metrics"]["altitude"],
                [450.0, 455.0],
            )

    def test_iter_activity_record_batches_hydrates_with_stable_global_keys(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = SyncRepository(str(Path(tmpdir) / "qfit.sqlite"))
            repo.ensure_schema()
            activities = [
                self._activity(
                    source_activity_id=str(index),
                    start_date=f"2026-03-{index + 10:02d}T06:00:00Z",
                    geometry_source="stream",
                    geometry_points=[(46.0 + index, 7.0)],
                    details_json={"stream_metrics": {"altitude": [500 + index]}},
                )
                for index in range(3)
            ]
            repo.upsert_activities(activities, compress_detail_payloads=True)

            batches = list(repo.iter_activity_record_batches(batch_size=2))

            self.assertEqual([len(batch) for batch in batches], [2, 1])
            records = [record for batch in batches for record in batch]
            self.assertEqual([record["_activity_fk"] for record in records], [1, 2, 3])
            self.assertTrue(all(record["geometry_points"] for record in records))

    def test_load_activity_records_hydrates_only_requested_keys(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = SyncRepository(str(Path(tmpdir) / "qfit.sqlite"))
            repo.ensure_schema()
            repo.upsert_activities(
                [
                    self._activity(
                        source_activity_id=str(index),
                        geometry_source="stream",
                        details_json={"stream_metrics": {"altitude": [500 + index]}},
                    )
                    for index in range(3)
                ],
                compress_detail_payloads=True,
            )

            records = repo.load_activity_records(
                (("strava", "2"), ("strava", "missing"), ("strava", "0"))
            )

            self.assertEqual(
                [record["source_activity_id"] for record in records],
                ["2", "0"],
            )
            self.assertTrue(all(record["_activity_fk"] > 0 for record in records))
            self.assertEqual(
                records[0]["details_json"]["stream_metrics"]["altitude"],
                [502],
            )

    def test_iter_activity_record_batches_keysets_nullable_and_tied_dates(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = SyncRepository(str(Path(tmpdir) / "qfit.sqlite"))
            repo.ensure_schema()
            activities = [
                self._activity(
                    source=source,
                    source_activity_id=activity_id,
                    start_date=start_date,
                )
                for source, activity_id, start_date in (
                    ("strava", "same", "2026-03-20T06:00:00Z"),
                    ("other", "same", "2026-03-20T06:00:00Z"),
                    ("strava", "older", "2026-03-19T06:00:00Z"),
                    ("strava", "undated", None),
                )
            ]
            repo.upsert_activities(activities)

            batches = list(repo.iter_activity_record_batches(batch_size=1))

            records = [record for batch in batches for record in batch]
            self.assertEqual(len(records), 4)
            self.assertEqual(
                {(record["source"], record["source_activity_id"]) for record in records},
                {
                    ("strava", "same"),
                    ("other", "same"),
                    ("strava", "older"),
                    ("strava", "undated"),
                },
            )
            self.assertEqual(
                [record["_activity_fk"] for record in records],
                [1, 2, 3, 4],
            )

    def test_uncompressed_update_replaces_old_detail_payload(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = SyncRepository(str(Path(tmpdir) / "qfit.sqlite"))
            repo.ensure_schema()
            repo.upsert_activities(
                [self._activity(geometry_source="stream")],
                compress_detail_payloads=True,
            )

            repo.upsert_activities(
                [self._activity(geometry_source="summary_polyline", geometry_points=[(1.0, 2.0)])],
                reconcile_existing=False,
            )

            with repo._connect() as connection:
                count = connection.execute(
                    "SELECT COUNT(*) FROM activity_detail_payloads"
                ).fetchone()[0]
            self.assertEqual(count, 0)
            self.assertEqual(repo.load_all_activities()[0].geometry_points, [[1.0, 2.0]])

    def test_full_sync_prunes_orphaned_detail_payloads(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = SyncRepository(str(Path(tmpdir) / "qfit.sqlite"))
            repo.ensure_schema()
            repo.upsert_activities(
                [
                    self._activity(source_activity_id="keep", geometry_source="stream"),
                    self._activity(source_activity_id="remove", geometry_source="stream"),
                ],
                compress_detail_payloads=True,
            )

            repo.upsert_activities(
                [self._activity(source_activity_id="keep", geometry_source="stream")],
                sync_metadata={"provider": "strava", "is_full_sync": True},
            )

            with repo._connect() as connection:
                payload_ids = connection.execute(
                    "SELECT source_activity_id FROM activity_detail_payloads"
                ).fetchall()
            self.assertEqual([row[0] for row in payload_ids], ["keep"])

    def test_api_summary_update_preserves_bulk_detail_and_compressed_storage(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = SyncRepository(str(Path(tmpdir) / "qfit.sqlite"))
            repo.ensure_schema()
            bulk = self._activity(
                geometry_source="stream",
                details_json={
                    "ingest_source": "strava_bulk_export",
                    "ingest_sources": ["strava_bulk_export"],
                    "geometry_ingest_source": "strava_bulk_export",
                    "stream_metrics": {
                        "distance": [0.0, 100.0],
                        "altitude": [450.0, 455.0],
                    },
                    "user_note": "keep me",
                },
            )
            repo.upsert_activities([bulk], compress_detail_payloads=True)
            api_summary = self._activity(
                distance_m=13000.0,
                geometry_source="summary_polyline",
                geometry_points=[(46.5, 6.6)],
                details_json={"ingest_source": "strava_api"},
            )

            result = repo.upsert_activities([api_summary])

            self.assertEqual(result.updated, 1)
            stored = repo.load_all_activities()[0]
            self.assertEqual(stored.distance_m, 13000.0)
            self.assertEqual(stored.geometry_source, "stream")
            self.assertEqual(stored.details_json["user_note"], "keep me")
            self.assertEqual(
                stored.details_json["ingest_sources"],
                ["strava_bulk_export", "strava_api"],
            )
            with repo._connect() as connection:
                payload_count = connection.execute(
                    "SELECT COUNT(*) FROM activity_detail_payloads"
                ).fetchone()[0]
                geometry_json = connection.execute(
                    "SELECT geometry_points_json FROM activity_registry"
                ).fetchone()[0]
            self.assertEqual(payload_count, 1)
            self.assertEqual(geometry_json, "[]")

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

    def test_partial_bulk_batches_do_not_claim_completed_sync(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = SyncRepository(str(Path(tmpdir) / "qfit.sqlite"))
            repo.ensure_schema()

            repo.upsert_activities(
                [self._activity()],
                sync_metadata={"provider": "strava", "suppress_sync_state": True},
                compress_detail_payloads=True,
            )

            rows = repo._connect().execute("SELECT * FROM sync_state").fetchall()
            self.assertEqual(rows, [])

    def test_partial_bulk_batches_skip_repeated_orphan_payload_scan(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = SyncRepository(str(Path(tmpdir) / "qfit.sqlite"))
            repo.ensure_schema()

            with patch.object(
                repo,
                "_prune_orphaned_detail_payloads",
                wraps=repo._prune_orphaned_detail_payloads,
            ) as prune:
                repo.upsert_activities(
                    [self._activity()],
                    sync_metadata={
                        "provider": "strava",
                        "suppress_sync_state": True,
                    },
                    compress_detail_payloads=True,
                )

            prune.assert_not_called()

    def test_bulk_checkpoint_initializes_sync_state_without_overwriting_existing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = SyncRepository(str(Path(tmpdir) / "qfit.sqlite"))
            repo.ensure_schema()
            repo.upsert_activities(
                [self._activity()],
                sync_metadata={"provider": "strava", "suppress_sync_state": True},
            )

            created = repo.record_activity_sync_checkpoint(
                provider="strava",
                fetched_count=1,
                inserted=1,
                is_full_sync=True,
                checkpoint="strava_bulk_import",
            )
            state = repo.load_activity_sync_state("strava")
            with repo._connect() as connection:
                initial_stats = connection.execute(
                    "SELECT last_sync_stats_json FROM sync_state WHERE provider = 'strava'"
                ).fetchone()[0]

            preserved = repo.record_activity_sync_checkpoint(
                provider="strava",
                fetched_count=999,
                checkpoint="replacement",
            )
            with repo._connect() as connection:
                final_stats = connection.execute(
                    "SELECT last_sync_stats_json FROM sync_state WHERE provider = 'strava'"
                ).fetchone()[0]

            self.assertTrue(created)
            self.assertFalse(preserved)
            self.assertTrue(state.has_completed_sync)
            self.assertEqual(state.latest_activity_start_date, "2026-03-20T06:00:00Z")
            self.assertEqual(json.loads(initial_stats)["checkpoint"], "strava_bulk_import")
            self.assertEqual(final_stats, initial_stats)

    def test_bulk_checkpoint_uses_local_manifest_date_when_utc_start_is_absent(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = SyncRepository(str(Path(tmpdir) / "qfit.sqlite"))
            repo.ensure_schema()
            repo.upsert_activities(
                [
                    self._activity(
                        start_date=None,
                        start_date_local="2026-03-20T07:00:00",
                        geometry_source=None,
                        geometry_points=[],
                    )
                ],
                sync_metadata={"provider": "strava", "suppress_sync_state": True},
            )

            repo.record_activity_sync_checkpoint(
                provider="strava",
                fetched_count=1,
                inserted=1,
                is_full_sync=True,
                checkpoint="strava_bulk_import",
            )
            state = repo.load_activity_sync_state("strava")

            self.assertTrue(state.has_completed_sync)
            self.assertEqual(
                state.latest_activity_start_date,
                "2026-03-20T07:00:00",
            )
            plan = plan_activity_sync(state)
            self.assertEqual(plan.mode, ActivitySyncMode.INCREMENTAL_UPDATE)
            self.assertIsNotNone(plan.after_epoch)

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

    def test_load_activity_count_can_filter_provider_without_hydrating_payloads(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = SyncRepository(str(Path(tmpdir) / "qfit.sqlite"))
            repo.ensure_schema()
            repo.upsert_activities(
                [
                    self._activity(source_activity_id="one"),
                    self._activity(source_activity_id="two", source="other"),
                ]
            )

            self.assertEqual(repo.load_activity_count(), 2)
            self.assertEqual(repo.load_activity_count("strava"), 1)

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

    def test_load_detailed_route_coverage_counts_stream_geometry(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = SyncRepository(str(Path(tmpdir) / "qfit.sqlite"))
            repo.ensure_schema()

            repo.upsert_activities([
                self._activity(source_activity_id="stream", geometry_source="stream"),
                self._activity(source_activity_id="summary", geometry_source="summary_polyline"),
                self._activity(source_activity_id="empty", geometry_source="summary_polyline", details_json={
                    "detailed_route_status": "empty",
                }),
            ])

            self.assertEqual(
                repo.load_detailed_route_coverage(provider="strava"),
                DetailedRouteCoverage(detailed_count=1, total_count=3),
            )

    def test_load_detailed_route_coverage_returns_zero_for_missing_database(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = SyncRepository(str(Path(tmpdir) / "missing.sqlite"))

            self.assertEqual(
                repo.load_detailed_route_coverage(provider="strava"),
                DetailedRouteCoverage(),
            )

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

            def fetchall(self):
                return []

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
