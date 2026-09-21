import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from tests import _path  # noqa: F401
from qfit.activities.application.strava_bulk_import import (
    StravaBulkImportProgress,
    StravaBulkImportRequest,
    StravaBulkImportWorkflow,
    reconcile_bulk_activity,
)
from qfit.activities.domain.models import Activity
from qfit.providers.infrastructure.strava_bulk_archive import (
    BulkActivityImportResult,
    BulkArchivePreflight,
    StravaBulkArchiveError,
)
from qfit.sync_repository import SyncStats
from qfit.sync_repository import SyncRepository


def _activity(activity_id, *, points=None, details=None, **overrides):
    payload = {
        "source": "strava",
        "source_activity_id": str(activity_id),
        "name": f"Activity {activity_id}",
        "distance_m": 1000.0,
        "geometry_source": "stream" if points else None,
        "geometry_points": points or [],
        "details_json": details or {"ingest_source": "strava_bulk_export"},
    }
    payload.update(overrides)
    return Activity(**payload)


class _Store:
    def __init__(self, records=None):
        self.records = records or {}

    def load_activity_record(self, source, activity_id):
        return self.records.get((source, str(activity_id)))

    def load_all_activity_records(self):
        return list(self.records.values())


class _Writer:
    def __init__(self, store):
        self.store = store
        self.batches = []
        self.rebuilt = False

    def prepare_activity_storage(self):
        return self.store

    def upsert_activity_batch(self, store, activities, *, compress_detail_payloads):
        self.batches.append((list(activities), compress_detail_payloads))
        inserted = 0
        updated = 0
        unchanged = 0
        for activity in activities:
            key = (activity.source, activity.source_activity_id)
            record = activity.to_record()
            if key not in store.records:
                inserted += 1
            elif store.records[key] == record:
                unchanged += 1
            else:
                updated += 1
            store.records[key] = record
        return SyncStats(inserted, updated, unchanged, len(store.records))

    def rebuild_activity_layers(self, *, activity_store):
        self.rebuilt = True
        return {"activity_tracks": SimpleNamespace(featureCount=lambda: len(activity_store.records))}


class _Reader:
    def __init__(self, results, preflight):
        self.results = results
        self.value = preflight

    def preflight(self, progress=None, cancelled=None):
        if cancelled and cancelled():
            raise AssertionError("test preflight unexpectedly cancelled")
        if progress:
            progress("validation")
            progress("manifest_parsing")
            progress("archive_integrity")
        return self.value

    def iter_activity_results(
        self,
        *,
        cancelled=None,
        progress=None,
        integrity_progress=None,
    ):
        if integrity_progress:
            integrity_progress(5, 10)
            integrity_progress(10, 10)
        for index, result in enumerate(self.results, start=1):
            if cancelled and cancelled():
                return
            yield result
            if progress:
                progress(index, len(self.results))


