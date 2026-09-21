from __future__ import annotations

import csv
import io
import os
import tempfile
import unittest
import zipfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests import _path  # noqa: F401
from tests.qgis_app import get_shared_qgis_app

try:
    from qgis.core import QgsApplication, QgsVectorLayer
except (ImportError, ModuleNotFoundError):  # pragma: no cover - no-QGIS test jobs
    QgsApplication = None
    QgsVectorLayer = None

if QgsApplication is not None:
    from qfit.activities.application.strava_bulk_import import (
        StravaBulkImportRequest,
        StravaBulkImportWorkflow,
    )
    from qfit.activities.application.strava_bulk_import_task import (
        StravaBulkImportTask,
    )
    from qfit.sync_repository import SyncRepository
    from qfit.providers.infrastructure.fit_runtime import load_fitdecode


def _archive(path):
    fields = [
        "Activity ID",
        "Activity Date",
        "Activity Name",
        "Activity Type",
        "Filename",
        "Distance",
        "Moving Time",
        "Elapsed Time",
        "Elevation Gain",
    ]
    csv_buffer = io.StringIO(newline="")
    writer = csv.DictWriter(csv_buffer, fieldnames=fields)
    writer.writeheader()
    writer.writerow(
        {
            "Activity ID": "123",
            "Activity Date": "Sep 21, 2026, 7:30:00 AM",
            "Activity Name": "Synthetic activity",
            "Activity Type": "Run",
            "Filename": "activities/device-file.gpx",
            "Distance": "250",
            "Moving Time": "60",
            "Elapsed Time": "65",
            "Elevation Gain": "10",
        }
    )
    gpx = b"""<?xml version="1.0" encoding="UTF-8"?>
<gpx xmlns="http://www.topografix.com/GPX/1/1"><trk><trkseg>
<trkpt lat="46.0" lon="7.0"><ele>500</ele><time>2026-09-21T05:30:00Z</time></trkpt>
<trkpt lat="46.001" lon="7.002"><ele>510</ele><time>2026-09-21T05:31:00Z</time></trkpt>
</trkseg></trk></gpx>"""
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("activities.csv", csv_buffer.getvalue())
        archive.writestr("activities/device-file.gpx", gpx)


@unittest.skipIf(QgsApplication is None, "QGIS Python bindings are not available")
class StravaBulkQgisIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        get_shared_qgis_app(QgsApplication)

    def test_import_reopen_profile_and_idempotent_reimport(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            archive_path = str(Path(temp_dir) / "export.zip")
            gpkg_path = str(Path(temp_dir) / "activities.gpkg")
            _archive(archive_path)
            workflow = StravaBulkImportWorkflow()
            request = StravaBulkImportRequest(
                archive_path=archive_path,
                output_path=gpkg_path,
                point_stride=1,
            )

            first = workflow.run(request)
            second = workflow.run(request)

            self.assertEqual(first.inserted, 1)
            self.assertEqual(second.unchanged, 1)
            stored = SyncRepository(gpkg_path).load_all_activities()
            self.assertEqual(len(stored), 1)
            self.assertEqual(len(stored[0].geometry_points), 2)
            self.assertEqual(
                stored[0].details_json["stream_metrics"]["altitude"],
                [500.0, 510.0],
            )
            provenance = stored[0].details_json["bulk_import"]
            self.assertEqual(provenance["schema_version"], 1)
            self.assertEqual(provenance["source_format"], "gpx")
            self.assertEqual(provenance["parse_status"], "detailed_profile")
            self.assertEqual(provenance["member_identity"], "activities/device-file.gpx")
            self.assertEqual(len(provenance["member_sha256"]), 64)
            self.assertEqual(
                stored[0].details_json["geometry_ingest_source"],
                "strava_bulk_export",
            )
            profile = QgsVectorLayer(
                gpkg_path + "|layername=atlas_profile_samples",
                "profile",
                "ogr",
            )
            self.assertTrue(profile.isValid())
            self.assertEqual(profile.featureCount(), 2)

    def test_fit_runtime_is_available_in_supported_qgis_python(self):
        fitdecode = load_fitdecode()

        self.assertTrue(hasattr(fitdecode, "FitReader"))
        self.assertTrue(hasattr(fitdecode, "FitDataMessage"))

    def test_task_exposes_phase_progress_and_completion(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            archive_path = str(Path(temp_dir) / "export.zip")
            gpkg_path = str(Path(temp_dir) / "activities.gpkg")
            _archive(archive_path)
            completed = []
            task = StravaBulkImportTask(
                StravaBulkImportWorkflow(),
                StravaBulkImportRequest(archive_path, gpkg_path),
                on_finished=lambda result, error, cancelled: completed.append(
                    (result, error, cancelled)
                ),
            )

            ok = task.run()
            task.finished(ok)

            self.assertTrue(ok)
            self.assertEqual(task.latest_progress.phase, "complete")
            self.assertEqual(task.latest_progress.percent, 100.0)
            self.assertEqual(len(completed), 1)
            self.assertIsNone(completed[0][1])
            self.assertFalse(completed[0][2])


if __name__ == "__main__":
    unittest.main()
