import importlib.util
import os
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests import _path  # noqa: F401
from tests.qgis_app import get_shared_qgis_app

try:
    _REAL_QGIS_PRESENT = importlib.util.find_spec("qgis") is not None
except ValueError:
    _REAL_QGIS_PRESENT = any(os.path.isdir(os.path.join(p, "qgis")) for p in sys.path if p)

try:
    from qgis.core import QgsApplication, QgsWkbTypes
except (ImportError, ModuleNotFoundError):  # pragma: no cover
    QgsApplication = None
    QgsWkbTypes = None

if QgsApplication is not None and _REAL_QGIS_PRESENT:
    from qfit.routes.infrastructure.geopackage.route_layer_builders import (
        build_route_point_layer,
        build_route_track_layer,
    )
else:  # pragma: no cover
    build_route_point_layer = None
    build_route_track_layer = None


def _ensure_qgis_app():
    if not _REAL_QGIS_PRESENT:
        raise unittest.SkipTest("QGIS Python bindings are not available")
    return get_shared_qgis_app(QgsApplication)


@unittest.skipIf(QgsApplication is None, "QGIS Python bindings are not available")
class RouteLayerBuilderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _ensure_qgis_app()

    def test_route_track_layer_uses_linestring_z_when_altitude_exists(self):
        layer = build_route_track_layer([
            {
                "source": "strava",
                "source_route_id": "733",
                "name": "Saved route",
                "route_type": "Ride",
                "geometry_source": "gpx",
                "geometry_points": [
                    {"latitude": 46.1, "longitude": 7.1, "altitude_m": 500.0, "distance_m": 0.0, "point_index": 0},
                    {"latitude": 46.2, "longitude": 7.2, "altitude_m": 550.0, "distance_m": 1000.0, "point_index": 1},
                ],
            }
        ])

        self.assertTrue(layer.isValid())
        self.assertEqual(layer.featureCount(), 1)
        self.assertTrue(QgsWkbTypes.hasZ(layer.wkbType()))
        feature = next(layer.getFeatures())
        self.assertEqual(feature["source_route_id"], "733")
        self.assertEqual(feature["geometry_point_count"], 2)

    def test_route_point_layer_keeps_ordered_profile_samples(self):
        layer = build_route_point_layer([
            {
                "source": "strava",
                "source_route_id": "733",
                "name": "Saved route",
                "geometry_source": "gpx",
                "geometry_points": [
                    {"latitude": 46.1, "longitude": 7.1, "altitude_m": 500.0, "distance_m": 0.0, "point_index": 0},
                    {"latitude": 46.2, "longitude": 7.2, "altitude_m": 550.0, "distance_m": 1000.0, "point_index": 1},
                ],
            }
        ])

        self.assertEqual(layer.featureCount(), 2)
        samples = sorted(layer.getFeatures(), key=lambda feature: feature["point_index"])
        self.assertEqual(samples[0]["route_fk"], "strava:733")
        self.assertEqual([sample["point_index"] for sample in samples], [0, 1])
        self.assertEqual(samples[1]["point_ratio"], 1.0)
        self.assertTrue(QgsWkbTypes.hasZ(layer.wkbType()))


if __name__ == "__main__":
    unittest.main()
