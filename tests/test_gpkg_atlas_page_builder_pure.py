import importlib
import sys
import unittest
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, patch

from tests import _path  # noqa: F401


class _FakeGeometry:
    @staticmethod
    def fromRect(rect):
        return {"rect": rect}


class _FakeRectangle:
    def __init__(self, x_min, y_min, x_max, y_max):
        self.xMinimum = x_min
        self.yMinimum = y_min
        self.xMaximum = x_max
        self.yMaximum = y_max


class _FakePointXY:
    def __init__(self, x, y):
        self.x = x
        self.y = y


class _FakeFeature:
    def __init__(self, fields):
        self._fields = fields
        self._values = {}
        self.geometry = None

    def setGeometry(self, geometry):
        self.geometry = geometry

    def __setitem__(self, key, value):
        self._values[key] = value

    def __getitem__(self, key):
        return self._values[key]


class _FakeProvider:
    def __init__(self, layer):
        self._layer = layer

    def addAttributes(self, fields):
        self._layer._fields = fields

    def addFeatures(self, features):
        self._layer._features.extend(features)


class _FakeVectorLayer:
    def __init__(self, layer_def, name, provider_name):
        self.layer_def = layer_def
        self.name = name
        self.provider_name = provider_name
        self._fields = []
        self._features = []
        self._provider = _FakeProvider(self)

    def dataProvider(self):
        return self._provider

    def updateFields(self):
        pass

    def updateExtents(self):
        pass

    def fields(self):
        return self._fields

    def featureCount(self):
        return len(self._features)

    def getFeatures(self):
        return list(self._features)

    def isValid(self):
        return True


def _make_qgis_stubs():
    qgis_mod = ModuleType("qgis")
    qgis_core = ModuleType("qgis.core")
    qgis_core.QgsFeature = _FakeFeature
    qgis_core.QgsGeometry = _FakeGeometry
    qgis_core.QgsPointXY = _FakePointXY
    qgis_core.QgsRectangle = _FakeRectangle
    qgis_core.QgsVectorLayer = _FakeVectorLayer
    qgis_mod.core = qgis_core
    return qgis_mod, qgis_core


def _make_schema_stub():
    schema = ModuleType("qfit.gpkg_schema")
    schema.ATLAS_FIELDS = [("name", "String"), ("document_cover_summary", "String")]
    schema.START_FIELDS = [("source", "String")]
    schema.TRACK_FIELDS = [("source", "String")]
    schema.make_qgs_fields = lambda field_defs: [name for name, _ in field_defs]
    return schema


def _plan(**overrides):
    values = {
        "page_number": 1,
        "source": "strava",
        "source_activity_id": "100",
        "name": "Morning Ride",
        "activity_type": "Ride",
        "start_date": "2026-03-18T07:10:00Z",
        "distance_m": 42500.0,
        "moving_time_s": 7200,
        "geometry_source": "stream",
        "page_sort_key": "0001",
        "page_name": "morning-ride",
        "page_title": "Morning Ride",
        "page_subtitle": "Ride",
        "page_date": "2026-03-18",
        "page_toc_label": "2026-03-18 · Morning Ride · 42.5 km · 2h 00m",
        "page_distance_label": "42.5 km",
        "page_duration_label": "2h 00m",
        "page_average_speed_label": "21.3 km/h",
        "page_average_pace_label": None,
        "page_elevation_gain_label": "640 m",
        "page_stats_summary": "42.5 km · 2h 00m · 21.3 km/h · ↑ 640 m",
        "page_profile_summary": "Profile available",
        "document_activity_count": 2,
        "document_date_range_label": "2026-03-18 → 2026-03-19",
        "document_total_distance_label": "52.6 km",
        "document_total_duration_label": "2h 50m",
        "document_total_elevation_gain_label": "725 m",
        "document_activity_types_label": "Ride, Run",
        "document_cover_summary": "2 activities · 2026-03-18 → 2026-03-19 · 52.6 km · 2h 50m · ↑ 725 m · Ride, Run",
        "profile_available": True,
        "profile_point_count": 4,
        "profile_distance_m": 42500.0,
        "profile_distance_label": "42.5 km",
        "profile_min_altitude_m": 430.0,
        "profile_max_altitude_m": 452.0,
        "profile_altitude_range_label": "430–452 m",
        "profile_relief_m": 22.0,
        "profile_elevation_gain_m": 640.0,
        "profile_elevation_gain_label": "640 m",
        "profile_elevation_loss_m": 640.0,
        "profile_elevation_loss_label": "640 m",
        "center_x_3857": 1000.0,
        "center_y_3857": 2000.0,
        "extent_width_deg": 0.2,
        "extent_height_deg": 0.1,
        "extent_width_m": 4000.0,
        "extent_height_m": 2000.0,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


class BuildAtlasLayerPureTests(unittest.TestCase):
    def _import_modules(self):
        qgis_mod, qgis_core = _make_qgis_stubs()
        schema_stub = _make_schema_stub()
        publish_atlas_stub = ModuleType("qfit.atlas.publish_atlas")
        publish_atlas_stub.build_atlas_page_plans = Mock(return_value=[_plan()])

        module_overrides = {
            "qgis": qgis_mod,
            "qgis.core": qgis_core,
            "qfit.gpkg_schema": schema_stub,
            "qfit.atlas.publish_atlas": publish_atlas_stub,
        }

        with patch.dict(sys.modules, module_overrides):
            sys.modules.pop("qfit.gpkg_atlas_page_builder", None)
            sys.modules.pop("qfit.gpkg_layer_builders", None)
            atlas_page_builder = importlib.import_module("qfit.gpkg_atlas_page_builder")
            layer_builders = importlib.import_module("qfit.gpkg_layer_builders")

        return atlas_page_builder, layer_builders, publish_atlas_stub

    def test_build_atlas_layer_uses_plan_values_and_precomputed_plans(self):
        atlas_page_builder, _, _ = self._import_modules()

        plan = _plan(center_x_3857=1500.0, center_y_3857=2500.0, extent_width_m=600.0, extent_height_m=300.0)
        layer = atlas_page_builder.build_atlas_layer([], atlas_page_settings=None, plans=[plan])

        self.assertTrue(layer.isValid())
        self.assertEqual(layer.featureCount(), 1)
        feature = layer.getFeatures()[0]
        rect = feature.geometry["rect"]
        self.assertEqual(rect.xMinimum, 1200.0)
        self.assertEqual(rect.yMinimum, 2350.0)
        self.assertEqual(rect.xMaximum, 1800.0)
        self.assertEqual(rect.yMaximum, 2650.0)
        self.assertEqual(feature["page_title"], "Morning Ride")
        self.assertEqual(feature["document_cover_summary"], plan.document_cover_summary)
        self.assertEqual(feature["profile_available"], 1)

    def test_build_atlas_layer_computes_plans_when_not_supplied(self):
        atlas_page_builder, layer_builders, publish_atlas_stub = self._import_modules()

        layer = atlas_page_builder.build_atlas_layer([{"name": "ignored"}], atlas_page_settings={"margin": 0.1})

        publish_atlas_stub.build_atlas_page_plans.assert_called_once_with(
            [{"name": "ignored"}], settings={"margin": 0.1}
        )
        self.assertEqual(layer.featureCount(), 1)
        self.assertIs(layer_builders.build_atlas_layer, atlas_page_builder.build_atlas_layer)


if __name__ == "__main__":
    unittest.main()
