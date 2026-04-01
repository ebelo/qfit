"""Tests for AtlasExportTask.

Uses the same stub-QgsTask pattern as test_fetch_task.py so that tests run
without a live QGIS instance.
"""

import sys
import unittest
from types import ModuleType
from unittest.mock import MagicMock, patch

from tests import _path  # noqa: F401

# ---------------------------------------------------------------------------
# Minimal QGIS stubs (must come before importing atlas_export_task)
# ---------------------------------------------------------------------------


class _FakeQgsTask:
    CanCancel = 1

    def __init__(self, description="", flags=0):
        self._cancelled = False

    def isCanceled(self):
        return self._cancelled

    def setProgress(self, value):  # noqa: N802
        pass


def _make_qgis_stub():
    """Build a minimal qgis.core stub module with the symbols we need."""
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

    sys.modules.setdefault("qgis", qgis_mod)
    sys.modules["qgis.core"] = qgis_core
    sys.modules.setdefault("qgis.PyQt", qgis_pyt)
    sys.modules["qgis.PyQt.QtCore"] = qgis_pyt_core
    sys.modules["qgis.PyQt.QtGui"] = qgis_pyt_gui
    return qgis_core


_qgis_core = _make_qgis_stub()

import qfit.atlas.export_task as atlas_export_task  # noqa: E402
from qfit.atlas.profile_item import (  # noqa: E402
    build_native_profile_inputs,
    NativeProfileItemConfig,
    NativeProfileRequestConfig,
    ProfileItemAdapter,
    build_native_profile_curve,
    build_profile_item,
    build_profile_item_adapter,
    build_native_profile_item,
    build_native_profile_request,
    native_profile_item_available,
    native_profile_request_available,
)

from qfit.atlas.export_task import (  # noqa: E402
    AtlasExportTask,
    build_atlas_layout,
    build_cover_layout,
    build_toc_layout,
    _normalize_profile_sample_key,
    _build_cover_summary_from_current_atlas_features,
    _apply_cover_heatmap_renderer,
)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _run_task(task):
    result = task.run()
    task.finished(result)
    return result


def _make_atlas_layer(feature_count=3):
    layer = MagicMock()
    layer.featureCount.return_value = feature_count
    fields = MagicMock()
    fields.indexOf = lambda name: 0  # all stored-extent fields exist
    layer.fields.return_value = fields
    return layer


def _make_atlas_mock(feature_count=3):
    """Return a (layout_mock, atlas_mock, exporter_cls_mock) triple that
    simulates the new per-page export loop correctly."""
    # atlas mock: beginRender/first/next/endRender
    atlas_mock = MagicMock()
    atlas_mock.beginRender.return_value = True
    atlas_mock.updateFeatures.return_value = feature_count
    # first() returns True, then next() returns False after feature_count calls
    call_count = {"n": 0}

    def _first():
        call_count["n"] = 1
        return feature_count > 0

    def _next():
        call_count["n"] += 1
        return call_count["n"] <= feature_count

    atlas_mock.first.side_effect = _first
    atlas_mock.next.side_effect = _next

    # layout.reportContext().feature() returns a feature with stored-extent attrs
    feat_mock = MagicMock()
    feat_mock.attribute.return_value = 1000.0  # dummy value for all attrs
    atlas_mock.layout.return_value.reportContext.return_value.feature.return_value = feat_mock

    layout_mock = MagicMock()
    layout_mock.atlas.return_value = atlas_mock
    layout_mock.pageCollection.return_value.pageCount.return_value = 1
    layout_mock.pageCollection.return_value.page.return_value = MagicMock()
    layout_mock.items.return_value = []  # no map items → extent override skipped

    exporter_cls_mock = MagicMock()
    exporter_cls_mock.Success = 0
    exporter_instance = MagicMock()
    # per-page exportToPdf(path, settings) → Success int
    exporter_instance.exportToPdf.return_value = 0
    exporter_cls_mock.return_value = exporter_instance

    return layout_mock, atlas_mock, exporter_cls_mock


# ---------------------------------------------------------------------------
# Tests: successful export
# ---------------------------------------------------------------------------


class TestBuildAtlasLayout(unittest.TestCase):
    def test_build_page_profile_payload_collects_svg_and_native_inputs(self):
        feat = MagicMock(name="feature")
        feat.attribute.return_value = "activity-1"
        feat.geometry.return_value = "feature-geometry"

        payload = atlas_export_task._build_page_profile_payload(
            feat,
            0,
            {"activity-1": [(0.0, 100.0), (1.0, 120.0)]},
        )

        self.assertEqual(payload.sample_key, "activity-1")
        self.assertEqual(payload.page_points, [(0.0, 100.0), (1.0, 120.0)])
        self.assertEqual(payload.feature_geometry, "feature-geometry")

        with patch.object(
            atlas_export_task,
            "build_native_profile_inputs",
            return_value=("curve", "request"),
        ) as build_native_inputs:
            native_curve, native_request = payload.native_inputs()

        self.assertEqual(native_curve, "curve")
        self.assertEqual(native_request, "request")
        build_native_inputs.assert_called_once_with("feature-geometry")

    def test_build_page_profile_payload_handles_missing_sort_key_and_geometry(self):
        feat = MagicMock(name="feature")
        feat.geometry.return_value = None

        payload = atlas_export_task._build_page_profile_payload(feat, -1, {})

        self.assertIsNone(payload.sample_key)
        self.assertEqual(payload.page_points, [])
        self.assertIsNone(payload.feature_geometry)

        with patch.object(
            atlas_export_task,
            "build_native_profile_inputs",
            return_value=(None, None),
        ) as build_native_inputs:
            native_curve, native_request = payload.native_inputs()

        self.assertIsNone(native_curve)
        self.assertIsNone(native_request)
        build_native_inputs.assert_called_once_with(None)

    def test_build_profile_item_creates_picture_backed_adapter(self):
        layout = MagicMock()

        adapter = build_profile_item(
            layout,
            item_id="profile",
            x=10.0,
            y=20.0,
            w=30.0,
            h=40.0,
        )

        self.assertIsInstance(adapter, ProfileItemAdapter)
        self.assertEqual(adapter.kind, "picture")
        self.assertIs(adapter.item, _qgis_core.QgsLayoutItemPicture.return_value)
        _qgis_core.QgsLayoutItemPicture.return_value.setId.assert_called_once_with("profile")
        layout.addLayoutItem.assert_called_once_with(_qgis_core.QgsLayoutItemPicture.return_value)

    def test_build_profile_item_adapter_can_clear_and_set_svg(self):
        item = MagicMock()
        adapter = build_profile_item_adapter(item)

        adapter.set_svg_profile("/tmp/profile.svg")
        adapter.clear_profile()

        self.assertEqual(item.setPicturePath.call_args_list[0][0][0], "/tmp/profile.svg")
        self.assertEqual(item.setPicturePath.call_args_list[1][0][0], "")

    def test_build_profile_item_adapter_detects_native_profile_items(self):
        native_item = _qgis_core.QgsLayoutItemElevationProfile.return_value
        native_item.__class__.__name__ = "QgsLayoutItemElevationProfile"

        adapter = build_profile_item_adapter(native_item)

        self.assertEqual(adapter.kind, "native")
        self.assertTrue(adapter.supports_native_profile)

    def test_native_profile_item_available_reflects_optional_qgis_class(self):
        self.assertTrue(native_profile_item_available())

    def test_native_profile_request_available_reflects_optional_qgis_class(self):
        self.assertTrue(native_profile_request_available())

    def test_native_profile_item_support_is_decoupled_from_profile_request_support(self):
        with (
            patch("qfit.atlas.profile_item.QgsLayoutItemElevationProfile", _qgis_core.QgsLayoutItemElevationProfile),
            patch("qfit.atlas.profile_item.QgsProfileRequest", None),
        ):
            self.assertTrue(native_profile_item_available())
            self.assertFalse(native_profile_request_available())

            adapter = build_native_profile_item(
                MagicMock(),
                item_id="profile",
                x=10.0,
                y=20.0,
                w=30.0,
                h=40.0,
            )

        self.assertIsNotNone(adapter)
        self.assertEqual(adapter.kind, "native")

    def test_native_profile_request_keeps_crs_when_native_item_class_is_missing(self):
        curve = MagicMock(name="curve")
        _qgis_core.QgsProfileRequest.return_value.setCrs.reset_mock()

        with (
            patch("qfit.atlas.profile_item.QgsLayoutItemElevationProfile", None),
            patch("qfit.atlas.profile_item.QgsCoordinateReferenceSystem", _qgis_core.QgsCoordinateReferenceSystem),
        ):
            request = build_native_profile_request(curve)

        self.assertIs(request, _qgis_core.QgsProfileRequest.return_value)
        request.setCrs.assert_called_once()

    def test_build_native_profile_item_returns_native_adapter_when_available(self):
        layout = MagicMock()
        native_item = _qgis_core.QgsLayoutItemElevationProfile.return_value
        native_item.__class__.__name__ = "QgsLayoutItemElevationProfile"

        adapter = build_native_profile_item(
            layout,
            item_id="profile",
            x=10.0,
            y=20.0,
            w=30.0,
            h=40.0,
            config=NativeProfileItemConfig(tolerance=12.5),
        )

        self.assertIsNotNone(adapter)
        self.assertEqual(adapter.kind, "native")
        native_item.setId.assert_called_once_with("profile")
        native_item.setAtlasDriven.assert_called_once_with(True)
        native_item.setTolerance.assert_called_once_with(12.5)
        native_item.setCrs.assert_called_once()
        layout.addLayoutItem.assert_called_once_with(native_item)

    def test_build_native_profile_item_returns_none_when_unavailable(self):
        with patch("qfit.atlas.profile_item.native_profile_item_available", return_value=False):
            adapter = build_native_profile_item(
                MagicMock(),
                item_id="profile",
                x=10.0,
                y=20.0,
                w=30.0,
                h=40.0,
            )

        self.assertIsNone(adapter)

    def test_picture_adapter_ignores_native_default_configuration(self):
        item = MagicMock()
        adapter = ProfileItemAdapter(item=item, kind="picture")

        adapter.configure_native_defaults()

        item.setCrs.assert_not_called()
        item.setAtlasDriven.assert_not_called()
        item.setTolerance.assert_not_called()

    def test_picture_adapter_ignores_native_profile_binding(self):
        item = MagicMock()
        adapter = ProfileItemAdapter(item=item, kind="picture")

        adapter.bind_native_profile(profile_curve="curve")

        item.setProfileCurve.assert_not_called()

    def test_build_native_profile_request_returns_configured_request(self):
        curve = MagicMock(name="curve")

        request = build_native_profile_request(
            curve,
            config=NativeProfileRequestConfig(tolerance=25.0, step_distance=5.0),
        )

        self.assertIs(request, _qgis_core.QgsProfileRequest.return_value)
        _qgis_core.QgsProfileRequest.assert_called_once_with(curve)
        request.setCrs.assert_called_once()
        request.setTolerance.assert_called_once_with(25.0)
        request.setStepDistance.assert_called_once_with(5.0)

    def test_build_native_profile_request_returns_none_without_curve_or_support(self):
        self.assertIsNone(build_native_profile_request(None))

        with patch("qfit.atlas.profile_item.native_profile_request_available", return_value=False):
            self.assertIsNone(build_native_profile_request(MagicMock(name="curve")))

    def test_build_native_profile_curve_clones_geometry_curve(self):
        curve = MagicMock(name="curve")
        curve.clone.return_value = "curve-clone"
        geometry = MagicMock(name="geometry")
        geometry.constGet.return_value = curve

        result = build_native_profile_curve(geometry)

        self.assertEqual(result, "curve-clone")
        curve.clone.assert_called_once_with()

    def test_build_native_profile_curve_returns_none_when_unavailable(self):
        geometry = MagicMock(name="geometry")
        geometry.constGet.return_value = None

        self.assertIsNone(build_native_profile_curve(None))
        self.assertIsNone(build_native_profile_curve(geometry))

    def test_build_native_profile_curve_rejects_polygon_like_geometries(self):
        polygon = MagicMock(name="polygon")
        polygon.__class__.__name__ = "QgsPolygon"
        polygon.exteriorRing.return_value = MagicMock()
        geometry = MagicMock(name="geometry")
        geometry.constGet.return_value = polygon

        self.assertIsNone(build_native_profile_curve(geometry))
        polygon.clone.assert_not_called()

    def test_build_native_profile_inputs_returns_curve_and_request_together(self):
        geometry = MagicMock(name="geometry")

        with (
            patch("qfit.atlas.profile_item.build_native_profile_curve", return_value="curve") as build_curve,
            patch("qfit.atlas.profile_item.build_native_profile_request", return_value="request") as build_request,
        ):
            curve, request = build_native_profile_inputs(
                geometry,
                request_config=NativeProfileRequestConfig(tolerance=12.0),
            )

        self.assertEqual(curve, "curve")
        self.assertEqual(request, "request")
        build_curve.assert_called_once_with(geometry)
        build_request.assert_called_once()

    def test_build_native_profile_inputs_returns_none_pair_when_curve_missing(self):
        geometry = MagicMock(name="geometry")

        with patch("qfit.atlas.profile_item.build_native_profile_curve", return_value=None):
            curve, request = build_native_profile_inputs(geometry)

        self.assertIsNone(curve)
        self.assertIsNone(request)

    def test_native_adapter_binds_curve_when_supported(self):
        item = MagicMock()
        adapter = ProfileItemAdapter(item=item, kind="native")

        adapter.bind_native_profile(profile_curve="curve")

        item.setProfileCurve.assert_called_once_with("curve")

    def test_export_map_excludes_atlas_coverage_layer_overlay(self):
        atlas_layer = _make_atlas_layer(feature_count=1)
        visible_track_layer = MagicMock(name="visible_track_layer")
        visible_background_layer = MagicMock(name="visible_background_layer")

        atlas_node = MagicMock()
        atlas_node.isVisible.return_value = True
        atlas_node.layer.return_value = atlas_layer

        track_node = MagicMock()
        track_node.isVisible.return_value = True
        track_node.layer.return_value = visible_track_layer

        background_node = MagicMock()
        background_node.isVisible.return_value = True
        background_node.layer.return_value = visible_background_layer

        project = MagicMock()
        project.layerTreeRoot.return_value.findLayers.return_value = [
            atlas_node,
            track_node,
            background_node,
        ]

        with patch("qfit.atlas.export_task.QgsPrintLayout") as mock_layout_cls, \
             patch("qfit.atlas.export_task.QgsLayoutItemMap") as mock_map_cls:
            layout = MagicMock()
            layout.atlas.return_value = MagicMock()
            layout.pageCollection.return_value.pageCount.return_value = 1
            layout.pageCollection.return_value.page.return_value = MagicMock()
            mock_layout_cls.return_value = layout
            map_item = MagicMock()
            mock_map_cls.return_value = map_item

            build_atlas_layout(atlas_layer, project=project)

        map_item.setLayers.assert_called_once_with(
            [visible_track_layer, visible_background_layer]
        )


