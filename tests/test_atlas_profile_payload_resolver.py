import json
import importlib
import os
import sqlite3
import sys
import tempfile
import unittest
from types import ModuleType
from unittest.mock import MagicMock, patch

from tests import _path  # noqa: F401


class _FakeQgsTask:
    CanCancel = 1

    def __init__(self, description="", flags=0):
        self._cancelled = False

    def isCanceled(self):
        return self._cancelled

    def setProgress(self, value):  # noqa: N802
        pass


def _make_qgis_stub():
    qgis_core = ModuleType("qgis.core")
    qgis_core.QgsTask = _FakeQgsTask
    qgis_core.QgsProject = MagicMock()
    layout_instance = MagicMock()
    layout_instance.pageCollection.return_value.pageCount.return_value = 1
    layout_instance.pageCollection.return_value.page.return_value = MagicMock()
    layout_cls = MagicMock(return_value=layout_instance)
    qgis_core.QgsPrintLayout = layout_cls
    qgis_core.QgsLayoutItemMap = MagicMock()
    qgis_core.QgsLayoutItemMap.Auto = 1
    qgis_core.QgsLayoutItemMap.Fixed = 0
    qgis_core.QgsCoordinateReferenceSystem = MagicMock(return_value=MagicMock())
    qgis_core.QgsRectangle = MagicMock(return_value=MagicMock())
    qgis_core.QgsLayoutItemLabel = MagicMock()
    qgis_core.QgsLayoutItemElevationProfile = MagicMock()
    qgis_core.QgsProfileRequest = MagicMock()
    qgis_core.QgsGeometry = MagicMock()
    pic_cls = MagicMock()
    pic_cls.Zoom = 0
    qgis_core.QgsLayoutItemPicture = pic_cls
    qgis_core.QgsLayoutPoint = MagicMock()
    qgis_core.QgsLayoutSize = MagicMock()
    qgis_core.QgsLayoutExporter = MagicMock()
    qgis_core.QgsLayoutExporter.Success = 0
    qgis_core.QgsUnitTypes = MagicMock()
    qgis_core.QgsUnitTypes.LayoutMillimeters = 0
    qgis_core.QgsUnitTypes.RenderMillimeters = 1
    qgis_core.QgsAtlasComposition = MagicMock()
    qgis_core.QgsHeatmapRenderer = MagicMock()
    qgis_core.QgsStyle = MagicMock()
    qgis_core.QgsGradientColorRamp = MagicMock()

    qgis_pyt = ModuleType("qgis.PyQt")
    qgis_pyt_core = ModuleType("qgis.PyQt.QtCore")
    qgis_pyt_core.Qt = MagicMock()
    qgis_pyt_core.Qt.AlignRight = 2
    qgis_pyt_core.Qt.AlignLeft = 1
    qgis_pyt_core.Qt.AlignVCenter = 32
    qgis_pyt_gui = ModuleType("qgis.PyQt.QtGui")
    qgis_pyt_gui.QColor = MagicMock(return_value=MagicMock())
    qgis_pyt_gui.QFont = MagicMock(return_value=MagicMock())

    qgis_mod = ModuleType("qgis")
    qgis_mod.core = qgis_core

    sys.modules["qgis"] = qgis_mod
    sys.modules["qgis.core"] = qgis_core
    sys.modules["qgis.PyQt"] = qgis_pyt
    sys.modules["qgis.PyQt.QtCore"] = qgis_pyt_core
    sys.modules["qgis.PyQt.QtGui"] = qgis_pyt_gui
    return qgis_core


def _import_resolver_module():
    _make_qgis_stub()
    for name in ["qfit.atlas.profile_payload_resolver", "qfit.atlas.profile_item"]:
        sys.modules.pop(name, None)
    return importlib.import_module("qfit.atlas.profile_payload_resolver")


def _cleanup_import_state():
    for name in [
        "qfit.atlas.profile_item",
        "qfit.atlas.profile_payload_resolver",
    ]:
        sys.modules.pop(name, None)

    export_task_tests = sys.modules.get("tests.test_atlas_export_task")
    if export_task_tests is not None and hasattr(export_task_tests, "_qgis_core"):
        qgis_mod = sys.modules.get("qgis")
        if qgis_mod is not None:
            qgis_mod.core = export_task_tests._qgis_core
        sys.modules["qgis.core"] = export_task_tests._qgis_core


