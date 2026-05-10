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
    _REAL_QGIS_PRESENT = any(
        os.path.isdir(os.path.join(p, "qgis")) for p in sys.path if p
    )

try:
    from qgis.core import QgsApplication
except (ImportError, ModuleNotFoundError):  # pragma: no cover
    QgsApplication = None

if QgsApplication is not None and _REAL_QGIS_PRESENT:
    from qfit.activities.infrastructure.geopackage.gpkg_point_layer_builder import (
        _activity_point_sequence,
        _has_stream_metric_values,
        _metric_value,
        _normalized_points,
        _sample_points,
        _stream_metrics,
        _stream_status,
        build_point_layer,
    )
else:  # pragma: no cover
    _activity_point_sequence = None
    _has_stream_metric_values = None
    _metric_value = None
    _normalized_points = None
    _sample_points = None
    _stream_metrics = None
    _stream_status = None
    build_point_layer = None


def _ensure_qgis_app():
    if not _REAL_QGIS_PRESENT:
        raise unittest.SkipTest("QGIS Python bindings are not available")

    global QgsApplication
    global _activity_point_sequence
    global _has_stream_metric_values
    global _metric_value
    global _normalized_points
    global _sample_points
    global _stream_metrics
    global _stream_status
    global build_point_layer
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
        from qgis.core import QgsApplication as RealQgsApplication  # type: ignore

        QgsApplication = RealQgsApplication
    if build_point_layer is None:
        sys.modules.pop(
            "qfit.activities.infrastructure.geopackage.gpkg_point_layer_builder",
            None,
        )
        from qfit.activities.infrastructure.geopackage.gpkg_point_layer_builder import (
            _activity_point_sequence as real_activity_point_sequence,
            _has_stream_metric_values as real_has_stream_metric_values,
            _metric_value as real_metric_value,
            _normalized_points as real_normalized_points,
            _sample_points as real_sample_points,
            _stream_metrics as real_stream_metrics,
            _stream_status as real_stream_status,
            build_point_layer as real_build_point_layer,
        )

        _activity_point_sequence = real_activity_point_sequence
        _has_stream_metric_values = real_has_stream_metric_values
        _metric_value = real_metric_value
        _normalized_points = real_normalized_points
        _sample_points = real_sample_points
        _stream_metrics = real_stream_metrics
        _stream_status = real_stream_status
        build_point_layer = real_build_point_layer
    return get_shared_qgis_app(QgsApplication)


class SamplePointsTests(unittest.TestCase):
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
        self.assertIn(4, indexes)

    def test_stride_larger_than_list(self):
        points = [(1.0, 2.0), (3.0, 4.0)]
        result = _sample_points(points, 10)
        indexes = [r[0] for r in result]
        self.assertIn(0, indexes)
        self.assertIn(1, indexes)

    def test_single_point(self):
        points = [(5.0, 6.0)]
        result = _sample_points(points, 1)
        self.assertEqual(result, [(0, 5.0, 6.0)])


class PointSequenceHelperTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _ensure_qgis_app()

    def test_normalized_points_skips_invalid_values(self):
        points = _normalized_points([(46.5, 6.6), ("bad", 6.7), (1,), None])
        self.assertEqual(points, [(46.5, 6.6)])

    def test_activity_point_sequence_prefers_stream_points(self):
        points, geometry_source = _activity_point_sequence(
            {
                "geometry_points": [(46.5, 6.6), (46.6, 6.7)],
                "summary_polyline": "_p~iF~ps|U_ulLnnqC_mqNvxq`@",
            }
        )

        self.assertEqual(geometry_source, "stream")
        self.assertEqual(points, [(46.5, 6.6), (46.6, 6.7)])

    def test_stream_metrics_only_returned_for_stream_geometry(self):
        record = {"details_json": {"stream_metrics": {"time": [0, 1]}}}

        self.assertEqual(_stream_metrics(record, "stream"), {"time": [0, 1]})
        self.assertEqual(_stream_metrics(record, "summary_polyline"), {})

    def test_stream_metrics_ignore_non_dict_details_json(self):
        record = {"details_json": '{"stream_metrics": {"time": [0, 1]}}'}

        self.assertEqual(_stream_metrics(record, "stream"), {})

    def test_has_stream_metric_values_requires_non_empty_metric_lists(self):
        self.assertTrue(_has_stream_metric_values({"time": [0]}))
        self.assertFalse(_has_stream_metric_values({"time": []}))
        self.assertFalse(_has_stream_metric_values({"time": None}))
        self.assertFalse(_has_stream_metric_values(None))

    def test_stream_status_records_unavailable_summary_geometry(self):
        self.assertEqual(
            _stream_status("summary_polyline", {}),
            "summary_polyline_no_stream_metrics",
        )
        self.assertEqual(_stream_status("start_end", {}), "start_end_no_stream_metrics")
        self.assertEqual(_stream_status("stream", {"time": [0]}), "stream_metrics")
        self.assertEqual(_stream_status("stream", {}), "stream_missing_metrics")

    def test_activity_point_sequence_returns_empty_when_no_geometry_is_available(self):
        points, geometry_source = _activity_point_sequence(
            {
                "geometry_points": [],
                "summary_polyline": None,
                "start_lat": None,
                "start_lon": None,
                "end_lat": None,
                "end_lon": None,
            }
        )

        self.assertEqual(points, [])
        self.assertIsNone(geometry_source)