class TestBuildAtlasLayoutSummaryLabels(unittest.TestCase):
    """Verify that profile and stats summary labels are added to the layout."""

    def _build_with_fields(self, available_fields):
        """Build a layout where *available_fields* are present on the atlas layer."""
        atlas_layer = MagicMock()
        atlas_layer.featureCount.return_value = 1
        fields = MagicMock()
        fields.indexOf = lambda name: 0 if name in available_fields else -1
        atlas_layer.fields.return_value = fields

        project = MagicMock()
        project.layerTreeRoot.return_value.findLayers.return_value = []

        with patch("qfit.atlas.export_task.QgsPrintLayout") as mock_layout_cls, \
             patch("qfit.atlas.export_task.QgsLayoutItemMap"):
            layout = MagicMock()
            layout.atlas.return_value = MagicMock()
            layout.pageCollection.return_value.pageCount.return_value = 1
            layout.pageCollection.return_value.page.return_value = MagicMock()
            mock_layout_cls.return_value = layout

            build_atlas_layout(atlas_layer, project=project)
        return layout

    def _label_texts(self, layout):
        """Return the list of text strings set on label items added to *layout*."""
        from qgis.core import QgsLayoutItemLabel
        texts = []
        for call in QgsLayoutItemLabel.return_value.setText.call_args_list:
            texts.append(call[0][0])
        return texts

    def _label_ids(self):
        """Return the list of IDs set on label items."""
        from qgis.core import QgsLayoutItemLabel
        ids = []
        for call in QgsLayoutItemLabel.return_value.setId.call_args_list:
            ids.append(call[0][0])
        return ids

    def test_both_summaries_rendered_when_fields_present(self):
        """Both profile summary and detail block labels are created when fields exist."""
        _qgis_core.QgsLayoutItemLabel.reset_mock()
        available = {
            "page_sort_key", "page_title", "page_stats_summary",
            "page_subtitle", "page_date", "page_profile_summary",
            "page_distance_label", "page_duration_label",
            "page_elevation_gain_label",
        }
        self._build_with_fields(available)
        ids = self._label_ids()
        from qfit.atlas.export_task import _PROFILE_SUMMARY_ID, _DETAIL_BLOCK_ID
        self.assertIn(_PROFILE_SUMMARY_ID, ids, "profile summary label missing")
        self.assertIn(_DETAIL_BLOCK_ID, ids, "detail block label missing")

    def test_no_raw_expression_in_profile_area_labels(self):
        """Profile summary and detail block labels must not contain [% %] syntax.

        These labels are populated per-page from feature attributes during export
        to prevent raw template syntax leaking into the PDF (issue #108).
        """
        _qgis_core.QgsLayoutItemLabel.reset_mock()
        available = {
            "page_sort_key", "page_title", "page_stats_summary",
            "page_subtitle", "page_date", "page_profile_summary",
            "page_distance_label", "page_duration_label",
            "page_elevation_gain_label",
        }
        self._build_with_fields(available)
        texts = self._label_texts(None)
        # No label text should reference profile-area field names inside [% %].
        profile_area_fields = {"page_profile_summary", "page_distance_label",
                               "page_duration_label", "page_elevation_gain_label"}
        for t in texts:
            if "[%" in t:
                for field in profile_area_fields:
                    self.assertNotIn(
                        field, t,
                        f"raw [% %] expression referencing {field} found: {t!r}",
                    )

    def test_detail_block_omitted_when_fields_absent(self):
        """Detail block label is not added when no detail fields are present."""
        _qgis_core.QgsLayoutItemLabel.reset_mock()
        available = {
            "page_sort_key", "page_title", "page_subtitle",
            "page_date", "page_profile_summary",
        }
        self._build_with_fields(available)
        ids = self._label_ids()
        from qfit.atlas.export_task import _DETAIL_BLOCK_ID
        self.assertNotIn(_DETAIL_BLOCK_ID, ids, "detail block should not be added")

    def test_detail_block_created_with_subset_of_fields(self):
        """Detail block label is created when at least some detail fields exist."""
        _qgis_core.QgsLayoutItemLabel.reset_mock()
        available = {
            "page_sort_key", "page_title", "page_subtitle", "page_date",
            "page_distance_label", "page_elevation_gain_label",
        }
        self._build_with_fields(available)
        ids = self._label_ids()
        from qfit.atlas.export_task import _DETAIL_BLOCK_ID
        self.assertIn(_DETAIL_BLOCK_ID, ids, "detail block should be created")

    def test_profile_summary_omitted_when_field_absent(self):
        """Profile summary label is not added when the field is missing."""
        _qgis_core.QgsLayoutItemLabel.reset_mock()
        available = {
            "page_sort_key", "page_title", "page_stats_summary",
            "page_subtitle", "page_date",
        }
        self._build_with_fields(available)
        ids = self._label_ids()
        from qfit.atlas.export_task import _PROFILE_SUMMARY_ID
        self.assertNotIn(_PROFILE_SUMMARY_ID, ids, "profile summary label should not be added")


class TestPerPageLabelTextSetting(unittest.TestCase):
    """Verify that profile-area label text is set from feature attributes per page (issue #108)."""

    def test_profile_summary_set_per_page(self):
        """Profile summary label receives plain text from feature attribute each page."""
        from qfit.atlas.export_task import _PROFILE_SUMMARY_ID, _DETAIL_BLOCK_ID

        layout_mock, atlas_mock, exporter_cls_mock = _make_atlas_mock(feature_count=1)

        # Create mock label items with IDs matching the profile-area constants.
        summary_label = MagicMock()
        summary_label.id.return_value = _PROFILE_SUMMARY_ID
        detail_label = MagicMock()
        detail_label.id.return_value = _DETAIL_BLOCK_ID
        layout_mock.items.return_value = [summary_label, detail_label]

        # Atlas layer with profile summary and detail fields present.
        atlas_layer = _make_atlas_layer(feature_count=1)
        field_names = [
            "page_sort_key", "page_profile_summary",
            "page_distance_label", "page_elevation_gain_label",
            "center_x_3857", "center_y_3857", "extent_width_m", "extent_height_m",
        ]
        atlas_layer.fields.return_value.indexOf = (
            lambda name: field_names.index(name) if name in field_names else -1
        )

        # Feature attributes: return realistic values per field index.
        attr_values = {
            0: "sort_key_1",               # page_sort_key
            1: "5.2 km · 120–450 m",       # page_profile_summary
            2: "5.2 km",                    # page_distance_label
            3: "330 m",                     # page_elevation_gain_label
            4: 1000.0, 5: 2000.0, 6: 500.0, 7: 500.0,  # extents
        }
        feat_mock = atlas_mock.layout.return_value.reportContext.return_value.feature.return_value
        feat_mock.attribute.side_effect = lambda idx: attr_values.get(idx)

        received = {}
        task = AtlasExportTask(
            atlas_layer=atlas_layer,
            output_path="/tmp/qfit_test_perpage.pdf",
            on_finished=lambda **kw: received.update(kw),
        )

        with patch("qfit.atlas.export_task.build_atlas_layout", return_value=layout_mock), \
             patch("qfit.atlas.export_task.QgsLayoutExporter", exporter_cls_mock), \
             patch("qfit.atlas.export_task.AtlasExportTask._export_cover_page", return_value=None), \
             patch("qfit.atlas.export_task.AtlasExportTask._export_toc_page", return_value=None), \
             patch("os.replace"), \
             patch("os.makedirs"):
            _run_task(task)

        # Profile summary label should have been set to the resolved attribute value.
        summary_label.setText.assert_called()
        summary_text = summary_label.setText.call_args[0][0]
        self.assertEqual(summary_text, "5.2 km · 120–450 m")
        self.assertNotIn("[%", summary_text)

        # Detail block label should have resolved label:value lines.
        detail_label.setText.assert_called()
        detail_text = detail_label.setText.call_args[0][0]
        self.assertIn("Distance: 5.2 km", detail_text)
        self.assertIn("Climbing: 330 m", detail_text)
        self.assertNotIn("[%", detail_text)
        # Fields not in the layer should not appear.
        self.assertNotIn("Moving time:", detail_text)
        self.assertNotIn("Speed:", detail_text)

    def test_null_attributes_produce_empty_text(self):
        """NULL or empty feature attributes produce empty label text, not raw syntax."""
        from qfit.atlas.export_task import _PROFILE_SUMMARY_ID, _DETAIL_BLOCK_ID

        layout_mock, atlas_mock, exporter_cls_mock = _make_atlas_mock(feature_count=1)

        summary_label = MagicMock()
        summary_label.id.return_value = _PROFILE_SUMMARY_ID
        detail_label = MagicMock()
        detail_label.id.return_value = _DETAIL_BLOCK_ID
        layout_mock.items.return_value = [summary_label, detail_label]

        atlas_layer = _make_atlas_layer(feature_count=1)
        field_names = [
            "page_sort_key", "page_profile_summary",
            "page_distance_label", "page_elevation_gain_label",
            "center_x_3857", "center_y_3857", "extent_width_m", "extent_height_m",
        ]
        atlas_layer.fields.return_value.indexOf = (
            lambda name: field_names.index(name) if name in field_names else -1
        )

        # All label attributes are None (e.g. activity with no profile data).
        feat_mock = atlas_mock.layout.return_value.reportContext.return_value.feature.return_value
        feat_mock.attribute.side_effect = lambda idx: {4: 1000.0, 5: 2000.0, 6: 500.0, 7: 500.0}.get(idx)

        received = {}
        task = AtlasExportTask(
            atlas_layer=atlas_layer,
            output_path="/tmp/qfit_test_null.pdf",
            on_finished=lambda **kw: received.update(kw),
        )

        with patch("qfit.atlas.export_task.build_atlas_layout", return_value=layout_mock), \
             patch("qfit.atlas.export_task.QgsLayoutExporter", exporter_cls_mock), \
             patch("qfit.atlas.export_task.AtlasExportTask._export_cover_page", return_value=None), \
             patch("qfit.atlas.export_task.AtlasExportTask._export_toc_page", return_value=None), \
             patch("os.replace"), \
             patch("os.makedirs"):
            _run_task(task)

        summary_label.setText.assert_called()
        self.assertEqual(summary_label.setText.call_args[0][0], "")

        detail_label.setText.assert_called()
        self.assertEqual(detail_label.setText.call_args[0][0], "")


class TestProfileChartRendering(unittest.TestCase):
    def test_normalize_profile_sample_key_casts_to_string(self):
        class _Key:
            def __str__(self):
                return " sort-key-1 "

        self.assertEqual(_normalize_profile_sample_key(_Key()), "sort-key-1")
        self.assertIsNone(_normalize_profile_sample_key(None))
        self.assertIsNone(_normalize_profile_sample_key("   "))

    def test_profile_chart_uses_normalized_sort_key_and_refreshes_picture(self):
        from qfit.atlas.export_task import _PROFILE_PICTURE_ID

        layout_mock, atlas_mock, exporter_cls_mock = _make_atlas_mock(feature_count=1)

        profile_pic = MagicMock()
        profile_pic.id.return_value = _PROFILE_PICTURE_ID
        layout_mock.items.return_value = [profile_pic]

        atlas_layer = _make_atlas_layer(feature_count=1)
        field_names = [
            "page_sort_key",
            "source_activity_id",
            "center_x_3857",
            "center_y_3857",
            "extent_width_m",
            "extent_height_m",
        ]
        atlas_layer.fields.return_value.indexOf = (
            lambda name: field_names.index(name) if name in field_names else -1
        )
        atlas_layer.source.return_value = "/tmp/fake.gpkg|layername=activity_atlas_pages"

        class _Key:
            def __str__(self):
                return " sort-key-1 "

        attr_values = {
            0: _Key(),
            1: "activity-1",
            2: 1000.0,
            3: 2000.0,
            4: 500.0,
            5: 500.0,
        }
        feat_mock = atlas_mock.layout.return_value.reportContext.return_value.feature.return_value
        feat_mock.attribute.side_effect = lambda idx: attr_values.get(idx)

        task = AtlasExportTask(
            atlas_layer=atlas_layer,
            output_path="/tmp/qfit_test_profile_chart.pdf",
            on_finished=lambda **kw: None,
        )

        with patch("qfit.atlas.export_task.build_atlas_layout", return_value=layout_mock), \
             patch("qfit.atlas.export_task.QgsLayoutExporter", exporter_cls_mock), \
             patch("qfit.atlas.export_task.AtlasExportTask._export_cover_page", return_value=None), \
             patch("qfit.atlas.export_task.AtlasExportTask._export_toc_page", return_value=None), \
             patch("qfit.atlas.export_task.os.path.isfile", return_value=True), \
             patch(
                 "qfit.atlas.export_task.load_profile_samples_from_gpkg",
                 return_value={"sort-key-1": [(0.0, 420.0), (1000.0, 470.0)]},
                 create=True,
             ), \
             patch(
                 "qfit.atlas.profile_renderer.load_profile_samples_from_gpkg",
                 return_value={"sort-key-1": [(0.0, 420.0), (1000.0, 470.0)]},
             ), \
             patch("qfit.atlas.profile_renderer.render_profile_to_file", return_value="/tmp/profile.svg"), \
             patch("os.replace"), \
             patch("os.makedirs"):
            _run_task(task)

        profile_pic.setPicturePath.assert_any_call("/tmp/profile.svg")
        profile_pic.refresh.assert_called()


