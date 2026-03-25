import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests import _path  # noqa: F401

try:
    from qgis.core import QgsApplication
except (ImportError, ModuleNotFoundError):  # pragma: no cover
    QgsApplication = None

if QgsApplication is not None:
    from qfit.gpkg_layer_builders import (
        _activity_geometry,
        _fallback_geometry,
        _geometry_from_points,
        _metric_value,
        _sample_points,
        build_point_layer,
        build_start_layer,
        build_track_layer,
    )
else:  # pragma: no cover
    _activity_geometry = None
    _fallback_geometry = None
    _geometry_from_points = None
    _metric_value = None
    _sample_points = None
    build_point_layer = None
    build_start_layer = None
    build_track_layer = None

_QGIS_APP = None


def _ensure_qgis_app():
    global _QGIS_APP
    if _QGIS_APP is None:
        _QGIS_APP = QgsApplication([], False)
        _QGIS_APP.initQgis()
    return _QGIS_APP


@unittest.skipIf(QgsApplication is None, "QGIS Python bindings are not available")
class SamplePointsTests(unittest.TestCase):
    """Tests for _sample_points (pure logic, no QGIS geometry)."""

    @classmethod
    def setUpClass(cls):
        _ensure_qgis_app()

    def test_empty_points_returns_empty(self):
        self.assertEqual(_sample_points([], 1), [])

    def test_stride_one_returns_all(self):
        points = [(1.0, 2.0), (3.0, 4.0), (5.0, 6.0)]
        result = _sample_points(points, 1)
        self.assertEqual(len(result), 3)
        self.assertEqual(result[0], (0, 1.0, 2.0))
        self.assertEqual(result[2], (2, 5.0, 6.0))

    def test_stride_two_includes_last(self):
        points = [(1.0, 2.0), (3.0, 4.0), (5.0, 6.0), (7.0, 8.0), (9.0, 10.0)]
        result = _sample_points(points, 2)
        indexes = [r[0] for r in result]
        self.assertIn(0, indexes)
        self.assertIn(4, indexes)  # last point always included

    def test_stride_larger_than_list(self):
        points = [(1.0, 2.0), (3.0, 4.0)]
        result = _sample_points(points, 10)
        indexes = [r[0] for r in result]
        self.assertIn(0, indexes)
        self.assertIn(1, indexes)  # last point always included

    def test_single_point(self):
        points = [(5.0, 6.0)]
        result = _sample_points(points, 1)
        self.assertEqual(result, [(0, 5.0, 6.0)])


@unittest.skipIf(QgsApplication is None, "QGIS Python bindings are not available")
class MetricValueTests(unittest.TestCase):
    """Tests for _metric_value (pure logic)."""

    @classmethod
    def setUpClass(cls):
        _ensure_qgis_app()

    def test_returns_float_by_default(self):
        self.assertEqual(_metric_value({"speed": [1.5, 2.5]}, "speed", 0), 1.5)

    def test_returns_int_when_as_int(self):
        self.assertEqual(_metric_value({"time": [10, 20]}, "time", 1, as_int=True), 20)

    def test_missing_key_returns_none(self):
        self.assertIsNone(_metric_value({"speed": [1.0]}, "missing", 0))

    def test_index_out_of_range_returns_none(self):
        self.assertIsNone(_metric_value({"speed": [1.0]}, "speed", 5))

    def test_none_value_returns_none(self):
        self.assertIsNone(_metric_value({"speed": [None]}, "speed", 0))

    def test_bool_true_as_int(self):
        self.assertEqual(_metric_value({"moving": [True]}, "moving", 0, as_int=True), 1)

    def test_bool_false_as_int(self):
        self.assertEqual(_metric_value({"moving": [False]}, "moving", 0, as_int=True), 0)

    def test_non_dict_metrics_returns_none(self):
        self.assertIsNone(_metric_value(None, "speed", 0))

    def test_invalid_float_returns_none(self):
        self.assertIsNone(_metric_value({"speed": ["bad"]}, "speed", 0))

    def test_invalid_int_returns_none(self):
        self.assertIsNone(_metric_value({"time": ["bad"]}, "time", 0, as_int=True))


