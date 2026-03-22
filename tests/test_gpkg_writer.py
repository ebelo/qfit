import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests import _path  # noqa: F401

try:
    from qgis.core import QgsApplication
except ModuleNotFoundError:  # pragma: no cover - exercised only on non-QGIS runners
    QgsApplication = None

from qfit.gpkg_writer import GeoPackageWriter


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
        layer = writer._build_atlas_layer(
            [
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
        )

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


if __name__ == "__main__":
    unittest.main()