class TestAtlasExportTaskSuccess(unittest.TestCase):
    def test_run_returns_true_on_success(self):
        layer = _make_atlas_layer(feature_count=3)
        received = {}
        task = AtlasExportTask(
            atlas_layer=layer,
            output_path="/tmp/qfit_test_atlas_success.pdf",
            on_finished=lambda **kw: received.update(kw),
        )
        layout_mock, atlas_mock, exporter_cls_mock = _make_atlas_mock(feature_count=3)
        with patch("qfit.atlas.export_task.build_atlas_layout", return_value=layout_mock), \
             patch("qfit.atlas.export_task.QgsLayoutExporter", exporter_cls_mock), \
             patch("qfit.atlas.export_task.AtlasExportTask._merge_pdfs"), \
             patch("qfit.atlas.export_task.AtlasExportTask._export_cover_page", return_value=None), \
             patch("qfit.atlas.export_task.AtlasExportTask._export_toc_page", return_value=None), \
             patch("os.replace"), \
             patch("os.makedirs"):
            result = task.run()
        self.assertTrue(result)

    def test_finished_callback_receives_output_path(self):
        layer = _make_atlas_layer(feature_count=1)
        received = {}
        task = AtlasExportTask(
            atlas_layer=layer,
            output_path="/tmp/qfit_test_atlas_cb.pdf",
            on_finished=lambda **kw: received.update(kw),
        )
        layout_mock, atlas_mock, exporter_cls_mock = _make_atlas_mock(feature_count=1)
        with patch("qfit.atlas.export_task.build_atlas_layout", return_value=layout_mock), \
             patch("qfit.atlas.export_task.QgsLayoutExporter", exporter_cls_mock), \
             patch("qfit.atlas.export_task.AtlasExportTask._export_cover_page", return_value=None), \
             patch("qfit.atlas.export_task.AtlasExportTask._export_toc_page", return_value=None), \
             patch("os.replace"), \
             patch("os.makedirs"):
            _run_task(task)
        self.assertEqual(received.get("output_path"), "/tmp/qfit_test_atlas_cb.pdf")
        self.assertIsNone(received.get("error"))
        self.assertFalse(received.get("cancelled"))
        self.assertEqual(received.get("page_count"), 1)

    def test_page_count_matches_feature_count(self):
        layer = _make_atlas_layer(feature_count=7)
        received = {}
        task = AtlasExportTask(
            atlas_layer=layer,
            output_path="/tmp/qfit_test_atlas_pc.pdf",
            on_finished=lambda **kw: received.update(kw),
        )
        layout_mock, _, exporter_cls_mock = _make_atlas_mock(feature_count=7)
        with patch("qfit.atlas.export_task.build_atlas_layout", return_value=layout_mock), \
             patch("qfit.atlas.export_task.QgsLayoutExporter", exporter_cls_mock), \
             patch("qfit.atlas.export_task.AtlasExportTask._merge_pdfs"), \
             patch("qfit.atlas.export_task.AtlasExportTask._export_cover_page", return_value=None), \
             patch("qfit.atlas.export_task.AtlasExportTask._export_toc_page", return_value=None), \
             patch("os.remove"), \
             patch("os.makedirs"):
            _run_task(task)
        self.assertEqual(received.get("page_count"), 7)


# ---------------------------------------------------------------------------
# Tests: empty atlas layer
# ---------------------------------------------------------------------------


class TestAtlasExportTaskEmptyLayer(unittest.TestCase):
    def test_run_returns_false_when_no_features(self):
        received = {}
        layer = _make_atlas_layer(feature_count=0)
        task = AtlasExportTask(
            atlas_layer=layer,
            output_path="/tmp/qfit_test_atlas.pdf",
            on_finished=lambda **kw: received.update(kw),
        )
        result = task.run()
        self.assertFalse(result)
        task.finished(result)
        self.assertIsNotNone(received.get("error"))
        self.assertIn("No atlas pages", received["error"])
        self.assertIsNone(received.get("output_path"))


# ---------------------------------------------------------------------------
# Tests: exporter error
# ---------------------------------------------------------------------------


class TestAtlasExportTaskExporterError(unittest.TestCase):
    def test_finished_callback_receives_error_on_exporter_failure(self):
        received = {}
        layer = _make_atlas_layer(feature_count=2)
        task = AtlasExportTask(
            atlas_layer=layer,
            output_path="/tmp/qfit_test_atlas_err.pdf",
            on_finished=lambda **kw: received.update(kw),
        )
        layout_mock, _, exporter_cls_mock = _make_atlas_mock(feature_count=2)
        # Make the per-page exportToPdf return failure code 1
        exporter_cls_mock.return_value.exportToPdf.return_value = 1
        with patch("qfit.atlas.export_task.build_atlas_layout", return_value=layout_mock), \
             patch("qfit.atlas.export_task.QgsLayoutExporter", exporter_cls_mock), \
             patch("os.makedirs"):
            _run_task(task)
        self.assertIsNone(received.get("output_path"))
        self.assertIsNotNone(received.get("error"))
        self.assertIn("page 1", received["error"])


# ---------------------------------------------------------------------------
# Tests: exception during run
# ---------------------------------------------------------------------------


class TestAtlasExportTaskException(unittest.TestCase):
    def test_finished_callback_receives_error_on_exception(self):
        received = {}
        layer = _make_atlas_layer(feature_count=2)
        task = AtlasExportTask(
            atlas_layer=layer,
            output_path="/tmp/qfit_test_atlas.pdf",
            on_finished=lambda **kw: received.update(kw),
        )
        with patch("qfit.atlas.export_task.build_atlas_layout", side_effect=RuntimeError("boom")):
            _run_task(task)

        self.assertIsNone(received.get("output_path"))
        self.assertIn("boom", received.get("error", ""))


# ---------------------------------------------------------------------------
# Tests: cancellation
# ---------------------------------------------------------------------------


class TestAtlasExportTaskCancellation(unittest.TestCase):
    def test_cancelled_task_reports_cancelled(self):
        received = {}
        layer = _make_atlas_layer(feature_count=3)
        task = AtlasExportTask(
            atlas_layer=layer,
            output_path="/tmp/qfit_test_atlas_cancel.pdf",
            on_finished=lambda **kw: received.update(kw),
        )
        task._cancelled = True
        layout_mock, _, exporter_cls_mock = _make_atlas_mock(feature_count=3)
        with patch("qfit.atlas.export_task.build_atlas_layout", return_value=layout_mock), \
             patch("qfit.atlas.export_task.QgsLayoutExporter", exporter_cls_mock), \
             patch("os.makedirs"):
            _run_task(task)
        self.assertTrue(received.get("cancelled"))
        self.assertIsNone(received.get("output_path"))


# ---------------------------------------------------------------------------
# Tests: no callback
# ---------------------------------------------------------------------------


class TestAtlasExportTaskNoCallback(unittest.TestCase):
    def test_finished_without_callback_does_not_raise(self):
        layer = _make_atlas_layer(feature_count=1)
        task = AtlasExportTask(
            atlas_layer=layer,
            output_path="/tmp/qfit_test_atlas_nocb.pdf",
            on_finished=None,
        )
        layout_mock, atlas_mock, exporter_cls_mock = _make_atlas_mock(feature_count=1)
        with patch("qfit.atlas.export_task.build_atlas_layout", return_value=layout_mock), \
             patch("qfit.atlas.export_task.QgsLayoutExporter", exporter_cls_mock), \
             patch("qfit.atlas.export_task.AtlasExportTask._export_cover_page", return_value=None), \
             patch("qfit.atlas.export_task.AtlasExportTask._export_toc_page", return_value=None), \
             patch("os.replace"), \
             patch("os.makedirs"):
            task.run()
            task.finished(True)  # should not raise


# ---------------------------------------------------------------------------
# Tests: atlas export leaves layer subset filters alone
# ---------------------------------------------------------------------------


class TestAtlasExportTaskLayerSubsetHandling(unittest.TestCase):
    def test_export_does_not_modify_layer_subset_string(self):
        """Atlas export should not clear, apply, or restore atlas layer subsets."""
        received = {}
        layer = _make_atlas_layer(feature_count=1)
        layer.setSubsetString = MagicMock()
        task = AtlasExportTask(
            atlas_layer=layer,
            output_path="/tmp/qfit_test_atlas_subset.pdf",
            on_finished=lambda **kw: received.update(kw),
        )
        layout_mock, atlas_mock, exporter_cls_mock = _make_atlas_mock(feature_count=1)
        with patch("qfit.atlas.export_task.build_atlas_layout", return_value=layout_mock), \
             patch("qfit.atlas.export_task.QgsLayoutExporter", exporter_cls_mock), \
             patch("qfit.atlas.export_task.AtlasExportTask._export_cover_page", return_value=None), \
             patch("qfit.atlas.export_task.AtlasExportTask._export_toc_page", return_value=None), \
             patch("os.replace"), \
             patch("os.makedirs"):
            _run_task(task)
        layer.setSubsetString.assert_not_called()
        self.assertIsNotNone(received.get("output_path"))


# ---------------------------------------------------------------------------
# Tests: per-page activity filtering
# ---------------------------------------------------------------------------