@unittest.skipIf(QgsApplication is None, "QGIS Python bindings are not available")
class ActivityGeometryTests(unittest.TestCase):
    """Tests for _activity_geometry and its sub-helpers."""

    @classmethod
    def setUpClass(cls):
        _ensure_qgis_app()

    def test_geometry_from_points_valid(self):
        geom = _geometry_from_points([(46.5, 6.6), (46.6, 6.7)])
        self.assertIsNotNone(geom)
        self.assertFalse(geom.isEmpty())

    def test_geometry_from_points_too_few(self):
        self.assertIsNone(_geometry_from_points([]))
        self.assertIsNone(_geometry_from_points([(46.5, 6.6)]))

    def test_fallback_geometry_valid(self):
        record = {"start_lat": 46.5, "start_lon": 6.6, "end_lat": 46.6, "end_lon": 6.7}
        geom = _fallback_geometry(record)
        self.assertIsNotNone(geom)

    def test_fallback_geometry_missing_coords(self):
        self.assertIsNone(_fallback_geometry({"start_lat": 46.5}))
        self.assertIsNone(_fallback_geometry({}))

    def test_activity_geometry_prefers_geometry_points(self):
        record = {
            "geometry_points": [(46.5, 6.6), (46.6, 6.7)],
            "summary_polyline": "_p~iF~ps|U_ulLnnqC_mqNvxq`@",
        }
        geom, source, count = _activity_geometry(record)
        self.assertIsNotNone(geom)
        self.assertEqual(source, "stream")
        self.assertEqual(count, 2)

    def test_activity_geometry_falls_back_to_polyline(self):
        record = {"summary_polyline": "_p~iF~ps|U_ulLnnqC_mqNvxq`@"}
        geom, source, count = _activity_geometry(record)
        self.assertIsNotNone(geom)
        self.assertEqual(source, "summary_polyline")

    def test_activity_geometry_falls_back_to_start_end(self):
        record = {"start_lat": 46.5, "start_lon": 6.6, "end_lat": 46.6, "end_lon": 6.7}
        geom, source, count = _activity_geometry(record)
        self.assertIsNotNone(geom)
        self.assertEqual(source, "start_end")
        self.assertEqual(count, 2)

    def test_activity_geometry_no_data_returns_none(self):
        geom, source, count = _activity_geometry({})
        self.assertIsNone(geom)
        self.assertIsNone(source)
        self.assertEqual(count, 0)

    def test_activity_geometry_honours_explicit_geometry_source(self):
        record = {
            "geometry_points": [(46.5, 6.6), (46.6, 6.7)],
            "geometry_source": "custom",
        }
        _, source, _ = _activity_geometry(record)
        self.assertEqual(source, "custom")


@unittest.skipIf(QgsApplication is None, "QGIS Python bindings are not available")
class BuildTrackLayerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _ensure_qgis_app()

    def test_empty_records_returns_valid_layer(self):
        layer = build_track_layer([])
        self.assertTrue(layer.isValid())
        self.assertEqual(layer.featureCount(), 0)

    def test_record_without_geometry_skipped(self):
        records = [{"source": "strava", "source_activity_id": "1"}]
        layer = build_track_layer(records)
        self.assertEqual(layer.featureCount(), 0)

    def test_record_with_geometry_points_included(self):
        records = [
            {
                "source": "strava",
                "source_activity_id": "1",
                "name": "Morning Ride",
                "geometry_points": [(46.5, 6.6), (46.6, 6.7)],
                "distance_m": 15000.0,
            }
        ]
        layer = build_track_layer(records)
        self.assertEqual(layer.featureCount(), 1)
        feature = next(layer.getFeatures())
        self.assertEqual(feature["source"], "strava")
        self.assertEqual(feature["name"], "Morning Ride")
        self.assertEqual(feature["geometry_source"], "stream")
        self.assertEqual(feature["geometry_point_count"], 2)