@unittest.skipIf(QgsApplication is None, "QGIS Python bindings are not available")
class MetricValueTests(unittest.TestCase):
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
        self.assertEqual(features[0]["stream_status"], "stream_metrics")
        self.assertEqual(features[-1]["point_index"], 2)
        self.assertEqual(features[-1]["altitude_m"], 410.0)
        self.assertEqual(features[-1]["point_ratio"], 1.0)

    def test_summary_polyline_points_have_no_stream_metrics_status(self):
        records = [
            {
                "source": "strava",
                "source_activity_id": "18449273890",
                "name": "Morning Ride",
                "activity_type": "Ride",
                "summary_polyline": "_p~iF~ps|U_ulLnnqC_mqNvxq`@",
                "details_json": {
                    "average_cadence": 71.8,
                    "weighted_average_watts": 140,
                },
            }
        ]

        layer = build_point_layer(records, write_activity_points=True, point_stride=1)

        self.assertTrue(layer.isValid())
        self.assertGreaterEqual(layer.featureCount(), 3)
        features = list(layer.getFeatures())
        self.assertEqual(features[0]["geometry_source"], "summary_polyline")
        self.assertEqual(
            features[0]["stream_status"],
            "summary_polyline_no_stream_metrics",
        )

    def test_stream_metrics_populate_detailed_analysis_fields(self):
        records = [
            {
                "source": "strava",
                "source_activity_id": "18449273890",
                "name": "Morning Ride",
                "activity_type": "Ride",
                "distance_m": 30240.0,
                "geometry_points": [(46.50, 6.60), (46.51, 6.61)],
                "details_json": {
                    "average_cadence": 71.8,
                    "weighted_average_watts": 140,
                    "stream_metrics": {
                        "time": [0, 60],
                        "distance": [0.0, 250.0],
                        "altitude": [520.0, 535.0],
                        "heartrate": [130, 136],
                        "cadence": [72, 75],
                        "watts": [118, 180],
                        "velocity_smooth": [5.2, 6.0],
                        "grade_smooth": [1.5, 4.2],
                    },
                },
            }
        ]

        layer = build_point_layer(records, write_activity_points=True, point_stride=1)

        feature = list(layer.getFeatures())[1]
        self.assertEqual(feature["stream_status"], "stream_metrics")
        self.assertEqual(feature["stream_time_s"], 60)
        self.assertEqual(feature["stream_distance_m"], 250.0)
        self.assertEqual(feature["altitude_m"], 535.0)
        self.assertEqual(feature["heartrate_bpm"], 136.0)
        self.assertEqual(feature["cadence_rpm"], 75.0)
        self.assertEqual(feature["watts"], 180.0)
        self.assertEqual(feature["velocity_mps"], 6.0)
        self.assertEqual(feature["grade_smooth_pct"], 4.2)

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
        strided_indexes = sorted(f["point_index"] for f in layer_strided.getFeatures())
        self.assertEqual(strided_indexes[-1], 9)

    def test_builds_features_from_summary_polyline_when_stream_points_are_missing(self):
        records = [
            {
                "source": "strava",
                "source_activity_id": "1",
                "summary_polyline": "_p~iF~ps|U_ulLnnqC_mqNvxq`@",
            }
        ]

        layer = build_point_layer(records, write_activity_points=True, point_stride=1)

        self.assertTrue(layer.isValid())
        self.assertGreaterEqual(layer.featureCount(), 3)
        features = list(layer.getFeatures())
        self.assertEqual(features[0]["geometry_source"], "summary_polyline")

    def test_builds_features_from_start_end_when_no_other_geometry_is_available(self):
        records = [
            {
                "source": "strava",
                "source_activity_id": "1",
                "start_lat": 46.5,
                "start_lon": 6.6,
                "end_lat": 46.6,
                "end_lon": 6.7,
            }
        ]

        layer = build_point_layer(records, write_activity_points=True, point_stride=1)

        self.assertTrue(layer.isValid())
        self.assertEqual(layer.featureCount(), 2)
        features = list(layer.getFeatures())
        self.assertEqual(features[0]["geometry_source"], "start_end")
        self.assertEqual(features[-1]["point_index"], 1)

    def test_skips_records_without_any_usable_geometry(self):
        records = [
            {
                "source": "strava",
                "source_activity_id": "1",
                "geometry_points": [("bad", 6.6)],
                "summary_polyline": None,
                "start_lat": None,
                "start_lon": None,
                "end_lat": None,
                "end_lon": None,
            }
        ]

        layer = build_point_layer(records, write_activity_points=True, point_stride=1)

        self.assertTrue(layer.isValid())
        self.assertEqual(layer.featureCount(), 0)


if __name__ == "__main__":
    unittest.main()