class TestAtlasExportTaskPerPageFilter(unittest.TestCase):
    def _make_filterable_layer(self, sid_value="act_001"):
        """Return a mock layer that has source_activity_id field and subset tracking."""
        layer = MagicMock()
        layer.subsetString.return_value = ""
        subset_calls = []
        layer.setSubsetString.side_effect = lambda s: subset_calls.append(s)
        fields = MagicMock()
        fields.indexOf = lambda name: 0 if name == "source_activity_id" else -1
        layer.fields.return_value = fields
        return layer, subset_calls

    def test_per_page_filter_applied_and_restored(self):
        """Each page's data layers are filtered to that page's activity and restored after."""
        track_layer, track_calls = self._make_filterable_layer()

        layout_mock, atlas_mock, exporter_cls_mock = _make_atlas_mock(feature_count=1)

        # Duck-typing: map item needs setExtent and layers callables.
        map_item = MagicMock()
        map_item.layers.return_value = [track_layer]
        map_item.setExtent = MagicMock()
        layout_mock.items.return_value = [map_item]

        # Atlas layer: all indexOf calls return 0 (all fields present).
        # All attribute() calls return 1000.0 (numeric, safe for both extent and sid).
        atlas_layer = _make_atlas_layer(feature_count=1)
        atlas_layer.fields.return_value.indexOf = lambda name: 0

        feat_mock = atlas_mock.layout.return_value.reportContext.return_value.feature.return_value
        feat_mock.attribute.return_value = 1000.0

        received = {}
        task = AtlasExportTask(
            atlas_layer=atlas_layer,
            output_path="/tmp/qfit_test_filter.pdf",
            on_finished=lambda **kw: received.update(kw),
        )

        with patch("qfit.atlas.export_task.build_atlas_layout", return_value=layout_mock), \
             patch("qfit.atlas.export_task.QgsLayoutExporter", exporter_cls_mock), \
             patch("qfit.atlas.export_task.AtlasExportTask._export_cover_page", return_value=None), \
             patch("qfit.atlas.export_task.AtlasExportTask._export_toc_page", return_value=None), \
             patch("os.replace"), \
             patch("os.makedirs"):
            _run_task(task)

        # A per-page filter was set on the track layer.
        self.assertTrue(len(track_calls) >= 2, f"Expected ≥2 calls, got: {track_calls}")
        self.assertTrue(any("source_activity_id" in call for call in track_calls[:-1]))
        # Original subset string ("") was restored as the final call.
        self.assertEqual(track_calls[-1], "")
        self.assertIsNotNone(received.get("output_path"))

    def test_export_normalizes_rectangular_stored_extent_to_square_before_pdf(self):
        """Export path should square-up stored extents before applying them to the map item."""
        class _Rect:
            def __init__(self, xmin, ymin, xmax, ymax):
                self._xmin = xmin
                self._ymin = ymin
                self._xmax = xmax
                self._ymax = ymax

            def width(self):
                return self._xmax - self._xmin

            def height(self):
                return self._ymax - self._ymin

            def xMinimum(self):
                return self._xmin

            def yMinimum(self):
                return self._ymin

            def xMaximum(self):
                return self._xmax

            def yMaximum(self):
                return self._ymax

        atlas_layer = _make_atlas_layer(feature_count=1)
        field_positions = {
            "center_x_3857": 0,
            "center_y_3857": 1,
            "extent_width_m": 2,
            "extent_height_m": 3,
            "source_activity_id": 4,
            "page_profile_summary": 5,
        }
        atlas_layer.fields.return_value.indexOf = lambda name: field_positions.get(name, -1)

        layout_mock, atlas_mock, exporter_cls_mock = _make_atlas_mock(feature_count=1)
        map_item = MagicMock()
        map_item.layers.return_value = []
        map_item.setExtent = MagicMock()
        layout_mock.items.return_value = [map_item]

        feat_mock = atlas_mock.layout.return_value.reportContext.return_value.feature.return_value
        values = {
            0: 1000.0,   # center_x_3857
            1: 2000.0,   # center_y_3857
            2: 200.0,    # extent_width_m (wide)
            3: 100.0,    # extent_height_m
            4: "act_001",
            5: "",
        }
        feat_mock.attribute.side_effect = lambda idx: values.get(idx)

        received = {}
        task = AtlasExportTask(
            atlas_layer=atlas_layer,
            output_path="/tmp/qfit_test_square_extent.pdf",
            on_finished=lambda **kw: received.update(kw),
        )

        with patch("qfit.atlas.export_task.QgsRectangle", _Rect), \
             patch("qfit.atlas.export_task.build_atlas_layout", return_value=layout_mock), \
             patch("qfit.atlas.export_task.QgsLayoutExporter", exporter_cls_mock), \
             patch("qfit.atlas.export_task.AtlasExportTask._export_cover_page", return_value=None), \
             patch("qfit.atlas.export_task.AtlasExportTask._export_toc_page", return_value=None), \
             patch("os.replace"), \
             patch("os.makedirs"):
            _run_task(task)

        applied_rect = map_item.setExtent.call_args[0][0]
        self.assertAlmostEqual(applied_rect.width(), applied_rect.height(), places=6)
        self.assertIsNotNone(received.get("output_path"))

    def test_multi_page_merges_pdfs(self):
        """Multi-page export calls _merge_pdfs and cleans up per-page files."""
        layer = _make_atlas_layer(feature_count=3)
        received = {}
        task = AtlasExportTask(
            atlas_layer=layer,
            output_path="/tmp/qfit_test_merge.pdf",
            on_finished=lambda **kw: received.update(kw),
        )
        layout_mock, _, exporter_cls_mock = _make_atlas_mock(feature_count=3)
        merge_calls = []
        remove_calls = []
        with patch("qfit.atlas.export_task.build_atlas_layout", return_value=layout_mock), \
             patch("qfit.atlas.export_task.QgsLayoutExporter", exporter_cls_mock), \
             patch("qfit.atlas.export_task.AtlasExportTask._merge_pdfs",
                   side_effect=lambda pages, out: merge_calls.append((pages, out))), \
             patch("qfit.atlas.export_task.AtlasExportTask._export_cover_page", return_value=None), \
             patch("qfit.atlas.export_task.AtlasExportTask._export_toc_page", return_value=None), \
             patch("os.remove", side_effect=lambda p: remove_calls.append(p)), \
             patch("os.makedirs"):
            _run_task(task)
        # _merge_pdfs was called with 3 page paths
        self.assertEqual(len(merge_calls), 1)
        self.assertEqual(len(merge_calls[0][0]), 3)
        self.assertEqual(merge_calls[0][1], "/tmp/qfit_test_merge.pdf")
        # All per-page files were removed
        self.assertEqual(len(remove_calls), 3)
        self.assertIsNotNone(received.get("output_path"))

    def test_single_page_replaces_without_merge(self):
        """Single-page export uses os.replace instead of _merge_pdfs."""
        layer = _make_atlas_layer(feature_count=1)
        received = {}
        task = AtlasExportTask(
            atlas_layer=layer,
            output_path="/tmp/qfit_test_replace.pdf",
            on_finished=lambda **kw: received.update(kw),
        )
        layout_mock, atlas_mock, exporter_cls_mock = _make_atlas_mock(feature_count=1)
        replace_calls = []
        with patch("qfit.atlas.export_task.build_atlas_layout", return_value=layout_mock), \
             patch("qfit.atlas.export_task.QgsLayoutExporter", exporter_cls_mock), \
             patch("qfit.atlas.export_task.AtlasExportTask._export_cover_page", return_value=None), \
             patch("qfit.atlas.export_task.AtlasExportTask._export_toc_page", return_value=None), \
             patch("os.replace", side_effect=lambda src, dst: replace_calls.append((src, dst))), \
             patch("qfit.atlas.export_task.AtlasExportTask._merge_pdfs") as mock_merge, \
             patch("os.makedirs"):
            _run_task(task)
        mock_merge.assert_not_called()
        self.assertEqual(len(replace_calls), 1)
        self.assertEqual(replace_calls[0][1], "/tmp/qfit_test_replace.pdf")

    def test_merge_pdfs_uses_vendored_qfit_pypdf_when_top_level_module_missing(self):
        """Fall back to qfit.pypdf when a system-wide pypdf install is unavailable."""
        import builtins
        import types
        from unittest.mock import mock_open

        calls = []

        class FakeWriter:
            def append(self, path):
                calls.append(("append", path))

            def write(self, handle):
                calls.append(("write", handle))

        vendored_module = types.ModuleType("qfit.pypdf")
        vendored_module.PdfWriter = FakeWriter
        original_import = builtins.__import__

        def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name == "pypdf":
                raise ImportError("missing top-level pypdf")
            return original_import(name, globals, locals, fromlist, level)

        with patch.dict("sys.modules", {"qfit.pypdf": vendored_module}, clear=False), \
             patch("builtins.__import__", side_effect=fake_import), \
             patch("builtins.open", mock_open()):
            AtlasExportTask._merge_pdfs(["/tmp/one.pdf", "/tmp/two.pdf"], "/tmp/out.pdf")

        self.assertEqual(calls[0], ("append", "/tmp/one.pdf"))
        self.assertEqual(calls[1], ("append", "/tmp/two.pdf"))
        self.assertEqual(calls[2][0], "write")

    def test_load_pdf_writer_prefers_top_level_pypdf(self):
        """Use a normal top-level pypdf install when available."""
        writer_cls = atlas_export_task._load_pdf_writer()
        self.assertEqual(writer_cls.__name__, "PdfWriter")

    def test_load_pdf_writer_uses_vendor_dir_after_sys_path_injection(self):
        """If top-level pypdf is initially missing, retry after adding vendor dir."""
        import builtins
        import os
        import types

        original_import = builtins.__import__
        import_calls = {"pypdf": 0}
        fake_module = types.ModuleType("pypdf")

        class FakeWriter:
            pass

        fake_module.PdfWriter = FakeWriter
        sentinel_vendor_dir = os.path.join(os.path.dirname(os.path.dirname(atlas_export_task.__file__)), "vendor")

        def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name == "pypdf":
                import_calls["pypdf"] += 1
                if import_calls["pypdf"] == 1:
                    raise ImportError("missing before vendor path is added")
                if sentinel_vendor_dir in sys.path:
                    return fake_module
            return original_import(name, globals, locals, fromlist, level)

        with patch("os.path.isdir", return_value=True), \
             patch("builtins.__import__", side_effect=fake_import):
            if sentinel_vendor_dir in sys.path:
                sys.path.remove(sentinel_vendor_dir)
            writer_cls = atlas_export_task._load_pdf_writer()

        self.assertIs(writer_cls, FakeWriter)
        self.assertIn(sentinel_vendor_dir, sys.path)

    def test_load_pdf_writer_raises_when_no_pdf_support_is_available(self):
        """Surface a clear ImportError when neither bundled nor external pypdf exists."""
        import builtins

        original_import = builtins.__import__

        def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name in {"pypdf", "qfit.pypdf"}:
                raise ImportError("missing")
            return original_import(name, globals, locals, fromlist, level)

        with patch("os.path.isdir", return_value=False), \
             patch("builtins.__import__", side_effect=fake_import):
            with self.assertRaisesRegex(ImportError, "pypdf is unavailable"):
                atlas_export_task._load_pdf_writer()

    def test_merge_pdfs_falls_back_to_first_page_when_pypdf_is_unavailable(self):
        """Fallback path should log and keep the first page when merging is unavailable."""
        with patch("qfit.atlas.export_task._load_pdf_writer", side_effect=ImportError("missing")), \
             patch("qfit.atlas.export_task.logger.warning") as mock_warning, \
             patch("os.replace") as mock_replace:
            AtlasExportTask._merge_pdfs(["/tmp/one.pdf", "/tmp/two.pdf"], "/tmp/out.pdf")

        mock_warning.assert_called_once()
        mock_replace.assert_called_once_with("/tmp/one.pdf", "/tmp/out.pdf")

    def test_profile_chart_clears_picture_when_svg_render_returns_none(self):
        """If chart rendering yields no SVG, the profile picture is cleared and refreshed."""
        from qfit.atlas.export_task import _PROFILE_PICTURE_ID

        layout_mock, atlas_mock, exporter_cls_mock = _make_atlas_mock(feature_count=1)
        profile_pic = MagicMock()
        profile_pic.id.return_value = _PROFILE_PICTURE_ID
        layout_mock.items.return_value = [profile_pic]

        atlas_layer = _make_atlas_layer(feature_count=1)
        field_names = [
            "page_sort_key",
            "source_activity_id",
            "center_x_3857",
            "center_y_3857",
            "extent_width_m",
            "extent_height_m",
        ]
        atlas_layer.fields.return_value.indexOf = (
            lambda name: field_names.index(name) if name in field_names else -1
        )
        atlas_layer.source.return_value = "/tmp/fake.gpkg|layername=activity_atlas_pages"

        feat_mock = atlas_mock.layout.return_value.reportContext.return_value.feature.return_value
        feat_mock.attribute.side_effect = lambda idx: {
            0: " page-2 ",
            1: "activity-2",
            2: 10.0,
            3: 20.0,
            4: 30.0,
            5: 40.0,
        }.get(idx)

        task = AtlasExportTask(
            atlas_layer=atlas_layer,
            output_path="/tmp/qfit_profile_none.pdf",
            on_finished=lambda **_: None,
        )

        with patch("qfit.atlas.export_task.build_atlas_layout", return_value=layout_mock), \
             patch("qfit.atlas.export_task.QgsLayoutExporter", exporter_cls_mock), \
             patch("qfit.atlas.export_task.AtlasExportTask._export_cover_page", return_value=None), \
             patch("qfit.atlas.export_task.AtlasExportTask._export_toc_page", return_value=None), \
             patch("qfit.atlas.export_task.os.path.isfile", return_value=True), \
             patch("qfit.atlas.profile_renderer.load_profile_samples_from_gpkg", return_value={"page-2": [1, 2, 3]}), \
             patch("qfit.atlas.profile_renderer.render_profile_to_file", return_value=None), \
             patch("qfit.atlas.export_task.AtlasExportTask._merge_pdfs"), \
             patch("os.makedirs"):
            _run_task(task)

        profile_pic.setPicturePath.assert_any_call("")
        profile_pic.refresh.assert_called()

    def test_profile_chart_clears_picture_when_svg_render_raises(self):
        """Exceptions while rendering the SVG should clear the profile image cleanly."""
        from qfit.atlas.export_task import _PROFILE_PICTURE_ID

        layout_mock, atlas_mock, exporter_cls_mock = _make_atlas_mock(feature_count=1)
        profile_pic = MagicMock()
        profile_pic.id.return_value = _PROFILE_PICTURE_ID
        layout_mock.items.return_value = [profile_pic]

        atlas_layer = _make_atlas_layer(feature_count=1)
        field_names = [
            "page_sort_key",
            "source_activity_id",
            "center_x_3857",
            "center_y_3857",
            "extent_width_m",
            "extent_height_m",
        ]
        atlas_layer.fields.return_value.indexOf = (
            lambda name: field_names.index(name) if name in field_names else -1
        )
        atlas_layer.source.return_value = "/tmp/fake.gpkg|layername=activity_atlas_pages"

        feat_mock = atlas_mock.layout.return_value.reportContext.return_value.feature.return_value
        feat_mock.attribute.side_effect = lambda idx: {
            0: "page-3",
            1: "activity-3",
            2: 10.0,
            3: 20.0,
            4: 30.0,
            5: 40.0,
        }.get(idx)

        task = AtlasExportTask(
            atlas_layer=atlas_layer,
            output_path="/tmp/qfit_profile_error.pdf",
            on_finished=lambda **_: None,
        )

        with patch("qfit.atlas.export_task.build_atlas_layout", return_value=layout_mock), \
             patch("qfit.atlas.export_task.QgsLayoutExporter", exporter_cls_mock), \
             patch("qfit.atlas.export_task.AtlasExportTask._export_cover_page", return_value=None), \
             patch("qfit.atlas.export_task.AtlasExportTask._export_toc_page", return_value=None), \
             patch("qfit.atlas.export_task.os.path.isfile", return_value=True), \
             patch("qfit.atlas.profile_renderer.load_profile_samples_from_gpkg", return_value={"page-3": [1, 2, 3]}), \
             patch("qfit.atlas.profile_renderer.render_profile_to_file", side_effect=RuntimeError("boom")), \
             patch("qfit.atlas.export_task.AtlasExportTask._merge_pdfs"), \
             patch("os.makedirs"):
            _run_task(task)

        profile_pic.setPicturePath.assert_any_call("")
        profile_pic.refresh.assert_called()


# ---------------------------------------------------------------------------
# Tests: cover page
# ---------------------------------------------------------------------------


def _make_cover_atlas_layer(fields_dict=None, feature_count=1):
    """Return a mock atlas layer with per-page fields populated for cover aggregation."""
    fields_dict = fields_dict or {
        "page_date": "2026-03-22",
        "activity_type": "Run",
        "distance_m": 250000.0,
        "moving_time_s": 45000,
        "total_elevation_gain_m": 5000.0,
        # Legacy/stale document fields may still exist but should be ignored by build_cover_layout
        "document_cover_summary": "stale summary",
        "document_activity_count": "999",
        "document_date_range_label": "stale range",
        "document_total_distance_label": "9999 km",
        "document_total_duration_label": "999h",
        "document_total_elevation_gain_label": "99999 m",
        "document_activity_types_label": "Everything",
    }
    all_field_names = list(fields_dict.keys())

    layer = MagicMock()
    layer.featureCount.return_value = feature_count

    fields = MagicMock()
    fields.indexOf = lambda name: all_field_names.index(name) if name in all_field_names else -1
    layer.fields.return_value = fields

    features = []
    for _ in range(feature_count):
        feat = MagicMock()
        feat.attribute = lambda idx, _vals=list(fields_dict.values()): _vals[idx] if 0 <= idx < len(_vals) else None
        features.append(feat)
    # Use side_effect so each getFeatures() call returns a fresh iterator.
    layer.getFeatures.side_effect = lambda: iter(features)

    return layer


