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
    from qfit.activities.infrastructure.geopackage.gpkg_layer_builders import (
        _activity_geometry,
        _fallback_geometry,
        _geometry_from_points,
        build_start_layer,
        build_track_layer,
    )
    from qfit.gpkg_layer_builders import (
        build_start_layer as legacy_build_start_layer,
        build_track_layer as legacy_build_track_layer,
    )
else:  # pragma: no cover
    _activity_geometry = None
    _fallback_geometry = None
    _geometry_from_points = None
    build_start_layer = None
    build_track_layer = None

_QGIS_APP = None


def _ensure_qgis_app():
    global QgsApplication
    global _activity_geometry
    global _fallback_geometry
    global _geometry_from_points
    global build_start_layer
    global build_track_layer
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
    if build_track_layer is None:
        sys.modules.pop(
            "qfit.activities.infrastructure.geopackage.gpkg_layer_builders",
            None,
        )
        from qfit.activities.infrastructure.geopackage.gpkg_layer_builders import (
            _activity_geometry as real_activity_geometry,
            _fallback_geometry as real_fallback_geometry,
            _geometry_from_points as real_geometry_from_points,
            build_start_layer as real_build_start_layer,
            build_track_layer as real_build_track_layer,
        )

        _activity_geometry = real_activity_geometry
        _fallback_geometry = real_fallback_geometry
        _geometry_from_points = real_geometry_from_points
        build_start_layer = real_build_start_layer
        build_track_layer = real_build_track_layer
    if _QGIS_APP is None:
        _QGIS_APP = QgsApplication([], False)
        _QGIS_APP.initQgis()
    return _QGIS_APP


@unittest.skipIf(not _REAL_QGIS_PRESENT, "QGIS Python bindings are not available")
class GpkgLayerBuilderShimTests(unittest.TestCase):
    def test_legacy_gpkg_layer_builder_shim_exports_same_functions(self):
        global legacy_build_start_layer
        global legacy_build_track_layer

        _ensure_qgis_app()
        if "legacy_build_start_layer" not in globals():
            from qfit.gpkg_layer_builders import (
                build_start_layer as legacy_build_start_layer,
                build_track_layer as legacy_build_track_layer,
            )

        self.assertIs(legacy_build_start_layer, build_start_layer)
        self.assertIs(legacy_build_track_layer, build_track_layer)


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


if __name__ == "__main__":
    unittest.main()
