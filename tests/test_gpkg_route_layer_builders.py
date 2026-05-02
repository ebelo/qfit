import importlib.util
import os
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests import _path  # noqa: E402,F401
from tests.qgis_app import get_shared_qgis_app  # noqa: E402
from qfit.providers.domain.routes import RouteProfilePoint  # noqa: E402

try:
    _REAL_QGIS_PRESENT = importlib.util.find_spec("qgis") is not None
except ValueError:
    _REAL_QGIS_PRESENT = any(
        os.path.isdir(os.path.join(p, "qgis")) for p in sys.path if p
    )

try:
    from qgis.core import QgsApplication, QgsWkbTypes
except (ImportError, ModuleNotFoundError):  # pragma: no cover
    QgsApplication = None
    QgsWkbTypes = None

if QgsApplication is not None and _REAL_QGIS_PRESENT:
    from qfit.activities.infrastructure.geopackage import (  # noqa: E501
        gpkg_route_layer_builders as route_builders,
    )

    _route_geometry = route_builders._route_geometry
    build_route_point_layer = route_builders.build_route_point_layer
    build_route_profile_sample_layer = (
        route_builders.build_route_profile_sample_layer
    )
    build_route_track_layer = route_builders.build_route_track_layer
    route_feature_key = route_builders.route_feature_key
else:  # pragma: no cover
    _route_geometry = None
    build_route_point_layer = None
    build_route_profile_sample_layer = None
    build_route_track_layer = None
    route_feature_key = None


def _ensure_qgis_app():
    if not _REAL_QGIS_PRESENT:
        raise unittest.SkipTest("QGIS Python bindings are not available")

    global QgsApplication
    global QgsWkbTypes
    global _route_geometry
    global build_route_point_layer
    global build_route_profile_sample_layer
    global build_route_track_layer
    global route_feature_key
    if QgsApplication is None and _REAL_QGIS_PRESENT:
        for module_name in [
            "qgis.core",
            "qgis.gui",
            "qgis.PyQt",
            "qgis.PyQt.QtCore",
            "qgis.PyQt.QtGui",
            "qgis",
        ]:
            sys.modules.pop(module_name, None)
        from qgis.core import (  # type: ignore
            QgsApplication as RealQgsApplication,
            QgsWkbTypes as RealQgsWkbTypes,
        )

        QgsApplication = RealQgsApplication
        QgsWkbTypes = RealQgsWkbTypes
    if build_route_track_layer is None:
        sys.modules.pop(
            "qfit.activities.infrastructure.geopackage."
            "gpkg_route_layer_builders",
            None,
        )
        from qfit.activities.infrastructure.geopackage import (
            gpkg_route_layer_builders as real_route_builders,
        )

        _route_geometry = real_route_builders._route_geometry
        build_route_point_layer = real_route_builders.build_route_point_layer
        build_route_profile_sample_layer = (
            real_route_builders.build_route_profile_sample_layer
        )
        build_route_track_layer = real_route_builders.build_route_track_layer
        route_feature_key = real_route_builders.route_feature_key
    return get_shared_qgis_app(QgsApplication)


@unittest.skipIf(
    QgsApplication is None,
    "QGIS Python bindings are not available",
)
class RouteLayerSchemaTests(unittest.TestCase):
    def test_route_layers_are_declared_in_schema(self):
        from qfit.activities.infrastructure.geopackage.gpkg_schema import (
            GPKG_LAYER_SCHEMA,
        )

        self.assertEqual(
            GPKG_LAYER_SCHEMA["route_tracks"]["geometry"],
            "LINESTRING",
        )
        self.assertIn(
            "LINESTRINGZ",
            GPKG_LAYER_SCHEMA["route_tracks"]["geometry_variants"],
        )
        self.assertIn("route_fk", GPKG_LAYER_SCHEMA["route_tracks"]["fields"])
        self.assertEqual(
            GPKG_LAYER_SCHEMA["route_points"]["geometry"],
            "POINT",
        )
        self.assertIn(
            "segment_index",
            GPKG_LAYER_SCHEMA["route_points"]["fields"],
        )
        self.assertIsNone(GPKG_LAYER_SCHEMA["route_profile_samples"]["geometry"])


