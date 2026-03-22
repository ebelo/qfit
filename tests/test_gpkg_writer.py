import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests import _path  # noqa: F401

try:
    from qgis.core import QgsApplication
except ModuleNotFoundError:  # pragma: no cover - exercised only on non-QGIS runners
    QgsApplication = None

if QgsApplication is not None:
    from qfit.gpkg_writer import GeoPackageWriter
else:  # pragma: no cover - exercised only on non-QGIS runners
    GeoPackageWriter = None


_QGIS_APP = None


def _ensure_qgis_app():
    global _QGIS_APP
    if _QGIS_APP is None:
        _QGIS_APP = QgsApplication([], False)
        _QGIS_APP.initQgis()
    return _QGIS_APP


@unittest.skipIf(QgsApplication is None, "QGIS Python bindings are not available")
class GeoPackageWriterAtlasTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _ensure_qgis_app()

    def test_build_atlas_layer_includes_document_summary_fields(self):
        writer = GeoPackageWriter(output_path="/tmp/qfit-test.gpkg")
        records = [
            {
                "source": "strava",
                "source_activity_id": "100",
                "name": "Morning Ride",
                "activity_type": "Ride",
                "start_date_local": "2026-03-18T08:10:00+01:00",
                "distance_m": 42500,
                "moving_time_s": 7200,
                "total_elevation_gain_m": 640,
                "geometry_points": [(46.52, 6.62), (46.57, 6.74)],
            },
            {
                "source": "strava",
                "source_activity_id": "200",
                "name": "Lunch Run",
                "activity_type": "Run",
                "start_date_local": "2026-03-19T12:00:00+01:00",
                "distance_m": 10100,
                "moving_time_s": 3000,
                "total_elevation_gain_m": 85,
                "geometry_points": [(46.50, 6.60), (46.51, 6.62)],
            },
        ]
        layer = writer._build_atlas_layer(records)

        self.assertTrue(layer.isValid())
        self.assertEqual(layer.featureCount(), 2)
        self.assertGreaterEqual(layer.fields().indexOf("document_cover_summary"), 0)

        features = list(layer.getFeatures())
        first_feature = features[0]
        self.assertEqual(first_feature["document_activity_count"], 2)
        self.assertEqual(first_feature["document_date_range_label"], "2026-03-18 → 2026-03-19")
        self.assertEqual(first_feature["document_total_distance_label"], "52.6 km")
        self.assertEqual(first_feature["document_total_duration_label"], "2h 50m")
        self.assertEqual(first_feature["document_total_elevation_gain_label"], "725 m")
        self.assertEqual(first_feature["document_activity_types_label"], "Ride, Run")
        self.assertEqual(
            first_feature["document_cover_summary"],
            "2 activities · 2026-03-18 → 2026-03-19 · 52.6 km · 2h 50m · ↑ 725 m · Ride, Run",
        )

        summary_layer = writer._build_document_summary_layer(records)
        self.assertTrue(summary_layer.isValid())
        self.assertEqual(summary_layer.featureCount(), 1)
        self.assertGreaterEqual(summary_layer.fields().indexOf("cover_summary"), 0)

        summary_feature = next(summary_layer.getFeatures())
        self.assertEqual(summary_feature["activity_count"], 2)
        self.assertEqual(summary_feature["activity_date_start"], "2026-03-18")
        self.assertEqual(summary_feature["activity_date_end"], "2026-03-19")
        self.assertEqual(summary_feature["date_range_label"], "2026-03-18 → 2026-03-19")
        self.assertEqual(summary_feature["total_distance_m"], 52600.0)
        self.assertEqual(summary_feature["total_distance_label"], "52.6 km")
        self.assertEqual(summary_feature["total_moving_time_s"], 10200)
        self.assertEqual(summary_feature["total_duration_label"], "2h 50m")
        self.assertEqual(summary_feature["total_elevation_gain_m"], 725.0)
        self.assertEqual(summary_feature["total_elevation_gain_label"], "725 m")
        self.assertEqual(summary_feature["activity_types_label"], "Ride, Run")
        self.assertEqual(
            summary_feature["cover_summary"],
            "2 activities · 2026-03-18 → 2026-03-19 · 52.6 km · 2h 50m · ↑ 725 m · Ride, Run",
        )

        toc_layer = writer._build_toc_layer(records)
        self.assertTrue(toc_layer.isValid())
        self.assertEqual(toc_layer.featureCount(), 2)
        self.assertGreaterEqual(toc_layer.fields().indexOf("toc_entry_label"), 0)

        toc_features = list(toc_layer.getFeatures())
        self.assertEqual(toc_features[0]["page_number"], 1)
        self.assertEqual(toc_features[0]["page_number_label"], "1")
        self.assertEqual(toc_features[0]["page_toc_label"], "2026-03-18 · Morning Ride · 42.5 km · 2h 00m")
        self.assertEqual(toc_features[0]["toc_entry_label"], "1. 2026-03-18 · Morning Ride · 42.5 km · 2h 00m")
        self.assertEqual(toc_features[1]["page_number"], 2)
        self.assertEqual(toc_features[1]["page_duration_label"], "50m 00s")
        self.assertEqual(toc_features[1]["page_stats_summary"], "10.1 km · 50m 00s · 4m 57s/km · ↑ 85 m")


if __name__ == "__main__":
    unittest.main()