@unittest.skipIf(QgsApplication is None, "QGIS Python bindings are not available")
class BuildStartLayerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _ensure_qgis_app()

    def test_empty_records_returns_valid_layer(self):
        layer = build_start_layer([])
        self.assertTrue(layer.isValid())
        self.assertEqual(layer.featureCount(), 0)

    def test_record_without_coords_skipped(self):
        records = [{"source": "strava", "source_activity_id": "1"}]
        layer = build_start_layer(records)
        self.assertEqual(layer.featureCount(), 0)

    def test_record_with_coords_included(self):
        records = [
            {
                "source": "strava",
                "source_activity_id": "1",
                "name": "Run",
                "start_lat": 46.5,
                "start_lon": 6.6,
            }
        ]
        layer = build_start_layer(records)
        self.assertEqual(layer.featureCount(), 1)
        feature = next(layer.getFeatures())
        self.assertEqual(feature["activity_fk"], 1)
        self.assertEqual(feature["source"], "strava")

    def test_activity_fk_is_1_based(self):
        records = [
            {"start_lat": 46.5, "start_lon": 6.6},
            {"start_lat": 47.0, "start_lon": 7.0},
        ]
        layer = build_start_layer(records)
        fks = sorted(f["activity_fk"] for f in layer.getFeatures())
        self.assertEqual(fks, [1, 2])


@unittest.skipIf(QgsApplication is None, "QGIS Python bindings are not available")
class BuildPointLayerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _ensure_qgis_app()

    def test_write_activity_points_false_returns_empty(self):
        records = [
            {
                "source": "strava",
                "source_activity_id": "1",
                "geometry_points": [(46.5, 6.6), (46.6, 6.7)],
            }
        ]
        layer = build_point_layer(records, write_activity_points=False)
        self.assertTrue(layer.isValid())
        self.assertEqual(layer.featureCount(), 0)

    def test_write_activity_points_true_builds_features(self):
        records = [
            {
                "source": "strava",
                "source_activity_id": "1",
                "name": "Ride",
                "activity_type": "Ride",
                "start_date": "2026-03-25T08:00:00Z",
                "start_date_local": "2026-03-25T09:00:00+01:00",
                "distance_m": 10000.0,
                "geometry_points": [(46.5, 6.6), (46.55, 6.65), (46.6, 6.7)],
                "details_json": {
                    "stream_metrics": {
                        "time": [0, 300, 600],
                        "distance": [0.0, 5000.0, 10000.0],
                        "altitude": [400.0, 420.0, 410.0],
                    }
                },
            }
        ]
        layer = build_point_layer(records, write_activity_points=True, point_stride=1)
        self.assertTrue(layer.isValid())
        self.assertEqual(layer.featureCount(), 3)
        features = list(layer.getFeatures())
        self.assertEqual(features[0]["activity_fk"], 1)
        self.assertEqual(features[0]["point_index"], 0)
        self.assertEqual(features[0]["altitude_m"], 400.0)
        self.assertEqual(features[-1]["point_index"], 2)
        self.assertEqual(features[-1]["altitude_m"], 410.0)
        self.assertEqual(features[-1]["point_ratio"], 1.0)

    def test_stride_reduces_feature_count(self):
        points = [(46.0 + i * 0.01, 6.0 + i * 0.01) for i in range(10)]
        records = [
            {
                "source": "strava",
                "source_activity_id": "1",
                "geometry_points": points,
            }
        ]
        layer_all = build_point_layer(records, write_activity_points=True, point_stride=1)
        layer_strided = build_point_layer(records, write_activity_points=True, point_stride=3)
        self.assertEqual(layer_all.featureCount(), 10)
        self.assertLess(layer_strided.featureCount(), 10)
        # last point must still be included
        strided_indexes = sorted(f["point_index"] for f in layer_strided.getFeatures())
        self.assertEqual(strided_indexes[-1], 9)


if __name__ == "__main__":
    unittest.main()