@unittest.skipIf(
    QgsApplication is None,
    "QGIS Python bindings are not available",
)
class RouteGeometryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _ensure_qgis_app()

    def test_route_geometry_prefers_profile_points(self):
        record = {
            "profile_points": [
                RouteProfilePoint(0, 46.5, 6.6, 0.0, altitude_m=400.0),
                {"lat": None, "lon": 6.65},
                RouteProfilePoint(1, 46.6, 6.7, 100.0, altitude_m=410.0),
            ],
            "geometry_points": [(47.0, 7.0), (47.1, 7.1)],
        }

        geometry, source, count, profile_count, has_elevation = _route_geometry(
            record
        )

        self.assertIsNotNone(geometry)
        self.assertEqual(source, "profile")
        self.assertEqual(count, 2)
        self.assertEqual(profile_count, 3)
        self.assertTrue(has_elevation)

    def test_route_geometry_falls_back_to_start_end(self):
        record = {
            "start_lat": 46.5,
            "start_lon": 6.6,
            "end_lat": 46.6,
            "end_lon": 6.7,
        }

        geometry, source, count, profile_count, has_elevation = _route_geometry(
            record
        )

        self.assertIsNotNone(geometry)
        self.assertEqual(source, "start_end")
        self.assertEqual(count, 2)
        self.assertEqual(profile_count, 0)
        self.assertFalse(has_elevation)

    def test_route_geometry_without_points_is_empty(self):
        geometry, source, count, profile_count, has_elevation = _route_geometry({})

        self.assertIsNone(geometry)
        self.assertIsNone(source)
        self.assertEqual(count, 0)
        self.assertEqual(profile_count, 0)
        self.assertFalse(has_elevation)


@unittest.skipIf(
    QgsApplication is None,
    "QGIS Python bindings are not available",
)
class BuildRouteTrackLayerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _ensure_qgis_app()

    def test_record_with_profile_points_builds_route_track_feature(self):
        records = [
            {
                "source": "strava",
                "source_route_id": "42",
                "name": "Lake Loop",
                "private": False,
                "starred": True,
                "distance_m": 12000.0,
                "profile_points": [
                    RouteProfilePoint(0, 46.5, 6.6, 0.0),
                    RouteProfilePoint(1, 46.6, 6.7, 100.0),
                ],
                "details_json": {"estimated": False},
            }
        ]

        layer = build_route_track_layer(records)

        self.assertEqual(layer.featureCount(), 1)
        self.assertFalse(QgsWkbTypes.hasZ(layer.wkbType()))
        feature = next(layer.getFeatures())
        self.assertEqual(feature["route_fk"], '["strava","42"]')
        self.assertEqual(feature["name"], "Lake Loop")
        self.assertEqual(feature["starred"], 1)
        self.assertEqual(feature["private"], 0)
        self.assertEqual(feature["geometry_source"], "profile")
        self.assertEqual(feature["geometry_point_count"], 2)
        self.assertEqual(feature["profile_point_count"], 2)
        self.assertEqual(feature["details_json"], '{"estimated": false}')

    def test_route_track_layer_creates_linestring_z_when_elevation_exists(self):
        layer = build_route_track_layer(
            [
                {
                    "source": "strava",
                    "source_route_id": "42",
                    "name": "Swiss gravel loop",
                    "geometry_source": "export_gpx",
                    "profile_points": [
                        {
                            "point_index": 0,
                            "lat": 46.5,
                            "lon": 6.6,
                            "distance_m": 0.0,
                            "altitude_m": 500.0,
                        },
                        {
                            "point_index": 1,
                            "lat": 46.501,
                            "lon": 6.601,
                            "distance_m": 135.4,
                            "altitude_m": 507.5,
                        },
                    ],
                }
            ]
        )

        self.assertTrue(layer.isValid())
        self.assertTrue(QgsWkbTypes.hasZ(layer.wkbType()))
        self.assertEqual(layer.featureCount(), 1)
        feature = next(layer.getFeatures())
        self.assertEqual(feature["source_route_id"], "42")
        self.assertEqual(feature["geometry_point_count"], 2)
        self.assertEqual(feature["profile_point_count"], 2)
        self.assertEqual(feature["has_elevation"], 1)
        self.assertTrue(QgsWkbTypes.hasZ(feature.geometry().wkbType()))
        first_vertex = next(feature.geometry().vertices())
        self.assertAlmostEqual(first_vertex.z(), 500.0)

    def test_record_without_geometry_is_skipped(self):
        layer = build_route_track_layer([
            {"source": "strava", "source_route_id": "42"}
        ])

        self.assertEqual(layer.featureCount(), 0)

    def test_record_without_stable_route_id_is_skipped(self):
        layer = build_route_track_layer([
            {
                "source": "strava",
                "profile_points": [
                    RouteProfilePoint(0, 46.5, 6.6, 0.0),
                    RouteProfilePoint(1, 46.6, 6.7, 100.0),
                ],
            }
        ])

        self.assertEqual(layer.featureCount(), 0)


