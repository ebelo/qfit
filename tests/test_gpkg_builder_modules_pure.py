import importlib
import sys
import unittest
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

from tests import _path  # noqa: F401


class _FakeFeature(dict):
    def __init__(self, fields):
        super().__init__()
        self.fields = fields
        self.geometry = None

    def setGeometry(self, geometry):
        self.geometry = geometry


class _FakeProvider:
    def __init__(self):
        self.attributes = []
        self.features = []

    def addAttributes(self, attrs):
        self.attributes.extend(attrs)

    def addFeature(self, feature):
        self.features.append(feature)

    def addFeatures(self, features):
        self.features.extend(features)


class _FakeLayer:
    def __init__(self, geometry_type, name, provider_name):
        self.geometry_type = geometry_type
        self.name = name
        self.provider_name = provider_name
        self._provider = _FakeProvider()

    def dataProvider(self):
        return self._provider

    def updateFields(self):
        return None

    def updateExtents(self):
        return None

    def fields(self):
        return list(self._provider.attributes)

    def getFeatures(self):
        return iter(self._provider.features)

    def featureCount(self):
        return len(self._provider.features)


class _FakePointXY:
    def __init__(self, x, y):
        self.x = x
        self.y = y


class _FakeGeometry:
    @staticmethod
    def fromPointXY(point):
        return ("point", point.x, point.y)

    @staticmethod
    def fromPolylineXY(points):
        return ("polyline", [(point.x, point.y) for point in points])


def _fake_qgis_modules():
    qgis = ModuleType("qgis")
    qgis_core = ModuleType("qgis.core")
    qgis_core.QgsFeature = _FakeFeature
    qgis_core.QgsGeometry = _FakeGeometry
    qgis_core.QgsPointXY = _FakePointXY
    qgis_core.QgsVectorLayer = _FakeLayer
    qgis.core = qgis_core
    return {
        "qgis": qgis,
        "qgis.core": qgis_core,
    }


def _fake_schema_module():
    schema = ModuleType("qfit.activities.infrastructure.geopackage.gpkg_schema")
    schema.COVER_HIGHLIGHT_FIELDS = ["highlight_order"]
    schema.DOCUMENT_SUMMARY_FIELDS = ["activity_count"]
    schema.PAGE_DETAIL_ITEM_FIELDS = ["page_number"]
    schema.PROFILE_SAMPLE_FIELDS = ["profile_point_index"]
    schema.TOC_FIELDS = ["page_number"]
    schema.POINT_FIELDS = ["point_index"]
    schema.START_FIELDS = ["source_activity_id"]
    schema.TRACK_FIELDS = ["source_activity_id"]
    schema.make_qgs_fields = lambda defs: list(defs)
    return schema


def _fake_publish_atlas_module():
    mod = ModuleType("qfit.atlas.publish_atlas")
    mod.build_atlas_page_plans = lambda records, settings=None: ["plan"]
    mod.build_atlas_document_summary_from_plans = lambda plans: SimpleNamespace(
        activity_count=2,
        activity_date_start="2026-04-01",
        activity_date_end="2026-04-02",
        date_range_label="2 days",
        total_distance_m=12345,
        total_distance_label="12.3 km",
        total_moving_time_s=3600,
        total_duration_label="1 h",
        total_elevation_gain_m=456,
        total_elevation_gain_label="456 m",
        activity_types_label="Ride, Run",
        cover_summary="2 activities",
    )
    mod.build_atlas_cover_highlights_from_summary = lambda summary: [
        SimpleNamespace(
            highlight_order=1,
            highlight_key="distance",
            highlight_label="Distance",
            highlight_value=summary.total_distance_label,
        )
    ]
    mod.build_atlas_page_detail_items = lambda records, settings=None, plans=None: [
        SimpleNamespace(
            page_number=1,
            page_sort_key="001",
            page_name="page-1",
            page_title="Day 1",
            detail_order=1,
            detail_key="distance",
            detail_label="Distance",
            detail_value="12.3 km",
        )
    ]
    mod.build_atlas_profile_samples = lambda records, settings=None, plans=None: [
        SimpleNamespace(
            page_number=1,
            page_sort_key="001",
            page_name="page-1",
            page_title="Day 1",
            page_date="2026-04-01",
            source="track",
            source_activity_id="42",
            activity_type="Ride",
            profile_point_index=0,
            profile_point_count=1,
            profile_point_ratio=0.0,
            distance_m=0.0,
            distance_label="0 km",
            altitude_m=500.0,
            profile_distance_m=0.0,
        )
    ]
    mod.build_atlas_toc_entries = lambda records, settings=None, plans=None: [
        SimpleNamespace(
            page_number=1,
            page_number_label="1",
            page_sort_key="001",
            page_name="page-1",
            page_title="Day 1",
            page_subtitle="Loop",
            page_date="2026-04-01",
            page_toc_label="Day 1",
            toc_entry_label="Day 1 - Loop",
            page_distance_label="12.3 km",
            page_duration_label="1 h",
            page_stats_summary="12.3 km • 1 h",
            profile_available=True,
            page_profile_summary="Profile ready",
        )
    ]
    return mod


