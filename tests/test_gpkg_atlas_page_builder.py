import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests import _path  # noqa: F401

try:
    from qgis.core import QgsApplication
except (ImportError, ModuleNotFoundError):  # pragma: no cover
    QgsApplication = None

if QgsApplication is not None:
    from qfit.atlas.export_task import _build_cover_summary_from_current_atlas_features
    from qfit.atlas.publish_atlas import normalize_atlas_page_settings
    from qfit.gpkg_atlas_page_builder import build_atlas_layer
else:  # pragma: no cover
    _build_cover_summary_from_current_atlas_features = None
    normalize_atlas_page_settings = None
    build_atlas_layer = None


_QGIS_APP = None


def _ensure_qgis_app():
    global _QGIS_APP
    if _QGIS_APP is None:
        _QGIS_APP = QgsApplication([], False)
        _QGIS_APP.initQgis()
    return _QGIS_APP


@unittest.skipIf(QgsApplication is None, "QGIS Python bindings are not available")
class BuildAtlasLayerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _ensure_qgis_app()
        cls.settings = normalize_atlas_page_settings()
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
        layer = build_atlas_layer(self.records, self.settings)

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

    def test_build_atlas_layer_accepts_precomputed_plans(self):
        layer = build_atlas_layer(self.records, self.settings, plans=[])
        self.assertTrue(layer.isValid())
        self.assertEqual(layer.featureCount(), 0)

    def test_built_atlas_layer_feeds_subset_cover_summary_metrics(self):
        layer = build_atlas_layer(self.records, self.settings)

        summary = _build_cover_summary_from_current_atlas_features(layer)

        self.assertEqual(summary["document_activity_types_label"], "GravelRide, Run")
        self.assertEqual(summary["document_total_elevation_gain_label"], "725 m")
        self.assertIn("725 m", summary["document_cover_summary"])


if __name__ == "__main__":
    unittest.main()
