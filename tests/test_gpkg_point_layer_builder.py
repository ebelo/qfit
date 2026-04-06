import importlib.util
import os
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests import _path  # noqa: F401

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
        _metric_value,
        _sample_points,
        build_point_layer,
    )
    from qfit.gpkg_point_layer_builder import build_point_layer as legacy_build_point_layer
else:  # pragma: no cover
    _metric_value = None
    _sample_points = None
    build_point_layer = None

_QGIS_APP = None


def _ensure_qgis_app():
    if not _REAL_QGIS_PRESENT:
        raise unittest.SkipTest("QGIS Python bindings are not available")

    global QgsApplication
    global _metric_value
    global _sample_points
    global build_point_layer
    global _QGIS_APP
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
            _metric_value as real_metric_value,
            _sample_points as real_sample_points,
            build_point_layer as real_build_point_layer,
        )

        _metric_value = real_metric_value
        _sample_points = real_sample_points
        build_point_layer = real_build_point_layer
    if _QGIS_APP is None:
        _QGIS_APP = QgsApplication([], False)
        _QGIS_APP.initQgis()
    return _QGIS_APP


@unittest.skipIf(not _REAL_QGIS_PRESENT, "QGIS Python bindings are not available")
class GpkgPointLayerBuilderShimTests(unittest.TestCase):
    def test_legacy_gpkg_point_layer_builder_shim_exports_same_function(self):
        global legacy_build_point_layer

        _ensure_qgis_app()
        if "legacy_build_point_layer" not in globals():
            from qfit.gpkg_point_layer_builder import (
                build_point_layer as legacy_build_point_layer,
            )

        self.assertIs(legacy_build_point_layer, build_point_layer)


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
        strided_indexes = sorted(f["point_index"] for f in layer_strided.getFeatures())
        self.assertEqual(strided_indexes[-1], 9)


if __name__ == "__main__":
    unittest.main()