def _fake_layer_builders_module():
    mod = ModuleType("qfit.activities.infrastructure.geopackage.gpkg_layer_builders")
    mod.parse_record_coordinate = lambda record, x_key, y_key: (
        float(record[x_key]),
        float(record[y_key]),
    )
    return mod


def _fake_polyline_utils_module():
    mod = ModuleType("qfit.polyline_utils")
    mod.decode_polyline = lambda polyline: [(46.0, 7.0), (46.1, 7.1)] if polyline else []
    return mod


def _fake_atlas_page_builder_module():
    mod = ModuleType("qfit.activities.infrastructure.geopackage.gpkg_atlas_page_builder")
    mod.build_atlas_layer = lambda records, settings=None: "atlas-layer"
    return mod


class GpkgBuilderModulesPureTests(unittest.TestCase):
    def _import_with_stubs(self):
        module_overrides = {
            **_fake_qgis_modules(),
            "qfit.activities.infrastructure.geopackage.gpkg_schema": _fake_schema_module(),
            "qfit.gpkg_schema": _fake_schema_module(),
            "qfit.atlas.publish_atlas": _fake_publish_atlas_module(),
            "qfit.activities.infrastructure.geopackage.gpkg_layer_builders": _fake_layer_builders_module(),
            "qfit.polyline_utils": _fake_polyline_utils_module(),
            "qfit.activities.infrastructure.geopackage.gpkg_atlas_page_builder": _fake_atlas_page_builder_module(),
            "qfit.gpkg_atlas_page_builder": _fake_atlas_page_builder_module(),
        }
        with patch.dict(sys.modules, module_overrides):
            for name in [
                "qfit.activities.infrastructure.geopackage.gpkg_atlas_table_builders",
                "qfit.activities.infrastructure.geopackage.gpkg_point_layer_builder",
                "qfit.activities.infrastructure.geopackage.gpkg_layer_builders",
                "qfit.gpkg_atlas_table_builders",
                "qfit.gpkg_point_layer_builder",
                "qfit.gpkg_layer_builders",
            ]:
                sys.modules.pop(name, None)
            atlas_tables = importlib.import_module(
                "qfit.activities.infrastructure.geopackage.gpkg_atlas_table_builders"
            )
            point_builder = importlib.import_module(
                "qfit.activities.infrastructure.geopackage.gpkg_point_layer_builder"
            )
            layer_builders = importlib.import_module(
                "qfit.activities.infrastructure.geopackage.gpkg_layer_builders"
            )
            legacy_atlas_tables = importlib.import_module("qfit.gpkg_atlas_table_builders")
            legacy_point_builder = importlib.import_module("qfit.gpkg_point_layer_builder")
            legacy_layer_builders = importlib.import_module("qfit.gpkg_layer_builders")
        return (
            atlas_tables,
            point_builder,
            layer_builders,
            legacy_atlas_tables,
            legacy_point_builder,
            legacy_layer_builders,
        )

    def test_moved_atlas_table_builders_work_without_real_qgis(self):
        atlas_tables, _, _, legacy_atlas_tables, _, _ = self._import_with_stubs()

        summary_layer = atlas_tables.build_document_summary_layer(records=[{"id": 1}])
        highlight_layer = atlas_tables.build_cover_highlight_layer(records=[{"id": 1}])
        detail_layer = atlas_tables.build_page_detail_item_layer(records=[{"id": 1}])
        profile_layer = atlas_tables.build_profile_sample_layer(records=[{"id": 1}])
        toc_layer = atlas_tables.build_toc_layer(records=[{"id": 1}])

        self.assertEqual(summary_layer.featureCount(), 1)
        self.assertEqual(highlight_layer.featureCount(), 1)
        self.assertEqual(detail_layer.featureCount(), 1)
        self.assertEqual(profile_layer.featureCount(), 1)
        self.assertEqual(toc_layer.featureCount(), 1)
        self.assertIs(
            legacy_atlas_tables.build_document_summary_layer,
            atlas_tables.build_document_summary_layer,
        )

    def test_moved_point_layer_builder_works_without_real_qgis(self):
        _, point_builder, _, _, legacy_point_builder, _ = self._import_with_stubs()

        layer = point_builder.build_point_layer(
            [
                {
                    "source": "track",
                    "source_activity_id": "42",
                    "start_date": "2026-04-01T10:00:00Z",
                    "start_date_local": "2026-04-01T12:00:00",
                    "name": "Morning Ride",
                    "activity_type": "Ride",
                    "distance_m": 12.5,
                    "geometry_points": [(46.0, 7.0)],
                    "details_json": {
                        "stream_metrics": {
                            "time": [0],
                            "distance": [12.5],
                            "altitude": [600.0],
                            "heartrate": [120],
                            "cadence": [85],
                            "watts": [210],
                            "velocity_smooth": [7.5],
                            "temp": [18.0],
                            "grade_smooth": [4.2],
                            "moving": [True],
                        }
                    },
                }
            ],
            write_activity_points=True,
        )

        features = list(layer.getFeatures())
        self.assertEqual(len(features), 1)
        self.assertEqual(features[0]["source_activity_id"], "42")
        self.assertEqual(features[0].geometry, ("point", 7.0, 46.0))
        self.assertIs(legacy_point_builder.build_point_layer, point_builder.build_point_layer)

    def test_moved_layer_builders_work_without_real_qgis(self):
        _, _, layer_builders, _, _, legacy_layer_builders = self._import_with_stubs()

        records = [
            {
                "source": "track",
                "source_activity_id": "42",
                "external_id": "ext-42",
                "name": "Morning Ride",
                "activity_type": "Ride",
                "sport_type": "cycling",
                "start_date": "2026-04-01T10:00:00Z",
                "start_date_local": "2026-04-01T12:00:00",
                "timezone": "Europe/Zurich",
                "distance_m": 12.5,
                "moving_time_s": 3600,
                "elapsed_time_s": 3700,
                "total_elevation_gain_m": 456.0,
                "average_speed_mps": 7.5,
                "max_speed_mps": 12.0,
                "average_heartrate": 120,
                "max_heartrate": 150,
                "average_watts": 210,
                "kilojoules": 600,
                "calories": 700,
                "suffer_score": 25,
                "start_lat": 46.0,
                "start_lon": 7.0,
                "end_lat": 46.1,
                "end_lon": 7.1,
                "summary_polyline": "encoded",
                "geometry_points": [(46.0, 7.0), (46.1, 7.1)],
                "details_json": {"ok": True},
                "summary_hash": "hash",
                "first_seen_at": "now",
                "last_synced_at": "now",
            }
        ]

        track_layer = layer_builders.build_track_layer(records)
        start_layer = layer_builders.build_start_layer(records)
        geometry, source, count = layer_builders._activity_geometry(records[0])
        fallback = layer_builders._fallback_geometry(records[0])

        self.assertEqual(track_layer.featureCount(), 1)
        self.assertEqual(start_layer.featureCount(), 1)
        self.assertEqual(source, "stream")
        self.assertEqual(count, 2)
        self.assertIsNotNone(geometry)
        self.assertIsNotNone(fallback)
        self.assertIs(legacy_layer_builders.build_track_layer, layer_builders.build_track_layer)


if __name__ == "__main__":
    unittest.main()
