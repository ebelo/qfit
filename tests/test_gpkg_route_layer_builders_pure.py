import importlib
import math
import sys
import unittest
from types import ModuleType
from unittest.mock import patch

from tests import _path  # noqa: F401


_BUILDER_MODULE = "qfit.activities.infrastructure.geopackage.gpkg_route_layer_builders"


class _FakePoint:
    def __init__(self, lon, lat, z=None, **kwargs):
        self.lon = lon
        self.lat = lat
        self.z = math.nan if z is None and kwargs.get("wkbType") else z


class _FakeWkbTypes:
    PointZ = 1001


class _FakePointXY:
    def __init__(self, lon, lat):
        self.lon = lon
        self.lat = lat


class _FakeGeometry:
    def __init__(self, kind, points):
        self.kind = kind
        self.points = points

    @classmethod
    def fromPolyline(cls, points):
        return cls("z", points)

    @classmethod
    def fromPolylineXY(cls, points):
        return cls("xy", points)


class _FakeFeature:
    def __init__(self, fields):
        self.fields = list(fields)
        self.attributes = {}
        self._geometry = None

    def setGeometry(self, geometry):
        self._geometry = geometry

    def geometry(self):
        return self._geometry

    def __setitem__(self, key, value):
        self.attributes[key] = value

    def __getitem__(self, key):
        return self.attributes.get(key)


class _FakeProvider:
    def __init__(self, layer):
        self.layer = layer

    def addAttributes(self, fields):
        self.layer._fields = list(fields)

    def addFeatures(self, features):
        self.layer._features.extend(features)
        return True, list(features)


class _FakeVectorLayer:
    def __init__(self, uri, name, provider_key):
        self.uri = uri
        self.name = name
        self.provider_key = provider_key
        self._fields = []
        self._features = []
        self._provider = _FakeProvider(self)

    def dataProvider(self):
        return self._provider

    def updateFields(self):
        return None

    def fields(self):
        return list(self._fields)

    def updateExtents(self):
        return None

    def featureCount(self):
        return len(self._features)

    def getFeatures(self):
        return iter(self._features)

    def isValid(self):
        return True


def _make_qgis_stubs():
    qgis_mod = ModuleType("qgis")
    qgis_core = ModuleType("qgis.core")
    qgis_core.QgsFeature = _FakeFeature
    qgis_core.QgsGeometry = _FakeGeometry
    qgis_core.QgsPoint = _FakePoint
    qgis_core.QgsPointXY = _FakePointXY
    qgis_core.QgsVectorLayer = _FakeVectorLayer
    qgis_core.QgsWkbTypes = _FakeWkbTypes
    qgis_mod.core = qgis_core
    return qgis_mod, qgis_core


def _make_schema_stub():
    schema = ModuleType("qfit.activities.infrastructure.geopackage.gpkg_schema")
    schema.ROUTE_TRACK_FIELDS = [
        ("route_fk", "String"),
        ("source", "String"),
        ("source_route_id", "String"),
        ("name", "String"),
        ("geometry_point_count", "Int"),
        ("profile_point_count", "Int"),
        ("has_elevation", "Int"),
    ]
    schema.ROUTE_POINT_FIELDS = [
        ("route_fk", "String"),
        ("source", "String"),
        ("source_route_id", "String"),
        ("point_index", "Int"),
        ("altitude_m", "Double"),
    ]
    schema.ROUTE_PROFILE_SAMPLE_FIELDS = [
        ("sample_group_index", "Int"),
        ("source", "String"),
        ("source_route_id", "String"),
        ("point_index", "Int"),
        ("altitude_m", "Double"),
    ]
    schema.make_qgs_fields = lambda field_defs: [name for name, _ in field_defs]
    return schema