class TestPageProfilePayloadResolver(unittest.TestCase):
    def tearDown(self):
        _cleanup_import_state()

    def test_build_page_profile_payload_collects_native_inputs(self):
        profile_payload_resolver = _import_resolver_module()
        feat = MagicMock(name="feature")
        feat.geometry.return_value = "feature-geometry"

        payload = profile_payload_resolver.build_page_profile_payload(feat, [])

        self.assertEqual(payload.feature_geometry, "feature-geometry")
        self.assertIs(payload.feature, feat)

        with patch.object(
            profile_payload_resolver,
            "build_native_profile_curve_from_feature",
            return_value="curve",
        ) as build_native_curve:
            native_curve, native_request = payload.native_inputs()

        self.assertEqual(native_curve, "curve")
        self.assertIsNone(native_request)
        build_native_curve.assert_called_once_with(
            "feature-geometry",
            feature=feat,
            altitudes=[],
        )

    def test_prefers_filtered_activity_line_geometry(self):
        profile_payload_resolver = _import_resolver_module()
        atlas_feature = MagicMock(name="atlas_feature")
        atlas_feature.geometry.return_value = "atlas-polygon"

        point_feature = MagicMock(name="point_feature")
        point_feature.geometry.return_value = "point-geometry"
        point_layer = MagicMock(name="point_layer")
        point_layer.getFeatures.side_effect = lambda: iter([point_feature])

        line_feature = MagicMock(name="line_feature")
        line_feature.geometry.return_value = "line-geometry"
        line_layer = MagicMock(name="line_layer")
        line_layer.getFeatures.side_effect = lambda: iter([line_feature])

        with patch.object(
            profile_payload_resolver,
            "build_native_profile_curve",
            side_effect=lambda geometry: "curve" if geometry == "line-geometry" else None,
        ):
            payload = profile_payload_resolver.build_page_profile_payload(
                atlas_feature,
                [(point_layer, ""), (line_layer, "")],
            )

        self.assertEqual(payload.feature_geometry, "line-geometry")

    def test_uses_profile_sample_lookup_for_source_activity(self):
        profile_payload_resolver = _import_resolver_module()
        feat = MagicMock(name="feature")
        feat.geometry.return_value = "feature-geometry"
        feat.attribute.side_effect = lambda name: "activity-42" if name == "source_activity_id" else None

        lookup = MagicMock(return_value=[(0.0, 450.0), (1000.0, 530.0)])

        payload = profile_payload_resolver.build_page_profile_payload(
            feat,
            [],
            profile_altitude_lookup=lookup,
        )

        self.assertEqual(payload.page_points, [(0.0, 450.0), (1000.0, 530.0)])
        lookup.assert_called_once_with("activity-42")

    def test_falls_back_to_details_json_from_filtered_layer(self):
        profile_payload_resolver = _import_resolver_module()
        atlas_feature = MagicMock(name="atlas_feature")
        atlas_feature.geometry.return_value = "atlas-z-line"
        atlas_feature.attribute.side_effect = lambda name: {
            "source_activity_id": "activity-42",
            "details_json": None,
        }.get(name)

        filtered_feature = MagicMock(name="filtered_feature")
        filtered_feature.geometry.return_value = "line-geometry"
        filtered_feature.attribute.side_effect = lambda name: {
            "source_activity_id": "activity-42",
            "details_json": json.dumps(
                {
                    "stream_metrics": {
                        "distance": [0, 1000],
                        "altitude": [450, 530],
                    }
                }
            ),
        }.get(name)
        filtered_layer = MagicMock(name="filtered_layer")
        filtered_layer.getFeatures.side_effect = lambda: iter([filtered_feature])

        with patch.object(
            profile_payload_resolver,
            "build_native_profile_curve",
            side_effect=lambda geometry: "curve" if geometry == "atlas-z-line" else None,
        ):
            payload = profile_payload_resolver.build_page_profile_payload(
                atlas_feature,
                [(filtered_layer, "")],
            )

        self.assertEqual(payload.page_points, [(0.0, 450.0), (1000.0, 530.0)])
        self.assertEqual(payload.feature_geometry, "atlas-z-line")
        self.assertIs(payload.feature, atlas_feature)

    def test_layer_fallback_ignores_other_activity_ids(self):
        profile_payload_resolver = _import_resolver_module()
        atlas_feature = MagicMock(name="atlas_feature")
        atlas_feature.geometry.return_value = "atlas-z-line"
        atlas_feature.attribute.side_effect = lambda name: {
            "source_activity_id": "activity-42",
            "details_json": None,
        }.get(name)

        wrong_feature = MagicMock(name="wrong_feature")
        wrong_feature.geometry.return_value = "line-geometry"
        wrong_feature.attribute.side_effect = lambda name: {
            "source_activity_id": "activity-99",
            "details_json": json.dumps(
                {
                    "stream_metrics": {
                        "distance": [0, 1000],
                        "altitude": [999, 1001],
                    }
                }
            ),
        }.get(name)
        filtered_layer = MagicMock(name="filtered_layer")
        filtered_layer.getFeatures.side_effect = lambda: iter([wrong_feature])

        with patch.object(
            profile_payload_resolver,
            "build_native_profile_curve",
            side_effect=lambda geometry: "curve" if geometry == "atlas-z-line" else None,
        ):
            payload = profile_payload_resolver.build_page_profile_payload(
                atlas_feature,
                [(filtered_layer, "")],
            )

        self.assertIsNone(payload.page_points)


class TestAtlasProfileSampleLookup(unittest.TestCase):
    def tearDown(self):
        _cleanup_import_state()

    def test_reads_ordered_altitudes_from_gpkg(self):
        profile_payload_resolver = _import_resolver_module()
        with tempfile.TemporaryDirectory() as tmp_dir:
            gpkg_path = os.path.join(tmp_dir, "profile-samples.gpkg")
            with sqlite3.connect(gpkg_path) as conn:
                conn.execute(
                    """
                    CREATE TABLE atlas_profile_samples (
                        source_activity_id TEXT,
                        profile_point_index INTEGER,
                        distance_m REAL,
                        altitude_m REAL
                    )
                    """
                )
                conn.executemany(
                    "INSERT INTO atlas_profile_samples VALUES (?, ?, ?, ?)",
                    [
                        ("activity-1", 2, 2000.0, 530.0),
                        ("activity-1", 0, 0.0, 450.0),
                        ("activity-1", 1, 1000.0, 490.0),
                    ],
                )

            atlas_layer = MagicMock(name="atlas_layer")
            atlas_layer.source.return_value = f"{gpkg_path}|layername=activity_atlas_pages"

            lookup = profile_payload_resolver.AtlasProfileSampleLookup(atlas_layer)

            self.assertEqual(
                lookup.lookup("activity-1"),
                [(0.0, 450.0), (1000.0, 490.0), (2000.0, 530.0)],
            )
            self.assertIsNone(lookup.lookup("missing"))


if __name__ == "__main__":
    unittest.main()