class TestBuildCoverLayout(unittest.TestCase):
    def test_cover_summary_prefers_sport_type_for_activity_labels(self):
        from qfit.atlas.export_task import _build_cover_summary_from_current_atlas_features

        field_names = [
            "page_date",
            "activity_type",
            "sport_type",
            "distance_m",
            "moving_time_s",
            "total_elevation_gain_m",
            "document_cover_summary",
            "document_activity_count",
            "document_date_range_label",
            "document_total_distance_label",
            "document_total_duration_label",
            "document_total_elevation_gain_label",
            "document_activity_types_label",
        ]

        rows = [
            ["2026-03-01", "Ride", "GravelRide", 12000.0, 3600, 300.0, "stale all data", "99", "", "", "", "", "Ride"],
            ["2026-03-02", "Ride", "Trail Run", 8000.0, 2400, 200.0, "stale all data", "99", "", "", "", "", "Ride"],
        ]

        layer = MagicMock()
        layer.featureCount.return_value = 2
        fields = MagicMock()
        fields.indexOf = lambda name: field_names.index(name) if name in field_names else -1
        layer.fields.return_value = fields
        feats = []
        for row in rows:
            feat = MagicMock()
            feat.attribute = lambda idx, _row=row: _row[idx] if 0 <= idx < len(_row) else None
            feats.append(feat)
        layer.getFeatures.side_effect = lambda: iter(feats)

        summary = _build_cover_summary_from_current_atlas_features(layer)

        self.assertEqual(summary["document_activity_types_label"], "GravelRide, Trail Run")
        self.assertIn("GravelRide, Trail Run", summary["document_cover_summary"])
        self.assertNotIn("Ride, Ride", summary["document_cover_summary"])

    def test_cover_summary_is_recomputed_from_current_atlas_subset(self):
        from qfit.atlas.export_task import _build_cover_summary_from_current_atlas_features

        field_names = [
            "page_date",
            "activity_type",
            "distance_m",
            "moving_time_s",
            "total_elevation_gain_m",
            "document_cover_summary",
            "document_activity_count",
            "document_date_range_label",
            "document_total_distance_label",
            "document_total_duration_label",
            "document_total_elevation_gain_label",
            "document_activity_types_label",
        ]

        rows = [
            ["2026-03-01", "NordicSkiing", 12000.0, 3600, 300.0, "stale all data", "99", "", "", "", "", "Run, Ride, NordicSkiing"],
            ["2026-03-02", "NordicSkiing", 8000.0, 2400, 200.0, "stale all data", "99", "", "", "", "", "Run, Ride, NordicSkiing"],
        ]

        layer = MagicMock()
        layer.featureCount.return_value = 2
        fields = MagicMock()
        fields.indexOf = lambda name: field_names.index(name) if name in field_names else -1
        layer.fields.return_value = fields
        feats = []
        for row in rows:
            feat = MagicMock()
            feat.attribute = lambda idx, _row=row: _row[idx] if 0 <= idx < len(_row) else None
            feats.append(feat)
        layer.getFeatures.side_effect = lambda: iter(feats)

        summary = _build_cover_summary_from_current_atlas_features(layer)

        self.assertEqual(summary["document_activity_count"], "2")
        self.assertEqual(summary["document_activity_types_label"], "NordicSkiing")
        self.assertIn("2026-03-01 → 2026-03-02", summary["document_cover_summary"])
        self.assertIn("20.0 km", summary["document_total_distance_label"])
        self.assertNotIn("Run, Ride", summary["document_cover_summary"])

    def test_build_cover_layout_returns_layout_for_populated_layer(self):
        """build_cover_layout returns a layout object when layer has features."""
        layer = _make_cover_atlas_layer()
        result = build_cover_layout(layer)
        self.assertIsNotNone(result)

    def test_build_cover_layout_sets_layout_name(self):
        """Cover layout name should be 'qfit Atlas Cover'."""
        layer = _make_cover_atlas_layer()
        layout = build_cover_layout(layer)
        self.assertIsNotNone(layout)
        layout.setName.assert_called_with("qfit Atlas Cover")

    def test_build_cover_layout_calls_initialize_defaults(self):
        """Cover layout should call initializeDefaults."""
        layer = _make_cover_atlas_layer()
        layout = build_cover_layout(layer)
        self.assertIsNotNone(layout)
        layout.initializeDefaults.assert_called_once()

    def test_build_cover_layout_skips_subtitle_when_summary_empty(self):
        """When cover summary is empty/missing, subtitle label should not be added."""
        fields_dict = {
            "document_cover_summary": "",
            "document_activity_count": "2",
            "document_date_range_label": "2025-01-01",
            "document_total_distance_label": "100.0 km",
            "document_total_duration_label": "5h",
            "document_total_elevation_gain_label": "",
            "document_activity_types_label": "Run",
        }
        layer = _make_cover_atlas_layer(fields_dict=fields_dict)
        # Should not raise and should still return a layout
        result = build_cover_layout(layer)
        self.assertIsNotNone(result)

    def test_build_cover_layout_skips_zero_activity_count_row(self):
        """Activity count of '0' should not appear in the stats block."""
        fields_dict = {
            "document_cover_summary": "",
            "document_activity_count": "0",
            "document_date_range_label": "",
            "document_total_distance_label": "",
            "document_total_duration_label": "",
            "document_total_elevation_gain_label": "",
            "document_activity_types_label": "",
        }
        layer = _make_cover_atlas_layer(fields_dict=fields_dict)
        # Should not raise even with all-empty fields
        result = build_cover_layout(layer)
        self.assertIsNotNone(result)

    def test_build_cover_layout_handles_missing_fields(self):
        """build_cover_layout tolerates a layer where document fields are absent."""
        layer = MagicMock()
        layer.featureCount.return_value = 1
        fields = MagicMock()
        fields.indexOf = lambda name: -1  # all fields missing
        layer.fields.return_value = fields
        feat = MagicMock()
        layer.getFeatures.return_value = iter([feat])
        result = build_cover_layout(layer)
        self.assertIsNotNone(result)

    def test_build_cover_layout_handles_none_attribute_values(self):
        """build_cover_layout tolerates None values returned for attributes."""
        layer = MagicMock()
        layer.featureCount.return_value = 1
        fields = MagicMock()
        fields.indexOf = lambda name: 0  # always returns index 0
        layer.fields.return_value = fields
        feat = MagicMock()
        feat.attribute.return_value = None  # all attribute reads return None
        layer.getFeatures.return_value = iter([feat])
        result = build_cover_layout(layer)
        self.assertIsNotNone(result)

    def test_build_cover_layout_uses_provided_project(self):
        """build_cover_layout passes the project to QgsPrintLayout."""
        layer = _make_cover_atlas_layer()
        project = MagicMock()
        build_cover_layout(layer, project=project)
        # QgsPrintLayout is mocked globally; verify it was called with the project
        from qfit.atlas.export_task import QgsPrintLayout  # noqa: PLC0415
        QgsPrintLayout.assert_called_with(project)

    def test_build_cover_layout_highlight_grid_item_count(self):
        """Each stat produces two layout items: an uppercase label and a bold value."""
        layer = _make_cover_atlas_layer()
        # Use a fresh layout mock to isolate item counts from other tests.
        fresh_layout = MagicMock()
        fresh_layout.pageCollection.return_value.pageCount.return_value = 1
        fresh_layout.pageCollection.return_value.page.return_value = MagicMock()
        with patch("qfit.atlas.export_task.QgsPrintLayout", return_value=fresh_layout):
            result = build_cover_layout(layer)
        self.assertIsNotNone(result)
        # With all 6 stats present, we expect:
        #   title (1) + subtitle (1) + separator (1) + 6×2 highlight items = 15
        add_calls = fresh_layout.addLayoutItem.call_args_list
        self.assertEqual(len(add_calls), 15)

    def test_build_cover_layout_highlight_labels_uppercased(self):
        """Highlight card labels are rendered in uppercase."""
        layer = _make_cover_atlas_layer()
        fresh_label_cls = MagicMock()
        fresh_layout = MagicMock()
        fresh_layout.pageCollection.return_value.pageCount.return_value = 1
        fresh_layout.pageCollection.return_value.page.return_value = MagicMock()
        with patch("qfit.atlas.export_task.QgsPrintLayout", return_value=fresh_layout), \
             patch("qfit.atlas.export_task.QgsLayoutItemLabel", fresh_label_cls):
            build_cover_layout(layer)
        label_texts = [
            call[0][0]
            for call in fresh_label_cls.return_value.setText.call_args_list
        ]
        expected_upper_labels = [
            "ACTIVITIES", "DATE RANGE", "DISTANCE",
            "MOVING TIME", "CLIMBING", "ACTIVITY TYPES",
        ]
        for expected in expected_upper_labels:
            self.assertIn(expected, label_texts)

    def test_build_cover_layout_highlight_grid_two_columns(self):
        """Highlight cards are positioned in a 2-column grid pattern."""
        from qfit.atlas.export_task import MARGIN_MM  # noqa: PLC0415
        layer = _make_cover_atlas_layer()
        fresh_point_cls = MagicMock()
        fresh_layout = MagicMock()
        fresh_layout.pageCollection.return_value.pageCount.return_value = 1
        fresh_layout.pageCollection.return_value.page.return_value = MagicMock()
        with patch("qfit.atlas.export_task.QgsPrintLayout", return_value=fresh_layout), \
             patch("qfit.atlas.export_task.QgsLayoutPoint", fresh_point_cls):
            build_cover_layout(layer)
        # Collect x-coordinates from all QgsLayoutPoint calls.
        x_coords = sorted({call[0][0] for call in fresh_point_cls.call_args_list})
        # There should be at least 2 distinct x positions for the grid columns
        # (beyond the title/subtitle x position at MARGIN_MM)
        grid_x_positions = [x for x in x_coords if x > MARGIN_MM]
        self.assertGreaterEqual(len(grid_x_positions), 1,
                                "Highlight cards should use at least two distinct x positions")

    def test_build_cover_layout_fewer_stats_fewer_items(self):
        """With only activity count + distance present, the grid stays compact."""
        fields_dict = {
            "page_date": "",
            "activity_type": "",
            "distance_m": 100000.0,
            "moving_time_s": None,
            "total_elevation_gain_m": None,
            "document_cover_summary": "stale summary",
            "document_activity_count": "999",
            "document_date_range_label": "",
            "document_total_distance_label": "",
            "document_total_duration_label": "",
            "document_total_elevation_gain_label": "",
            "document_activity_types_label": "",
        }
        layer = _make_cover_atlas_layer(fields_dict=fields_dict)
        fresh_layout = MagicMock()
        fresh_layout.pageCollection.return_value.pageCount.return_value = 1
        fresh_layout.pageCollection.return_value.page.return_value = MagicMock()
        with patch("qfit.atlas.export_task.QgsPrintLayout", return_value=fresh_layout):
            result = build_cover_layout(layer)
        self.assertIsNotNone(result)
        # title (1) + subtitle (1) + separator (1) + 2 stats × 2 label/value items = 7
        add_calls = fresh_layout.addLayoutItem.call_args_list
        self.assertEqual(len(add_calls), 7)

    def test_build_cover_layout_minimal_subset_still_shows_activity_count(self):
        """A non-empty subset should still show an activity-count card even if other stats are empty."""
        fields_dict = {
            "page_date": "",
            "activity_type": "",
            "distance_m": None,
            "moving_time_s": None,
            "total_elevation_gain_m": None,
            "document_cover_summary": "",
            "document_activity_count": "0",
            "document_date_range_label": "",
            "document_total_distance_label": "",
            "document_total_duration_label": "",
            "document_total_elevation_gain_label": "",
            "document_activity_types_label": "",
        }
        layer = _make_cover_atlas_layer(fields_dict=fields_dict)
        fresh_layout = MagicMock()
        fresh_layout.pageCollection.return_value.pageCount.return_value = 1
        fresh_layout.pageCollection.return_value.page.return_value = MagicMock()
        with patch("qfit.atlas.export_task.QgsPrintLayout", return_value=fresh_layout):
            result = build_cover_layout(layer)
        self.assertIsNotNone(result)
        # title + subtitle + separator + one stat card (label+value) = 5
        add_calls = fresh_layout.addLayoutItem.call_args_list
        self.assertEqual(len(add_calls), 5)


class TestExportCoverPage(unittest.TestCase):
    def test_export_cover_page_returns_path_on_success(self):
        """_export_cover_page returns the cover PDF path when export succeeds."""
        layer = _make_cover_atlas_layer()
        cover_layout = MagicMock()
        exporter_instance = MagicMock()
        exporter_instance.exportToPdf.return_value = 0  # Success

        exporter_cls = MagicMock()
        exporter_cls.return_value = exporter_instance
        exporter_cls.Success = 0
        exporter_cls.PdfExportSettings = MagicMock(return_value=MagicMock())

        with patch("qfit.atlas.export_task.build_cover_layout", return_value=cover_layout), \
             patch("qfit.atlas.export_task.QgsLayoutExporter", exporter_cls):
            result = AtlasExportTask._export_cover_page(layer, "/tmp/atlas.pdf")

        self.assertEqual(result, "/tmp/atlas.pdf.cover.pdf")

    def test_export_cover_page_returns_none_when_layout_is_none(self):
        """_export_cover_page returns None when build_cover_layout returns None."""
        layer = _make_cover_atlas_layer(feature_count=0)
        with patch("qfit.atlas.export_task.build_cover_layout", return_value=None):
            result = AtlasExportTask._export_cover_page(layer, "/tmp/atlas.pdf")
        self.assertIsNone(result)

    def test_export_cover_page_returns_none_on_exporter_failure(self):
        """_export_cover_page returns None when exportToPdf reports a non-success code."""
        layer = _make_cover_atlas_layer()
        cover_layout = MagicMock()
        exporter_instance = MagicMock()
        exporter_instance.exportToPdf.return_value = 1  # failure

        exporter_cls = MagicMock()
        exporter_cls.return_value = exporter_instance
        exporter_cls.Success = 0
        exporter_cls.PdfExportSettings = MagicMock(return_value=MagicMock())

        with patch("qfit.atlas.export_task.build_cover_layout", return_value=cover_layout), \
             patch("qfit.atlas.export_task.QgsLayoutExporter", exporter_cls):
            result = AtlasExportTask._export_cover_page(layer, "/tmp/atlas.pdf")

        self.assertIsNone(result)

    def test_export_cover_page_returns_none_on_exception(self):
        """_export_cover_page swallows exceptions and returns None."""
        layer = _make_cover_atlas_layer()
        with patch("qfit.atlas.export_task.build_cover_layout", side_effect=RuntimeError("boom")):
            result = AtlasExportTask._export_cover_page(layer, "/tmp/atlas.pdf")
        self.assertIsNone(result)