class StravaBulkImportWorkflowTests(unittest.TestCase):
    def test_phase_weighted_progress_is_monotonic_across_rebuild(self):
        values = [
            StravaBulkImportProgress("validation").percent,
            StravaBulkImportProgress("manifest_parsing").percent,
            StravaBulkImportProgress("archive_integrity").percent,
            StravaBulkImportProgress("archive_integrity", 5, 10).percent,
            StravaBulkImportProgress("archive_integrity", 10, 10).percent,
            StravaBulkImportProgress("activity_parsing", 10, 10).percent,
            StravaBulkImportProgress("derived_layers", 0, 30).percent,
            StravaBulkImportProgress("derived_layers", 30, 30).percent,
            StravaBulkImportProgress("complete").percent,
        ]

        self.assertEqual(values, sorted(values))
        self.assertEqual(values[-1], 100.0)

    def _workflow(self, results, *, store=None):
        preflight = BulkArchivePreflight(
            archive_fingerprint="abc",
            activity_count=len(results),
            referenced_file_count=len(results),
            summary_only_count=0,
            conflict_count=0,
            missing_file_count=0,
            unsupported_file_count=0,
        )
        reader = _Reader(results, preflight)
        writer = _Writer(store or _Store())
        workflow = StravaBulkImportWorkflow(
            reader_factory=lambda _archive_path: reader,
            writer_factory=lambda **_kwargs: writer,
        )
        return workflow, writer

    def test_batches_writes_and_rebuilds_once(self):
        results = [
            BulkActivityImportResult(i + 2, str(i), "detailed_profile", _activity(i, points=[(1, 2)]))
            for i in range(5)
        ]
        workflow, writer = self._workflow(results)
        progress = []

        result = workflow.run(
            StravaBulkImportRequest("export.zip", "qfit.gpkg", batch_size=2),
            progress=progress.append,
        )

        self.assertEqual([len(batch[0]) for batch in writer.batches], [2, 2, 1])
        self.assertTrue(all(batch[1] for batch in writer.batches))
        self.assertTrue(writer.rebuilt)
        self.assertEqual(result.inserted, 5)
        self.assertEqual(result.total_stored, 5)
        self.assertEqual(result.layer_counts["activity_tracks"], 5)
        self.assertEqual(progress[-1].phase, "complete")
        self.assertEqual(progress[-1].percent, 100.0)
        integrity_updates = [
            item for item in progress
            if item.phase == "archive_integrity" and item.total
        ]
        self.assertEqual(
            [item.completed for item in integrity_updates],
            [5, 10],
        )
        self.assertEqual(integrity_updates[-1].message, "Verified 10 B of 10 B")
        phases = {item.phase for item in progress}
        self.assertTrue(
            {
                "validation",
                "manifest_parsing",
                "archive_integrity",
                "activity_parsing",
                "reconciliation",
                "derived_layers",
                "complete",
            }.issubset(phases)
        )

    def test_confirmed_archive_fingerprint_is_checked_before_writing(self):
        workflow, writer = self._workflow(
            [BulkActivityImportResult(2, "1", "summary_only", _activity("1"))]
        )
        request = StravaBulkImportRequest(
            "export.zip",
            "qfit.gpkg",
            expected_archive_fingerprint="different",
        )

        with self.assertRaisesRegex(StravaBulkArchiveError, "changed after confirmation"):
            workflow.run(request)

        self.assertEqual(writer.batches, [])
        self.assertFalse(writer.rebuilt)

    def test_member_failures_are_counted_without_aborting_valid_rows(self):
        results = [
            BulkActivityImportResult(2, "1", "failed", _activity("1"), "invalid_activity_file"),
            BulkActivityImportResult(3, "2", "detailed_no_altitude", _activity("2", points=[(1, 2)])),
            BulkActivityImportResult(4, "3", "summary_only", _activity("3")),
        ]
        workflow, _writer = self._workflow(results)

        result = workflow.run(StravaBulkImportRequest("export.zip", "qfit.gpkg"))

        self.assertEqual(result.failed, 1)
        self.assertEqual(result.no_altitude, 1)
        self.assertEqual(result.summary_only, 1)
        self.assertEqual(result.imported_count, 3)
        report = result.private_diagnostic_report()
        self.assertIn("activity_id=1 status=failed reason=invalid_activity_file", report)
        self.assertNotIn("export.zip", report)

    def test_detailed_reimport_repairs_corrupt_stored_payload(self):
        activity = _activity(
            "42",
            points=[(46.5, 6.6), (46.6, 6.7)],
            details={"stream_metrics": {"altitude": [450.0, 455.0]}},
        )
        result = BulkActivityImportResult(2, "42", "detailed_profile", activity)

        with tempfile.TemporaryDirectory() as temp_dir:
            repository = SyncRepository(str(Path(temp_dir) / "qfit.sqlite"))
            repository.ensure_schema()
            repository.upsert_activities([activity], compress_detail_payloads=True)
            with repository._connect() as connection:
                connection.execute(
                    "UPDATE activity_detail_payloads SET payload_zlib = ?",
                    (b"not-zlib",),
                )
                connection.commit()

            class RepositoryWriter(_Writer):
                def __init__(self):
                    super().__init__(repository)

                def upsert_activity_batch(self, store, activities, *, compress_detail_payloads):
                    return store.upsert_activities(
                        activities,
                        sync_metadata={"provider": "strava", "suppress_sync_state": True},
                        compress_detail_payloads=compress_detail_payloads,
                        reconcile_existing=True,
                    )

                def rebuild_activity_layers(self, *, activity_store):
                    self.rebuilt = True
                    return {
                        "activity_tracks": SimpleNamespace(
                            featureCount=activity_store.load_activity_count
                        )
                    }

            preflight = BulkArchivePreflight(
                archive_fingerprint="abc",
                activity_count=1,
                referenced_file_count=1,
                summary_only_count=0,
                conflict_count=0,
                missing_file_count=0,
                unsupported_file_count=0,
            )
            reader = _Reader([result], preflight)
            workflow = StravaBulkImportWorkflow(
                reader_factory=lambda _path: reader,
                writer_factory=lambda **_kwargs: RepositoryWriter(),
            )

            imported = workflow.run(
                StravaBulkImportRequest("export.zip", "qfit.gpkg")
            )

            self.assertEqual(imported.updated, 1)
            self.assertEqual(
                repository.load_all_activities()[0].details_json["stream_metrics"]["altitude"],
                [450.0, 455.0],
            )

    def test_cancellation_commits_coherent_batch_and_skips_layer_rebuild(self):
        results = [
            BulkActivityImportResult(i + 2, str(i), "summary_only", _activity(i))
            for i in range(4)
        ]
        workflow, writer = self._workflow(results)
        calls = 0

        def cancelled():
            nonlocal calls
            calls += 1
            return calls >= 4

        result = workflow.run(
            StravaBulkImportRequest("export.zip", "qfit.gpkg", batch_size=10),
            cancelled=cancelled,
        )

        self.assertTrue(result.cancelled)
        self.assertFalse(writer.rebuilt)
        self.assertEqual(len(writer.batches), 1)
        self.assertGreaterEqual(result.total_stored, 1)