@unittest.skipIf(
    QgsApplication is None,
    "QGIS Python bindings are not available",
)
class BuildRoutePointLayerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _ensure_qgis_app()

    def test_profile_points_build_stable_route_point_features(self):
        records = [
            {
                "source": "strava",
                "source_route_id": "42",
                "name": "Lake Loop",
                "geometry_source": "export_gpx",
                "profile_points": [
                    RouteProfilePoint(
                        point_index=0,
                        lat=46.5,
                        lon=6.6,
                        distance_m=0.0,
                        segment_index=0,
                        altitude_m=400.0,
                    ),
                    {
                        "point_index": 1,
                        "lat": 46.6,
                        "lon": 6.7,
                        "distance_m": 100.0,
                        "segment_index": 1,
                        "altitude_m": 410.0,
                    },
                ],
            }
        ]

        layer = build_route_point_layer(records)

        self.assertEqual(layer.featureCount(), 2)
        features = list(layer.getFeatures())
        self.assertEqual(
            [feature["route_fk"] for feature in features],
            ['["strava","42"]'] * 2,
        )
        self.assertEqual(
            [feature["segment_index"] for feature in features],
            [0, 1],
        )
        self.assertEqual(features[1]["distance_m"], 100.0)
        self.assertEqual(features[1]["geometry_source"], "export_gpx")

    def test_profile_points_are_skipped_when_track_geometry_is_missing(self):
        records = [
            {
                "source": "strava",
                "source_route_id": "42",
                "profile_points": [RouteProfilePoint(0, 46.5, 6.6, 0.0)],
            }
        ]

        layer = build_route_point_layer(records)

        self.assertEqual(layer.featureCount(), 0)

    def test_profile_points_are_skipped_when_route_id_is_missing(self):
        records = [
            {
                "source": "strava",
                "profile_points": [
                    RouteProfilePoint(0, 46.5, 6.6, 0.0),
                    RouteProfilePoint(1, 46.6, 6.7, 100.0),
                ],
            }
        ]

        layer = build_route_point_layer(records)

        self.assertEqual(layer.featureCount(), 0)


@unittest.skipIf(
    QgsApplication is None,
    "QGIS Python bindings are not available",
)
class BuildRouteProfileSampleLayerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _ensure_qgis_app()

    def test_route_profile_samples_include_join_key_distance_and_altitude(self):
        layer = build_route_profile_sample_layer([
            {
                "source": "strava",
                "source_route_id": "42",
                "name": "Swiss gravel loop",
                "profile_points": [
                    {
                        "point_index": 0,
                        "segment_index": 0,
                        "lat": 46.5,
                        "lon": 6.6,
                        "distance_m": 0.0,
                        "altitude_m": 500.0,
                    },
                    {
                        "point_index": 1,
                        "segment_index": 0,
                        "lat": 46.501,
                        "lon": 6.601,
                        "distance_m": 135.4,
                        "altitude_m": 507.5,
                    },
                ],
            }
        ])

        self.assertTrue(layer.isValid())
        self.assertEqual(layer.featureCount(), 2)
        samples = list(layer.getFeatures())
        self.assertEqual(samples[1]["sample_group_index"], 1)
        self.assertEqual(samples[1]["source"], "strava")
        self.assertEqual(samples[1]["source_route_id"], "42")
        self.assertEqual(samples[1]["point_index"], 1)
        self.assertEqual(samples[1]["distance_m"], 135.4)
        self.assertEqual(samples[1]["altitude_m"], 507.5)


@unittest.skipIf(
    QgsApplication is None,
    "QGIS Python bindings are not available",
)
class RouteFeatureKeyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _ensure_qgis_app()

    def test_route_feature_key_uses_stable_source_identity(self):
        self.assertEqual(
            route_feature_key({"source": "strava", "source_route_id": "42"}),
            '["strava","42"]',
        )

    def test_route_feature_key_preserves_component_boundaries(self):
        self.assertNotEqual(
            route_feature_key({"source": "a:b", "source_route_id": "c"}),
            route_feature_key({"source": "a", "source_route_id": "b:c"}),
        )

    def test_route_feature_key_rejects_missing_route_id(self):
        self.assertIsNone(route_feature_key({"source": "strava"}))


if __name__ == "__main__":
    unittest.main()