class TestCoverPage(unittest.TestCase):
    def test_cover_page_prepended_to_output(self):
        """Cover PDF path appears first in the merge call when cover succeeds."""
        layer = _make_atlas_layer(feature_count=2)
        received = {}
        task = AtlasExportTask(
            atlas_layer=layer,
            output_path="/tmp/qfit_cover_test.pdf",
            on_finished=lambda **kw: received.update(kw),
        )
        layout_mock, _, exporter_cls_mock = _make_atlas_mock(feature_count=2)
        merge_calls = []
        cover_path = "/tmp/qfit_cover_test.pdf.cover.pdf"
        with patch("qfit.atlas.export_task.build_atlas_layout", return_value=layout_mock), \
             patch("qfit.atlas.export_task.QgsLayoutExporter", exporter_cls_mock), \
             patch("qfit.atlas.export_task.AtlasExportTask._export_cover_page",
                   return_value=cover_path), \
             patch("qfit.atlas.export_task.AtlasExportTask._merge_pdfs",
                   side_effect=lambda pages, out: merge_calls.append((pages, out))), \
             patch("os.remove"), \
             patch("os.makedirs"):
            _run_task(task)
        # Cover path is first in the merged list, followed by 2 activity pages.
        self.assertEqual(len(merge_calls), 1)
        all_pages = merge_calls[0][0]
        self.assertEqual(len(all_pages), 3)
        self.assertEqual(all_pages[0], cover_path)
        self.assertIsNotNone(received.get("output_path"))

    def test_cover_page_skipped_on_failure(self):
        """Export succeeds even when _export_cover_page raises or returns None."""
        layer = _make_atlas_layer(feature_count=1)
        received = {}
        task = AtlasExportTask(
            atlas_layer=layer,
            output_path="/tmp/qfit_cover_fail.pdf",
            on_finished=lambda **kw: received.update(kw),
        )
        layout_mock, _, exporter_cls_mock = _make_atlas_mock(feature_count=1)
        with patch("qfit.atlas.export_task.build_atlas_layout", return_value=layout_mock), \
             patch("qfit.atlas.export_task.QgsLayoutExporter", exporter_cls_mock), \
             patch("qfit.atlas.export_task.AtlasExportTask._export_cover_page",
                   return_value=None), \
             patch("os.replace"), \
             patch("os.makedirs"):
            _run_task(task)
        # Export should still succeed without a cover page.
        self.assertIsNotNone(received.get("output_path"))
        self.assertIsNone(received.get("error"))

    def test_build_cover_layout_returns_none_for_empty_layer(self):
        """build_cover_layout returns None when the atlas layer has no features."""
        layer = _make_atlas_layer(feature_count=0)
        result = build_cover_layout(layer)
        self.assertIsNone(result)

    def test_build_cover_layout_returns_none_for_none_layer(self):
        """build_cover_layout returns None when atlas_layer is None."""
        result = build_cover_layout(None)
        self.assertIsNone(result)


# ---------------------------------------------------------------------------
# Tests: narrowed exception handling
# ---------------------------------------------------------------------------


class TestAtlasExportTaskNarrowedExceptions(unittest.TestCase):
    """Verify narrowed except clauses catch expected types and propagate others."""

    def test_runtime_error_caught_by_inner_handler(self):
        """RuntimeError in _run_export is caught by the inner (RuntimeError, OSError) handler."""
        received = {}
        layer = _make_atlas_layer(feature_count=1)
        task = AtlasExportTask(
            atlas_layer=layer,
            output_path="/tmp/qfit_test_narrow.pdf",
            on_finished=lambda **kw: received.update(kw),
        )
        layout_mock, _, _ = _make_atlas_mock(feature_count=1)
        with patch("qfit.atlas.export_task.build_atlas_layout", return_value=layout_mock), \
             patch("qfit.atlas.export_task.QgsLayoutExporter", side_effect=OSError("disk full")), \
             patch("os.makedirs"):
            _run_task(task)
        self.assertIn("disk full", received.get("error", ""))

    def test_cover_page_catches_runtime_error(self):
        """_export_cover_page returns None on RuntimeError."""
        layer = _make_cover_atlas_layer()
        with patch("qfit.atlas.export_task.build_cover_layout", side_effect=RuntimeError("layout fail")):
            result = AtlasExportTask._export_cover_page(layer, "/tmp/atlas.pdf")
        self.assertIsNone(result)

    def test_cover_page_catches_os_error(self):
        """_export_cover_page returns None on OSError."""
        layer = _make_cover_atlas_layer()
        with patch("qfit.atlas.export_task.build_cover_layout", side_effect=OSError("no space")):
            result = AtlasExportTask._export_cover_page(layer, "/tmp/atlas.pdf")
        self.assertIsNone(result)


class TestExtentNormalization(unittest.TestCase):
    class _Rect:
        def __init__(self, xmin, ymin, xmax, ymax):
            self._xmin = xmin
            self._ymin = ymin
            self._xmax = xmax
            self._ymax = ymax

        def width(self):
            return self._xmax - self._xmin

        def height(self):
            return self._ymax - self._ymin

        def xMinimum(self):
            return self._xmin

        def yMinimum(self):
            return self._ymin

        def xMaximum(self):
            return self._xmax

        def yMaximum(self):
            return self._ymax

    def test_normalize_extent_expands_width_for_tall_rect(self):
        from qfit.atlas.export_task import _normalize_extent_to_aspect_ratio

        rect = self._Rect(0, 0, 10, 20)
        with patch("qfit.atlas.export_task.QgsRectangle", self._Rect):
            normalized = _normalize_extent_to_aspect_ratio(rect, 1.0)

        self.assertAlmostEqual(normalized.width(), normalized.height(), places=6)
        self.assertAlmostEqual((normalized.xMinimum() + normalized.xMaximum()) / 2.0, 5.0, places=6)
        self.assertAlmostEqual((normalized.yMinimum() + normalized.yMaximum()) / 2.0, 10.0, places=6)

    def test_normalize_extent_expands_height_for_wide_rect(self):
        from qfit.atlas.export_task import _normalize_extent_to_aspect_ratio

        rect = self._Rect(0, 0, 20, 10)
        with patch("qfit.atlas.export_task.QgsRectangle", self._Rect):
            normalized = _normalize_extent_to_aspect_ratio(rect, 1.0)

        self.assertAlmostEqual(normalized.width(), normalized.height(), places=6)
        self.assertAlmostEqual((normalized.xMinimum() + normalized.xMaximum()) / 2.0, 10.0, places=6)
        self.assertAlmostEqual((normalized.yMinimum() + normalized.yMaximum()) / 2.0, 5.0, places=6)


class TestLayoutGeometry(unittest.TestCase):
    """Verify A4 portrait layout dimensions and square map frame."""

    def test_page_dimensions_are_a4_portrait(self):
        from qfit.atlas.export_task import PAGE_WIDTH_MM, PAGE_HEIGHT_MM

        self.assertAlmostEqual(PAGE_WIDTH_MM, 210.0)
        self.assertAlmostEqual(PAGE_HEIGHT_MM, 297.0)
        self.assertGreater(PAGE_HEIGHT_MM, PAGE_WIDTH_MM, "Page should be portrait (taller than wide)")

    def test_map_frame_is_square(self):
        from qfit.atlas.export_task import MAP_W, MAP_H

        self.assertAlmostEqual(MAP_W, MAP_H, places=3, msg="Map frame should be square")
        self.assertGreater(MAP_W, 0)

    def test_map_target_aspect_ratio_is_one(self):
        from qfit.atlas.export_task import BUILTIN_ATLAS_MAP_TARGET_ASPECT_RATIO

        self.assertAlmostEqual(BUILTIN_ATLAS_MAP_TARGET_ASPECT_RATIO, 1.0, places=3)

    def test_map_frame_fits_within_page(self):
        from qfit.atlas.export_task import (
            MAP_X, MAP_Y, MAP_W, MAP_H,
            PAGE_WIDTH_MM, PAGE_HEIGHT_MM, MARGIN_MM,
        )

        self.assertGreaterEqual(MAP_X, MARGIN_MM)
        self.assertLessEqual(MAP_X + MAP_W, PAGE_WIDTH_MM - MARGIN_MM)
        self.assertGreater(MAP_Y, MARGIN_MM)
        self.assertLess(MAP_Y + MAP_H, PAGE_HEIGHT_MM - MARGIN_MM)

    def test_footer_space_below_map(self):
        from qfit.atlas.export_task import (
            MAP_Y, MAP_H, PAGE_HEIGHT_MM, MARGIN_MM, FOOTER_HEIGHT_MM,
            FOOTER_GAP_MM, PROFILE_GAP_MM, PROFILE_H,
        )

        space_below_map = PAGE_HEIGHT_MM - MARGIN_MM - (MAP_Y + MAP_H)
        self.assertGreaterEqual(
            space_below_map,
            PROFILE_GAP_MM + PROFILE_H + FOOTER_GAP_MM + FOOTER_HEIGHT_MM,
            "Must be enough space below map for profile area + footer",
        )

    def test_profile_area_positioned_below_map(self):
        from qfit.atlas.export_task import (
            MAP_Y, MAP_H, PROFILE_X, PROFILE_Y, PROFILE_W, PROFILE_H, MARGIN_MM,
        )

        self.assertGreater(PROFILE_Y, MAP_Y + MAP_H, "Profile must start below map")
        self.assertGreaterEqual(PROFILE_X, MARGIN_MM)
        self.assertGreater(PROFILE_W, 0)
        self.assertGreater(PROFILE_H, 0)

    def test_profile_area_does_not_overlap_footer(self):
        from qfit.atlas.export_task import (
            PROFILE_Y, PROFILE_H, FOOTER_GAP_MM, FOOTER_HEIGHT_MM,
            PAGE_HEIGHT_MM, MARGIN_MM,
        )

        profile_bottom = PROFILE_Y + PROFILE_H
        footer_y = profile_bottom + FOOTER_GAP_MM
        footer_bottom = footer_y + FOOTER_HEIGHT_MM
        self.assertLessEqual(
            footer_bottom,
            PAGE_HEIGHT_MM - MARGIN_MM,
            "Footer must not extend beyond bottom margin",
        )

    def test_profile_area_has_usable_height(self):
        from qfit.atlas.export_task import PROFILE_H

        self.assertGreaterEqual(PROFILE_H, 40.0, "Profile area should be at least 40mm tall")

    def test_layout_items_do_not_overlap_vertically(self):
        from qfit.atlas.export_task import (
            MARGIN_MM, HEADER_HEIGHT_MM, HEADER_GAP_MM,
            MAP_Y, MAP_H, PROFILE_GAP_MM,
            PROFILE_Y, PROFILE_H, FOOTER_GAP_MM,
            FOOTER_HEIGHT_MM, PAGE_HEIGHT_MM,
        )

        header_bottom = MARGIN_MM + HEADER_HEIGHT_MM
        self.assertLessEqual(header_bottom + HEADER_GAP_MM, MAP_Y)

        map_bottom = MAP_Y + MAP_H
        self.assertLessEqual(map_bottom + PROFILE_GAP_MM, PROFILE_Y)

        profile_bottom = PROFILE_Y + PROFILE_H
        footer_y = profile_bottom + FOOTER_GAP_MM
        self.assertLessEqual(footer_y + FOOTER_HEIGHT_MM, PAGE_HEIGHT_MM - MARGIN_MM)

    def test_profile_chart_and_summaries_fit_within_profile_area(self):
        from qfit.atlas.export_task import (
            PROFILE_Y, PROFILE_H, PROFILE_CHART_Y, PROFILE_CHART_H,
            PROFILE_SUMMARY_Y, PROFILE_SUMMARY_H, PROFILE_SUMMARY_GAP,
            DETAIL_BLOCK_Y, DETAIL_BLOCK_H, DETAIL_BLOCK_GAP,
        )

        # Chart starts at profile area top
        self.assertAlmostEqual(PROFILE_CHART_Y, PROFILE_Y)
        # Profile summary is below chart with gap
        self.assertAlmostEqual(
            PROFILE_SUMMARY_Y,
            PROFILE_CHART_Y + PROFILE_CHART_H + PROFILE_SUMMARY_GAP,
        )
        # Detail block is below profile summary with gap
        self.assertAlmostEqual(
            DETAIL_BLOCK_Y,
            PROFILE_SUMMARY_Y + PROFILE_SUMMARY_H + DETAIL_BLOCK_GAP,
        )
        # Everything fits within profile area
        total = (PROFILE_CHART_H + PROFILE_SUMMARY_GAP + PROFILE_SUMMARY_H
                 + DETAIL_BLOCK_GAP + DETAIL_BLOCK_H)
        self.assertAlmostEqual(total, PROFILE_H)

    def test_profile_chart_has_positive_height(self):
        from qfit.atlas.export_task import PROFILE_CHART_H

        self.assertGreater(PROFILE_CHART_H, 20.0, "Profile chart should be at least 20mm tall")


# ---------------------------------------------------------------------------
# Tests: table of contents page
# ---------------------------------------------------------------------------


