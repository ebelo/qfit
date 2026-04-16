import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests import _path  # noqa: F401
from tests.qgis_app import get_shared_qgis_app

try:
    from qgis.core import QgsApplication
except (ImportError, ModuleNotFoundError):  # pragma: no cover - exercised only on non-QGIS runners
    QgsApplication = None

if QgsApplication is not None:
    from qfit.activities.infrastructure.geopackage.gpkg_atlas_page_builder import build_atlas_layer
    from qfit.activities.infrastructure.geopackage.gpkg_atlas_table_builders import (
        build_cover_highlight_layer,
        build_document_summary_layer,
        build_page_detail_item_layer,
        build_profile_sample_layer,
        build_toc_layer,
    )
    from qfit.activities.infrastructure.geopackage.gpkg_writer import GeoPackageWriter
else:  # pragma: no cover - exercised only on non-QGIS runners
    build_atlas_layer = None
    build_cover_highlight_layer = None
    build_document_summary_layer = None
    build_page_detail_item_layer = None
    build_profile_sample_layer = None
    build_toc_layer = None
    GeoPackageWriter = None

def _ensure_qgis_app():
    return get_shared_qgis_app(QgsApplication)


@unittest.skipIf(QgsApplication is None, "QGIS Python bindings are not available")
class GeoPackageWriterAtlasTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _ensure_qgis_app()
        cls.writer = GeoPackageWriter(output_path="/tmp/qfit-test.gpkg")
        cls.records = [
            {
                "source": "strava",
                "source_activity_id": "100",
                "name": "Morning Ride",
                "activity_type": "Ride",
                "sport_type": "GravelRide",
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

    def test_build_atlas_layer_includes_document_summary_fields(self):
        layer = build_atlas_layer(self.records, self.writer.atlas_page_settings)

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
        self.assertEqual(first_feature["document_activity_types_label"], "GravelRide, Run")
        self.assertEqual(first_feature["sport_type"], "GravelRide")
        self.assertEqual(first_feature["total_elevation_gain_m"], 640.0)
        self.assertEqual(
            first_feature["document_cover_summary"],
            "2 activities · 2026-03-18 → 2026-03-19 · 52.6 km · 2h 50m · ↑ 725 m · GravelRide, Run",
        )

    def test_build_document_summary_layer(self):
        summary_layer = build_document_summary_layer(self.records)
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
        self.assertEqual(summary_feature["activity_types_label"], "GravelRide, Run")
        self.assertEqual(
            summary_feature["cover_summary"],
            "2 activities · 2026-03-18 → 2026-03-19 · 52.6 km · 2h 50m · ↑ 725 m · GravelRide, Run",
        )

    def test_build_cover_highlight_layer(self):
        cover_highlight_layer = build_cover_highlight_layer(self.records)
        self.assertTrue(cover_highlight_layer.isValid())
        self.assertEqual(cover_highlight_layer.featureCount(), 6)
        self.assertGreaterEqual(cover_highlight_layer.fields().indexOf("highlight_value"), 0)
        cover_highlight_features = list(cover_highlight_layer.getFeatures())
        self.assertEqual(cover_highlight_features[0]["highlight_key"], "activity_count")
        self.assertEqual(cover_highlight_features[0]["highlight_label"], "Activities")
        self.assertEqual(cover_highlight_features[0]["highlight_value"], "2 activities")
        self.assertEqual(cover_highlight_features[-1]["highlight_key"], "activity_types")
        self.assertEqual(cover_highlight_features[-1]["highlight_value"], "GravelRide, Run")

    def test_build_page_detail_item_layer(self):
        page_detail_item_layer = build_page_detail_item_layer(self.records)
        self.assertTrue(page_detail_item_layer.isValid())
        self.assertEqual(page_detail_item_layer.featureCount(), 9)
        self.assertGreaterEqual(page_detail_item_layer.fields().indexOf("detail_value"), 0)
        page_detail_features = list(page_detail_item_layer.getFeatures())
        self.assertEqual(page_detail_features[0]["detail_key"], "distance")
        self.assertEqual(page_detail_features[0]["detail_label"], "Distance")
        self.assertEqual(page_detail_features[0]["detail_value"], "42.5 km")
        self.assertEqual(page_detail_features[-1]["detail_key"], "stats_summary")

    def test_build_profile_sample_layer_empty(self):
        profile_sample_layer = build_profile_sample_layer(self.records)
        self.assertTrue(profile_sample_layer.isValid())
        self.assertEqual(profile_sample_layer.featureCount(), 0)

    def test_build_profile_sample_layer_with_stream(self):
        profile_records = [
            {
                "source": "strava",
                "source_activity_id": "300",
                "name": "Lunch Run",
                "activity_type": "Run",
                "start_date_local": "2026-03-19T12:00:00+01:00",
                "distance_m": 10100,
                "moving_time_s": 3000,
                "total_elevation_gain_m": 85,
                "geometry_points": [(46.50, 6.60), (46.51, 6.62)],
                "details_json": {
                    "stream_metrics": {
                        "distance": [0, 3300, 6700, 10100],
                        "altitude": [430, 445, 438, 452],
                    }
                },
            }
        ]
        profile_sample_layer = build_profile_sample_layer(profile_records)
        self.assertTrue(profile_sample_layer.isValid())
        self.assertEqual(profile_sample_layer.featureCount(), 4)
        self.assertGreaterEqual(profile_sample_layer.fields().indexOf("profile_point_ratio"), 0)
        profile_features = list(profile_sample_layer.getFeatures())
        self.assertEqual(profile_features[0]["distance_label"], "0.0 km")
        self.assertEqual(profile_features[-1]["distance_m"], 10100.0)
        self.assertEqual(profile_features[-1]["altitude_m"], 452.0)
        self.assertEqual(profile_features[-1]["profile_point_ratio"], 1.0)
        self.assertEqual(profile_features[-1]["profile_distance_m"], 10100.0)

    def test_build_toc_layer(self):
        toc_layer = build_toc_layer(self.records)
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