class ReconcileBulkActivityTests(unittest.TestCase):
    def test_preserves_richer_api_geometry_and_local_annotations(self):
        existing = _activity(
            "42",
            points=[(10, 20), (11, 21)],
            details={
                "ingest_source": "strava_api",
                "ingest_sources": ["strava_api"],
                "geometry_ingest_source": "strava_api",
                "stream_metrics": {"altitude": [100, 110]},
                "user_note": "keep me",
            },
            external_id="api-external",
        ).to_record()
        incoming = _activity(
            "42",
            details={
                "ingest_source": "strava_bulk_export",
                "ingest_sources": ["strava_bulk_export"],
                "bulk_import": {"parse_status": "summary_only"},
            },
            distance_m=1200.0,
        )

        merged = reconcile_bulk_activity(incoming, existing)

        self.assertEqual(merged.distance_m, 1200.0)
        self.assertEqual(merged.external_id, "api-external")
        self.assertEqual(merged.geometry_points, [(10, 20), (11, 21)])
        self.assertEqual(merged.details_json["stream_metrics"]["altitude"], [100, 110])
        self.assertEqual(merged.details_json["user_note"], "keep me")
        self.assertEqual(
            merged.details_json["ingest_sources"],
            ["strava_api", "strava_bulk_export"],
        )

    def test_new_exact_archive_geometry_replaces_summary_polyline_geometry(self):
        existing = _activity(
            "42",
            points=[(10, 20)],
            geometry_source="summary_polyline",
            details={"user_tag": "holiday"},
        ).to_record()
        incoming = _activity(
            "42",
            points=[(1, 2), (3, 4)],
            details={"stream_metrics": {"altitude": [50, 60]}},
        )

        merged = reconcile_bulk_activity(incoming, existing)

        self.assertEqual(merged.geometry_source, "stream")
        self.assertEqual(merged.geometry_points, [(1, 2), (3, 4)])
        self.assertEqual(merged.details_json["user_tag"], "holiday")
        self.assertEqual(merged.details_json["stream_metrics"]["altitude"], [50, 60])

    def test_one_point_stream_does_not_replace_usable_summary_geometry(self):
        existing = _activity(
            "42",
            points=[(10, 20), (11, 21), (12, 22)],
            geometry_source="summary_polyline",
        ).to_record()
        incoming = _activity(
            "42",
            points=[(1, 2)],
            geometry_source="stream",
        )

        merged = reconcile_bulk_activity(incoming, existing)

        self.assertEqual(merged.geometry_source, "summary_polyline")
        self.assertEqual(merged.geometry_points, [(10, 20), (11, 21), (12, 22)])

    def test_one_point_stream_does_not_replace_encoded_summary_polyline(self):
        encoded = "_p~iF~ps|U_ulLnnqC_mqNvxq`@"
        existing = _activity(
            "42",
            points=[],
            geometry_source="summary_polyline",
            summary_polyline=encoded,
        ).to_record()
        incoming = _activity(
            "42",
            points=[(1, 2)],
            geometry_source="stream",
        )

        merged = reconcile_bulk_activity(incoming, existing)

        self.assertEqual(merged.geometry_source, "summary_polyline")
        self.assertEqual(merged.summary_polyline, encoded)
        self.assertEqual(merged.geometry_points, [])

    def test_does_not_replace_profile_with_lower_fidelity_stream(self):
        existing = _activity(
            "42",
            points=[(10, 20), (11, 21)],
            details={
                "geometry_ingest_source": "strava_api",
                "stream_metrics": {
                    "distance": [0, 100],
                    "altitude": [500, 510],
                    "heartrate": [120, 125],
                },
            },
        ).to_record()
        incoming = _activity(
            "42",
            points=[(1, 2), (3, 4)],
            details={"stream_metrics": {"distance": [0, 100]}},
        )

        merged = reconcile_bulk_activity(incoming, existing)

        self.assertEqual(merged.geometry_points, [(10, 20), (11, 21)])
        self.assertEqual(
            merged.details_json["stream_metrics"]["altitude"],
            [500, 510],
        )


if __name__ == "__main__":
    unittest.main()