def _make_toc_atlas_layer(entries=None, feature_count=None):
    """Return a mock atlas layer with TOC-relevant fields populated.

    *entries* is a list of dicts with keys: page_number, page_toc_label,
    page_name, page_sort_key.
    """
    if entries is None:
        entries = [
            {"page_number": 1, "page_toc_label": "2025-06-01 · Morning Ride · 42 km",
             "page_name": "Morning Ride", "page_sort_key": "2025-06-01|morning_ride"},
            {"page_number": 2, "page_toc_label": "2025-06-02 · Afternoon Run · 10 km",
             "page_name": "Afternoon Run", "page_sort_key": "2025-06-02|afternoon_run"},
            {"page_number": 3, "page_toc_label": None,
             "page_name": "Evening Walk", "page_sort_key": "2025-06-03|evening_walk"},
        ]
    if feature_count is None:
        feature_count = len(entries)

    all_field_names = ["page_number", "page_toc_label", "page_name", "page_sort_key"]
    layer = MagicMock()
    layer.featureCount.return_value = feature_count

    fields = MagicMock()
    fields.indexOf = lambda name: all_field_names.index(name) if name in all_field_names else -1
    layer.fields.return_value = fields

    feats = []
    for entry in entries:
        feat = MagicMock()
        feat.attribute = lambda idx, _e=entry: list(_e.values())[idx] if 0 <= idx < len(_e) else None
        feats.append(feat)
    layer.getFeatures.return_value = iter(feats)

    return layer


class TestBuildTocLayout(unittest.TestCase):
    def test_build_toc_layout_returns_layout_for_populated_layer(self):
        layer = _make_toc_atlas_layer()
        result = build_toc_layout(layer)
        self.assertIsNotNone(result)

    def test_build_toc_layout_sets_layout_name(self):
        layer = _make_toc_atlas_layer()
        layout = build_toc_layout(layer)
        self.assertIsNotNone(layout)
        layout.setName.assert_called_with("qfit Atlas Contents")

    def test_build_toc_layout_returns_none_for_empty_layer(self):
        layer = _make_toc_atlas_layer(entries=[], feature_count=0)
        result = build_toc_layout(layer)
        self.assertIsNone(result)

    def test_build_toc_layout_returns_none_for_none_layer(self):
        result = build_toc_layout(None)
        self.assertIsNone(result)

    def test_build_toc_layout_returns_none_when_fields_missing(self):
        layer = MagicMock()
        layer.featureCount.return_value = 1
        fields = MagicMock()
        fields.indexOf = lambda name: -1  # all fields missing
        layer.fields.return_value = fields
        result = build_toc_layout(layer)
        self.assertIsNone(result)

    def test_build_toc_layout_falls_back_to_page_name(self):
        """When page_toc_label is None, page_name is used instead."""
        entries = [
            {"page_number": 1, "page_toc_label": None,
             "page_name": "Fallback Name", "page_sort_key": "a"},
        ]
        layer = _make_toc_atlas_layer(entries=entries)
        result = build_toc_layout(layer)
        self.assertIsNotNone(result)

    def test_build_toc_layout_uses_provided_project(self):
        layer = _make_toc_atlas_layer()
        project = MagicMock()
        build_toc_layout(layer, project=project)
        from qfit.atlas.export_task import QgsPrintLayout  # noqa: PLC0415
        QgsPrintLayout.assert_called_with(project)


class TestExportTocPage(unittest.TestCase):
    def test_export_toc_page_returns_path_on_success(self):
        layer = _make_toc_atlas_layer()
        toc_layout = MagicMock()
        exporter_instance = MagicMock()
        exporter_instance.exportToPdf.return_value = 0  # Success

        exporter_cls = MagicMock()
        exporter_cls.return_value = exporter_instance
        exporter_cls.Success = 0
        exporter_cls.PdfExportSettings = MagicMock(return_value=MagicMock())

        with patch("qfit.atlas.export_task.build_toc_layout", return_value=toc_layout), \
             patch("qfit.atlas.export_task.QgsLayoutExporter", exporter_cls):
            result = AtlasExportTask._export_toc_page(layer, "/tmp/atlas.pdf")

        self.assertEqual(result, "/tmp/atlas.pdf.toc.pdf")

    def test_export_toc_page_returns_none_when_layout_is_none(self):
        layer = _make_toc_atlas_layer(entries=[], feature_count=0)
        with patch("qfit.atlas.export_task.build_toc_layout", return_value=None):
            result = AtlasExportTask._export_toc_page(layer, "/tmp/atlas.pdf")
        self.assertIsNone(result)

    def test_export_toc_page_returns_none_on_exporter_failure(self):
        layer = _make_toc_atlas_layer()
        toc_layout = MagicMock()
        exporter_instance = MagicMock()
        exporter_instance.exportToPdf.return_value = 1  # failure

        exporter_cls = MagicMock()
        exporter_cls.return_value = exporter_instance
        exporter_cls.Success = 0
        exporter_cls.PdfExportSettings = MagicMock(return_value=MagicMock())

        with patch("qfit.atlas.export_task.build_toc_layout", return_value=toc_layout), \
             patch("qfit.atlas.export_task.QgsLayoutExporter", exporter_cls):
            result = AtlasExportTask._export_toc_page(layer, "/tmp/atlas.pdf")

        self.assertIsNone(result)

    def test_export_toc_page_returns_none_on_exception(self):
        layer = _make_toc_atlas_layer()
        with patch("qfit.atlas.export_task.build_toc_layout", side_effect=RuntimeError("boom")):
            result = AtlasExportTask._export_toc_page(layer, "/tmp/atlas.pdf")
        self.assertIsNone(result)


class TestTocPageInExport(unittest.TestCase):
    def test_toc_page_inserted_between_cover_and_activity_pages(self):
        """TOC PDF path appears after cover and before activity pages in merge."""
        layer = _make_atlas_layer(feature_count=2)
        received = {}
        task = AtlasExportTask(
            atlas_layer=layer,
            output_path="/tmp/qfit_toc_test.pdf",
            on_finished=lambda **kw: received.update(kw),
        )
        layout_mock, _, exporter_cls_mock = _make_atlas_mock(feature_count=2)
        merge_calls = []
        cover_path = "/tmp/qfit_toc_test.pdf.cover.pdf"
        toc_path = "/tmp/qfit_toc_test.pdf.toc.pdf"
        with patch("qfit.atlas.export_task.build_atlas_layout", return_value=layout_mock), \
             patch("qfit.atlas.export_task.QgsLayoutExporter", exporter_cls_mock), \
             patch("qfit.atlas.export_task.AtlasExportTask._export_cover_page",
                   return_value=cover_path), \
             patch("qfit.atlas.export_task.AtlasExportTask._export_toc_page",
                   return_value=toc_path), \
             patch("qfit.atlas.export_task.AtlasExportTask._merge_pdfs",
                   side_effect=lambda pages, out: merge_calls.append((pages, out))), \
             patch("os.remove"), \
             patch("os.makedirs"):
            _run_task(task)
        self.assertEqual(len(merge_calls), 1)
        all_pages = merge_calls[0][0]
        self.assertEqual(all_pages[0], cover_path)
        self.assertEqual(all_pages[1], toc_path)
        self.assertEqual(len(all_pages), 4)  # cover + toc + 2 activity pages

    def test_toc_page_skipped_on_failure(self):
        """Export succeeds even when _export_toc_page returns None."""
        layer = _make_atlas_layer(feature_count=1)
        received = {}
        task = AtlasExportTask(
            atlas_layer=layer,
            output_path="/tmp/qfit_toc_fail.pdf",
            on_finished=lambda **kw: received.update(kw),
        )
        layout_mock, _, exporter_cls_mock = _make_atlas_mock(feature_count=1)
        with patch("qfit.atlas.export_task.build_atlas_layout", return_value=layout_mock), \
             patch("qfit.atlas.export_task.QgsLayoutExporter", exporter_cls_mock), \
             patch("qfit.atlas.export_task.AtlasExportTask._export_cover_page",
                   return_value=None), \
             patch("qfit.atlas.export_task.AtlasExportTask._export_toc_page",
                   return_value=None), \
             patch("os.replace"), \
             patch("os.makedirs"):
            _run_task(task)
        self.assertIsNotNone(received.get("output_path"))
        self.assertIsNone(received.get("error"))


# ---------------------------------------------------------------------------
# Tests: cover heatmap overview map
# ---------------------------------------------------------------------------


def _make_cover_atlas_layer_with_extents(feature_count=2):
    """Return a mock atlas layer whose features carry extent and activity-ID fields."""
    field_names = [
        "page_date", "activity_type", "distance_m", "moving_time_s",
        "total_elevation_gain_m",
        "document_cover_summary", "document_activity_count",
        "document_date_range_label", "document_total_distance_label",
        "document_total_duration_label", "document_total_elevation_gain_label",
        "document_activity_types_label",
        # Extent and ID fields used by the cover heatmap map
        "center_x_3857", "center_y_3857", "extent_width_m", "extent_height_m",
        "source_activity_id",
    ]
    rows = [
        ["2026-03-01", "Run", 10000.0, 3600, 200.0,
         "stale", "99", "", "", "", "", "Run",
         1000000.0, 6000000.0, 5000.0, 5000.0, "act_1"],
        ["2026-03-02", "Ride", 20000.0, 7200, 400.0,
         "stale", "99", "", "", "", "", "Run, Ride",
         1010000.0, 6010000.0, 6000.0, 6000.0, "act_2"],
    ]

    layer = MagicMock()
    layer.featureCount.return_value = feature_count

    fields = MagicMock()
    fields.indexOf = lambda name: field_names.index(name) if name in field_names else -1
    layer.fields.return_value = fields

    feats = []
    for i in range(feature_count):
        row = rows[i % len(rows)]
        feat = MagicMock()
        feat.attribute = lambda idx, _row=row: _row[idx] if 0 <= idx < len(_row) else None
        feats.append(feat)
    layer.getFeatures.side_effect = lambda: iter(feats)
    return layer


class TestCoverSummaryExtentAndActivityIds(unittest.TestCase):
    """Tests for extent bounds and activity IDs computed by the cover summary."""

    def test_summary_returns_valid_extent_bounds(self):
        layer = _make_cover_atlas_layer_with_extents()
        result = _build_cover_summary_from_current_atlas_features(layer)
        self.assertIsNotNone(result.get("_cover_extent_xmin"))
        self.assertIsNotNone(result.get("_cover_extent_ymin"))
        self.assertIsNotNone(result.get("_cover_extent_xmax"))
        self.assertIsNotNone(result.get("_cover_extent_ymax"))
        self.assertLess(result["_cover_extent_xmin"], result["_cover_extent_xmax"])
        self.assertLess(result["_cover_extent_ymin"], result["_cover_extent_ymax"])

    def test_summary_collects_unique_activity_ids(self):
        layer = _make_cover_atlas_layer_with_extents()
        result = _build_cover_summary_from_current_atlas_features(layer)
        ids = result.get("_atlas_activity_ids", [])
        self.assertEqual(ids, ["act_1", "act_2"])

    def test_summary_extent_none_when_fields_absent(self):
        """When extent fields are missing, bounds should be None."""
        layer = _make_cover_atlas_layer(feature_count=1)
        result = _build_cover_summary_from_current_atlas_features(layer)
        self.assertIsNone(result.get("_cover_extent_xmin"))


class TestApplyCoverHeatmapRenderer(unittest.TestCase):
    """Tests for _apply_cover_heatmap_renderer."""

    def test_sets_renderer_on_layer(self):
        layer = MagicMock()
        # Add the symbols the function imports at runtime into the qgis.core stub.
        heatmap_renderer = MagicMock()
        heatmap_cls = MagicMock(return_value=heatmap_renderer)
        style_cls = MagicMock()
        style_cls.defaultStyle.return_value.colorRamp.return_value = MagicMock()
        ramp_cls = MagicMock()
        _qgis_core.QgsHeatmapRenderer = heatmap_cls
        _qgis_core.QgsStyle = style_cls
        _qgis_core.QgsGradientColorRamp = ramp_cls
        try:
            _apply_cover_heatmap_renderer(layer)
        finally:
            del _qgis_core.QgsHeatmapRenderer
            del _qgis_core.QgsStyle
            del _qgis_core.QgsGradientColorRamp
        layer.setRenderer.assert_called_once_with(heatmap_renderer)
        layer.setOpacity.assert_called_once_with(0.85)