def _load_builder_with_stubs(test_case):
    qgis_mod, qgis_core = _make_qgis_stubs()
    schema = _make_schema_stub()
    previous_builder = sys.modules.pop(_BUILDER_MODULE, None)

    def restore_builder():
        sys.modules.pop(_BUILDER_MODULE, None)
        if previous_builder is not None:
            sys.modules[_BUILDER_MODULE] = previous_builder

    test_case.addCleanup(restore_builder)
    with patch.dict(
        sys.modules,
        {
            "qgis": qgis_mod,
            "qgis.core": qgis_core,
            "qfit.activities.infrastructure.geopackage.gpkg_schema": schema,
        },
    ):
        return importlib.import_module(_BUILDER_MODULE)


class RouteLayerBuilderPureTests(unittest.TestCase):
    def test_route_track_layer_uses_z_only_for_complete_altitude_samples(self):
        builders = _load_builder_with_stubs(self)

        layer = builders.build_route_track_layer(
            [
                {
                    "source": "strava",
                    "source_route_id": "complete",
                    "profile_points": [
                        {"point_index": 0, "lat": 46.5, "lon": 6.6, "distance_m": 0.0, "altitude_m": 500.0},
                        {"point_index": 1, "lat": 46.6, "lon": 6.7, "distance_m": 100.0, "altitude_m": 510.0},
                    ],
                },
                {
                    "source": "strava",
                    "source_route_id": "partial",
                    "profile_points": [
                        {"point_index": 0, "lat": 46.5, "lon": 6.6, "distance_m": 0.0, "altitude_m": 500.0},
                        {"point_index": 1, "lat": 46.6, "lon": 6.7, "distance_m": 100.0, "altitude_m": None},
                    ],
                },
            ]
        )

        features = {feature["source_route_id"]: feature for feature in layer.getFeatures()}
        self.assertEqual(layer.uri, "LineStringZ?crs=EPSG:4326")
        self.assertEqual(features["complete"].geometry().kind, "z")
        self.assertEqual(features["complete"].geometry().points[0].z, 500.0)
        self.assertEqual(features["complete"]["has_elevation"], 1)
        self.assertEqual(features["partial"].geometry().kind, "z")
        self.assertTrue(math.isnan(features["partial"].geometry().points[0].z))
        self.assertEqual(features["partial"]["has_elevation"], 0)

    def test_geometry_point_fallback_is_padded_when_catalog_has_elevation(self):
        builders = _load_builder_with_stubs(self)

        layer = builders.build_route_track_layer(
            [
                {
                    "source": "strava",
                    "source_route_id": "z-route",
                    "profile_points": [
                        {"point_index": 0, "lat": 46.5, "lon": 6.6, "distance_m": 0.0, "altitude_m": 500.0},
                        {"point_index": 1, "lat": 46.6, "lon": 6.7, "distance_m": 100.0, "altitude_m": 510.0},
                    ],
                },
                {
                    "source": "strava",
                    "source_route_id": "polyline-only",
                    "geometry_points": [(46.7, 6.8), (46.8, 6.9)],
                },
            ]
        )

        features = {feature["source_route_id"]: feature for feature in layer.getFeatures()}
        self.assertEqual(layer.uri, "LineStringZ?crs=EPSG:4326")
        self.assertEqual(features["z-route"].geometry().kind, "z")
        self.assertEqual(features["polyline-only"].geometry().kind, "z")
        self.assertTrue(
            math.isnan(features["polyline-only"].geometry().points[0].z)
        )
        self.assertEqual(features["polyline-only"]["has_elevation"], 0)

    def test_route_profile_samples_use_stable_join_key_and_group_index(self):
        builders = _load_builder_with_stubs(self)

        layer = builders.build_route_profile_sample_layer(
            [
                {
                    "source": "strava",
                    "source_route_id": "42",
                    "name": "Swiss gravel loop",
                    "profile_points": [
                        {"point_index": 0, "lat": 46.5, "lon": 6.6, "distance_m": 0.0, "altitude_m": None},
                    ],
                }
            ]
        )

        sample = next(layer.getFeatures())
        self.assertIn("sample_group_index", sample.attributes)
        self.assertEqual(sample["sample_group_index"], 1)
        self.assertEqual((sample["source"], sample["source_route_id"]), ("strava", "42"))
        self.assertIsNone(sample["altitude_m"])


if __name__ == "__main__":
    unittest.main()