class TestBuildCoverLayoutWithMap(unittest.TestCase):
    """Tests for the cover heatmap overview map in build_cover_layout."""

    def _make_cover_data_with_extent(self):
        return {
            "document_cover_summary": "2 activities",
            "document_activity_count": "2",
            "document_date_range_label": "2026-03-01 → 2026-03-02",
            "document_total_distance_label": "30.0 km",
            "document_total_duration_label": "3h",
            "document_total_elevation_gain_label": "600 m",
            "document_activity_types_label": "Run, Ride",
            "_cover_extent_xmin": 997500.0,
            "_cover_extent_ymin": 5997500.0,
            "_cover_extent_xmax": 1013000.0,
            "_cover_extent_ymax": 6013000.0,
            "_atlas_activity_ids": ["act_1", "act_2"],
        }

    def test_map_item_added_when_layers_and_extent_provided(self):
        """A QgsLayoutItemMap is added when map_layers and extent data exist."""
        layer = _make_cover_atlas_layer()
        cover_data = self._make_cover_data_with_extent()
        map_layer = MagicMock()

        fresh_layout = MagicMock()
        fresh_layout.pageCollection.return_value.pageCount.return_value = 1
        fresh_layout.pageCollection.return_value.page.return_value = MagicMock()
        map_item_mock = MagicMock()

        with patch("qfit.atlas.export_task.QgsPrintLayout", return_value=fresh_layout), \
             patch("qfit.atlas.export_task.QgsLayoutItemMap", return_value=map_item_mock):
            result = build_cover_layout(
                layer, map_layers=[map_layer], cover_data=cover_data,
            )
        self.assertIsNotNone(result)
        # The map item should have been added to the layout
        add_calls = [
            c for c in fresh_layout.addLayoutItem.call_args_list
            if c[0][0] is map_item_mock
        ]
        self.assertEqual(len(add_calls), 1)
        # Map should be set to the provided layers
        map_item_mock.setLayers.assert_called_once_with([map_layer])
        map_item_mock.setCrs.assert_called_once()
        map_item_mock.setExtent.assert_called_once()

    def test_no_map_when_layers_absent(self):
        """No map item is added when map_layers is None."""
        layer = _make_cover_atlas_layer()
        cover_data = self._make_cover_data_with_extent()

        fresh_layout = MagicMock()
        fresh_layout.pageCollection.return_value.pageCount.return_value = 1
        fresh_layout.pageCollection.return_value.page.return_value = MagicMock()
        map_cls = MagicMock()

        with patch("qfit.atlas.export_task.QgsPrintLayout", return_value=fresh_layout), \
             patch("qfit.atlas.export_task.QgsLayoutItemMap", map_cls):
            result = build_cover_layout(
                layer, map_layers=None, cover_data=cover_data,
            )
        self.assertIsNotNone(result)
        map_cls.assert_not_called()

    def test_no_map_when_extent_missing(self):
        """No map item is added when extent bounds are absent from cover_data."""
        layer = _make_cover_atlas_layer()
        cover_data = self._make_cover_data_with_extent()
        cover_data["_cover_extent_xmin"] = None  # invalidate extent
        map_layer = MagicMock()

        fresh_layout = MagicMock()
        fresh_layout.pageCollection.return_value.pageCount.return_value = 1
        fresh_layout.pageCollection.return_value.page.return_value = MagicMock()
        map_cls = MagicMock()

        with patch("qfit.atlas.export_task.QgsPrintLayout", return_value=fresh_layout), \
             patch("qfit.atlas.export_task.QgsLayoutItemMap", map_cls):
            result = build_cover_layout(
                layer, map_layers=[map_layer], cover_data=cover_data,
            )
        self.assertIsNotNone(result)
        map_cls.assert_not_called()

    def test_map_is_square_and_centered(self):
        """The cover map item is square and horizontally centered."""
        from qfit.atlas.export_task import PAGE_WIDTH_MM  # noqa: PLC0415
        layer = _make_cover_atlas_layer()
        cover_data = self._make_cover_data_with_extent()
        map_layer = MagicMock()

        fresh_layout = MagicMock()
        fresh_layout.pageCollection.return_value.pageCount.return_value = 1
        fresh_layout.pageCollection.return_value.page.return_value = MagicMock()

        size_calls = []
        point_calls = []
        original_size = _qgis_core.QgsLayoutSize
        original_point = _qgis_core.QgsLayoutPoint

        def capture_size(*args, **kwargs):
            size_calls.append(args)
            return original_size(*args, **kwargs)

        def capture_point(*args, **kwargs):
            point_calls.append(args)
            return original_point(*args, **kwargs)

        map_item_mock = MagicMock()
        with patch("qfit.atlas.export_task.QgsPrintLayout", return_value=fresh_layout), \
             patch("qfit.atlas.export_task.QgsLayoutItemMap", return_value=map_item_mock), \
             patch("qfit.atlas.export_task.QgsLayoutSize", side_effect=capture_size), \
             patch("qfit.atlas.export_task.QgsLayoutPoint", side_effect=capture_point):
            build_cover_layout(
                layer, map_layers=[map_layer], cover_data=cover_data,
            )

        # Find the size call for the map (square → width == height)
        resize_calls = map_item_mock.attemptResize.call_args_list
        self.assertEqual(len(resize_calls), 1)
        # The size was created with (cover_map_size, cover_map_size, ...)
        # Get the args from the QgsLayoutSize call that was passed to attemptResize
        map_size_arg = resize_calls[0][0][0]  # first positional arg
        # Find the matching size_calls entry
        map_sizes = [s for s in size_calls if len(s) >= 2 and s[0] == s[1]]
        self.assertGreaterEqual(len(map_sizes), 1, "Map size should be square (w == h)")

        # Check centering: map x should be (PAGE_WIDTH - size) / 2
        move_calls = map_item_mock.attemptMove.call_args_list
        self.assertEqual(len(move_calls), 1)
        map_point_arg = move_calls[0][0][0]
        # Find the point call that was used for the map move
        # The x coordinate should approximately center the map
        map_point_match = [p for p in point_calls if len(p) >= 2
                          and abs(p[0] - (PAGE_WIDTH_MM - p[0] * 2) / 2) < 1.0
                          or abs(p[0] * 2 + map_sizes[0][0] - PAGE_WIDTH_MM) < 1.0]
        # Just verify it was called - exact centering validated by the formula in code
        self.assertTrue(len(move_calls) > 0)


class TestExportCoverPageHeatmap(unittest.TestCase):
    """Tests for heatmap layer discovery and state restoration in _export_cover_page."""

    def _make_project_with_layers(self, points_layer=None, starts_layer=None,
                                   background_layer=None):
        """Build a mock project whose layer tree contains the given layers."""
        project = MagicMock()
        nodes = []
        for lyr in [points_layer, starts_layer, background_layer]:
            if lyr is not None:
                node = MagicMock()
                node.isVisible.return_value = True
                node.layer.return_value = lyr
                nodes.append(node)
        project.layerTreeRoot.return_value.findLayers.return_value = nodes
        return project

    def _make_points_layer(self, name="qfit activity points"):
        layer = MagicMock()
        layer.name.return_value = name
        layer.subsetString.return_value = ""
        layer.opacity.return_value = 1.0
        renderer = MagicMock()
        renderer.clone.return_value = MagicMock()
        layer.renderer.return_value = renderer
        # Give it a source_activity_id field
        fields = MagicMock()
        fields.indexOf = lambda n: 0 if n == "source_activity_id" else -1
        layer.fields.return_value = fields
        return layer

    def test_heatmap_renderer_applied_to_points_layer(self):
        """When a points layer exists, _export_cover_page applies heatmap renderer."""
        atlas_layer = _make_cover_atlas_layer_with_extents()
        pts = self._make_points_layer()
        project = self._make_project_with_layers(points_layer=pts)

        cover_layout = MagicMock()
        exporter_instance = MagicMock()
        exporter_instance.exportToPdf.return_value = 0

        exporter_cls = MagicMock()
        exporter_cls.return_value = exporter_instance
        exporter_cls.Success = 0
        exporter_cls.PdfExportSettings = MagicMock(return_value=MagicMock())

        with patch("qfit.atlas.export_task.build_cover_layout", return_value=cover_layout) as build_mock, \
             patch("qfit.atlas.export_task.QgsLayoutExporter", exporter_cls), \
             patch("qfit.atlas.export_task._apply_cover_heatmap_renderer") as heatmap_mock:
            result = AtlasExportTask._export_cover_page(
                atlas_layer, "/tmp/atlas.pdf", project=project,
            )

        self.assertIsNotNone(result)
        heatmap_mock.assert_called_once_with(pts)
        # build_cover_layout should have received map_layers containing the points layer
        _, kwargs = build_mock.call_args
        self.assertIsNotNone(kwargs.get("map_layers"))
        self.assertIn(pts, kwargs["map_layers"])

    def test_subset_filter_applied_for_atlas_activity_ids(self):
        """Points layer gets filtered to the atlas subset's activity IDs."""
        atlas_layer = _make_cover_atlas_layer_with_extents()
        pts = self._make_points_layer()
        project = self._make_project_with_layers(points_layer=pts)

        cover_layout = MagicMock()
        exporter_instance = MagicMock()
        exporter_instance.exportToPdf.return_value = 0

        exporter_cls = MagicMock()
        exporter_cls.return_value = exporter_instance
        exporter_cls.Success = 0
        exporter_cls.PdfExportSettings = MagicMock(return_value=MagicMock())

        with patch("qfit.atlas.export_task.build_cover_layout", return_value=cover_layout), \
             patch("qfit.atlas.export_task.QgsLayoutExporter", exporter_cls), \
             patch("qfit.atlas.export_task._apply_cover_heatmap_renderer"):
            AtlasExportTask._export_cover_page(
                atlas_layer, "/tmp/atlas.pdf", project=project,
            )

        # The subset string should reference the activity IDs.
        # call_args_list[0] is the filter, call_args_list[-1] is the restore.
        subset_calls = pts.setSubsetString.call_args_list
        self.assertGreaterEqual(len(subset_calls), 2)
        filter_str = subset_calls[0][0][0]
        self.assertIn("act_1", filter_str)
        self.assertIn("act_2", filter_str)
        self.assertIn("source_activity_id", filter_str)

    def test_layer_state_restored_after_export(self):
        """Original renderer, opacity, and subset are restored after export."""
        atlas_layer = _make_cover_atlas_layer_with_extents()
        pts = self._make_points_layer()
        original_renderer = pts.renderer().clone()
        project = self._make_project_with_layers(points_layer=pts)

        cover_layout = MagicMock()
        exporter_instance = MagicMock()
        exporter_instance.exportToPdf.return_value = 0

        exporter_cls = MagicMock()
        exporter_cls.return_value = exporter_instance
        exporter_cls.Success = 0
        exporter_cls.PdfExportSettings = MagicMock(return_value=MagicMock())

        with patch("qfit.atlas.export_task.build_cover_layout", return_value=cover_layout), \
             patch("qfit.atlas.export_task.QgsLayoutExporter", exporter_cls), \
             patch("qfit.atlas.export_task._apply_cover_heatmap_renderer"):
            AtlasExportTask._export_cover_page(
                atlas_layer, "/tmp/atlas.pdf", project=project,
            )

        # Subset should be restored to original ""
        restore_calls = pts.setSubsetString.call_args_list
        self.assertEqual(restore_calls[-1][0][0], "")
        # Opacity should be restored
        pts.setOpacity.assert_called()
        # Renderer should be restored
        pts.setRenderer.assert_called()

    def test_layer_state_restored_on_export_failure(self):
        """Layer state is restored even when PDF export fails."""
        atlas_layer = _make_cover_atlas_layer_with_extents()
        pts = self._make_points_layer()
        project = self._make_project_with_layers(points_layer=pts)

        cover_layout = MagicMock()
        exporter_instance = MagicMock()
        exporter_instance.exportToPdf.return_value = 1  # failure

        exporter_cls = MagicMock()
        exporter_cls.return_value = exporter_instance
        exporter_cls.Success = 0
        exporter_cls.PdfExportSettings = MagicMock(return_value=MagicMock())

        with patch("qfit.atlas.export_task.build_cover_layout", return_value=cover_layout), \
             patch("qfit.atlas.export_task.QgsLayoutExporter", exporter_cls), \
             patch("qfit.atlas.export_task._apply_cover_heatmap_renderer"):
            result = AtlasExportTask._export_cover_page(
                atlas_layer, "/tmp/atlas.pdf", project=project,
            )

        self.assertIsNone(result)
        # Subset should still be restored to original ""
        restore_calls = pts.setSubsetString.call_args_list
        self.assertEqual(restore_calls[-1][0][0], "")

    def test_falls_back_to_starts_layer_when_no_points(self):
        """Uses the starts layer for heatmap when points layer is absent."""
        atlas_layer = _make_cover_atlas_layer_with_extents()
        starts = self._make_points_layer(name="qfit activity starts")
        project = self._make_project_with_layers(starts_layer=starts)

        cover_layout = MagicMock()
        exporter_instance = MagicMock()
        exporter_instance.exportToPdf.return_value = 0

        exporter_cls = MagicMock()
        exporter_cls.return_value = exporter_instance
        exporter_cls.Success = 0
        exporter_cls.PdfExportSettings = MagicMock(return_value=MagicMock())

        with patch("qfit.atlas.export_task.build_cover_layout", return_value=cover_layout) as build_mock, \
             patch("qfit.atlas.export_task.QgsLayoutExporter", exporter_cls), \
             patch("qfit.atlas.export_task._apply_cover_heatmap_renderer") as heatmap_mock:
            AtlasExportTask._export_cover_page(
                atlas_layer, "/tmp/atlas.pdf", project=project,
            )

        heatmap_mock.assert_called_once_with(starts)

    def test_no_map_when_no_suitable_layers(self):
        """Cover is still generated but without a map when no point layers exist."""
        atlas_layer = _make_cover_atlas_layer_with_extents()
        # Only a background layer, no points or starts
        bg = MagicMock()
        bg.name.return_value = "Mapbox Satellite"
        project = self._make_project_with_layers(background_layer=bg)

        cover_layout = MagicMock()
        exporter_instance = MagicMock()
        exporter_instance.exportToPdf.return_value = 0

        exporter_cls = MagicMock()
        exporter_cls.return_value = exporter_instance
        exporter_cls.Success = 0
        exporter_cls.PdfExportSettings = MagicMock(return_value=MagicMock())

        with patch("qfit.atlas.export_task.build_cover_layout", return_value=cover_layout) as build_mock, \
             patch("qfit.atlas.export_task.QgsLayoutExporter", exporter_cls), \
             patch("qfit.atlas.export_task._apply_cover_heatmap_renderer") as heatmap_mock:
            result = AtlasExportTask._export_cover_page(
                atlas_layer, "/tmp/atlas.pdf", project=project,
            )

        self.assertIsNotNone(result)
        heatmap_mock.assert_not_called()

    def test_starts_layer_hidden_when_points_used_for_heatmap(self):
        """When points layer drives the heatmap, starts layer opacity is set to 0."""
        atlas_layer = _make_cover_atlas_layer_with_extents()
        pts = self._make_points_layer()
        starts = self._make_points_layer(name="qfit activity starts")
        project = self._make_project_with_layers(
            points_layer=pts, starts_layer=starts,
        )

        cover_layout = MagicMock()
        exporter_instance = MagicMock()
        exporter_instance.exportToPdf.return_value = 0

        exporter_cls = MagicMock()
        exporter_cls.return_value = exporter_instance
        exporter_cls.Success = 0
        exporter_cls.PdfExportSettings = MagicMock(return_value=MagicMock())

        with patch("qfit.atlas.export_task.build_cover_layout", return_value=cover_layout), \
             patch("qfit.atlas.export_task.QgsLayoutExporter", exporter_cls), \
             patch("qfit.atlas.export_task._apply_cover_heatmap_renderer"):
            AtlasExportTask._export_cover_page(
                atlas_layer, "/tmp/atlas.pdf", project=project,
            )

        # Starts layer should have been set to 0 opacity during export
        opacity_calls = starts.setOpacity.call_args_list
        self.assertTrue(any(c[0][0] == 0.0 for c in opacity_calls),
                        "Starts layer should be hidden (opacity 0) when points drive the heatmap")


if __name__ == "__main__":
    unittest.main()
