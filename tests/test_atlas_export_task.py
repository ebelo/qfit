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
    qgis_core.QgsLayoutPoint = MagicMock()
    qgis_core.QgsLayoutSize = MagicMock()
    qgis_core.QgsLayoutExporter = MagicMock()
    qgis_core.QgsLayoutExporter.Success = 0
    qgis_core.QgsUnitTypes = MagicMock()
    qgis_core.QgsUnitTypes.LayoutMillimeters = 0
    qgis_core.QgsAtlasComposition = MagicMock()

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

from qfit.atlas_export_task import AtlasExportTask, build_atlas_layout, build_cover_layout  # noqa: E402


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

        with patch("qfit.atlas_export_task.QgsPrintLayout") as mock_layout_cls, \
             patch("qfit.atlas_export_task.QgsLayoutItemMap") as mock_map_cls:
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
        with patch("qfit.atlas_export_task.build_atlas_layout", return_value=layout_mock), \
             patch("qfit.atlas_export_task.QgsLayoutExporter", exporter_cls_mock), \
             patch("qfit.atlas_export_task.AtlasExportTask._merge_pdfs"), \
             patch("qfit.atlas_export_task.AtlasExportTask._export_cover_page", return_value=None), \
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
        layout_mock, _, exporter_cls_mock = _make_atlas_mock(feature_count=1)
        with patch("qfit.atlas_export_task.build_atlas_layout", return_value=layout_mock), \
             patch("qfit.atlas_export_task.QgsLayoutExporter", exporter_cls_mock), \
             patch("qfit.atlas_export_task.AtlasExportTask._export_cover_page", return_value=None), \
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
        with patch("qfit.atlas_export_task.build_atlas_layout", return_value=layout_mock), \
             patch("qfit.atlas_export_task.QgsLayoutExporter", exporter_cls_mock), \
             patch("qfit.atlas_export_task.AtlasExportTask._merge_pdfs"), \
             patch("qfit.atlas_export_task.AtlasExportTask._export_cover_page", return_value=None), \
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
        with patch("qfit.atlas_export_task.build_atlas_layout", return_value=layout_mock), \
             patch("qfit.atlas_export_task.QgsLayoutExporter", exporter_cls_mock), \
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
        with patch("qfit.atlas_export_task.build_atlas_layout", side_effect=RuntimeError("boom")):
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
        with patch("qfit.atlas_export_task.build_atlas_layout", return_value=layout_mock), \
             patch("qfit.atlas_export_task.QgsLayoutExporter", exporter_cls_mock), \
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
        layout_mock, _, exporter_cls_mock = _make_atlas_mock(feature_count=1)
        with patch("qfit.atlas_export_task.build_atlas_layout", return_value=layout_mock), \
             patch("qfit.atlas_export_task.QgsLayoutExporter", exporter_cls_mock), \
             patch("qfit.atlas_export_task.AtlasExportTask._export_cover_page", return_value=None), \
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
        layout_mock, _, exporter_cls_mock = _make_atlas_mock(feature_count=1)
        with patch("qfit.atlas_export_task.build_atlas_layout", return_value=layout_mock), \
             patch("qfit.atlas_export_task.QgsLayoutExporter", exporter_cls_mock), \
             patch("qfit.atlas_export_task.AtlasExportTask._export_cover_page", return_value=None), \
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

        with patch("qfit.atlas_export_task.build_atlas_layout", return_value=layout_mock), \
             patch("qfit.atlas_export_task.QgsLayoutExporter", exporter_cls_mock), \
             patch("qfit.atlas_export_task.AtlasExportTask._export_cover_page", return_value=None), \
             patch("os.replace"), \
             patch("os.makedirs"):
            _run_task(task)

        # A per-page filter was set on the track layer.
        self.assertTrue(len(track_calls) >= 2, f"Expected ≥2 calls, got: {track_calls}")
        self.assertTrue(any("source_activity_id" in call for call in track_calls[:-1]))
        # Original subset string ("") was restored as the final call.
        self.assertEqual(track_calls[-1], "")
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
        with patch("qfit.atlas_export_task.build_atlas_layout", return_value=layout_mock), \
             patch("qfit.atlas_export_task.QgsLayoutExporter", exporter_cls_mock), \
             patch("qfit.atlas_export_task.AtlasExportTask._merge_pdfs",
                   side_effect=lambda pages, out: merge_calls.append((pages, out))), \
             patch("qfit.atlas_export_task.AtlasExportTask._export_cover_page", return_value=None), \
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
        layout_mock, _, exporter_cls_mock = _make_atlas_mock(feature_count=1)
        replace_calls = []
        with patch("qfit.atlas_export_task.build_atlas_layout", return_value=layout_mock), \
             patch("qfit.atlas_export_task.QgsLayoutExporter", exporter_cls_mock), \
             patch("qfit.atlas_export_task.AtlasExportTask._export_cover_page", return_value=None), \
             patch("os.replace", side_effect=lambda src, dst: replace_calls.append((src, dst))), \
             patch("qfit.atlas_export_task.AtlasExportTask._merge_pdfs") as mock_merge, \
             patch("os.makedirs"):
            _run_task(task)
        mock_merge.assert_not_called()
        self.assertEqual(len(replace_calls), 1)
        self.assertEqual(replace_calls[0][1], "/tmp/qfit_test_replace.pdf")


# ---------------------------------------------------------------------------
# Tests: cover page
# ---------------------------------------------------------------------------


def _make_cover_atlas_layer(fields_dict=None, feature_count=1):
    """Return a mock atlas layer with cover document fields populated."""
    fields_dict = fields_dict or {
        "document_cover_summary": "3 activities · 2025-01-01 → 2026-03-22 · 250.0 km",
        "document_activity_count": "3",
        "document_date_range_label": "2025-01-01 → 2026-03-22",
        "document_total_distance_label": "250.0 km",
        "document_total_duration_label": "12h 30m",
        "document_total_elevation_gain_label": "5000 m",
        "document_activity_types_label": "Run, Ride",
    }
    all_field_names = list(fields_dict.keys())

    layer = MagicMock()
    layer.featureCount.return_value = feature_count

    fields = MagicMock()
    fields.indexOf = lambda name: all_field_names.index(name) if name in all_field_names else -1
    layer.fields.return_value = fields

    feat = MagicMock()
    feat.attribute = lambda idx: list(fields_dict.values())[idx] if 0 <= idx < len(fields_dict) else None
    layer.getFeatures.return_value = iter([feat])

    return layer


class TestBuildCoverLayout(unittest.TestCase):
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
        from qfit.atlas_export_task import QgsPrintLayout  # noqa: PLC0415
        QgsPrintLayout.assert_called_with(project)


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

        with patch("qfit.atlas_export_task.build_cover_layout", return_value=cover_layout), \
             patch("qfit.atlas_export_task.QgsLayoutExporter", exporter_cls):
            result = AtlasExportTask._export_cover_page(layer, "/tmp/atlas.pdf")

        self.assertEqual(result, "/tmp/atlas.pdf.cover.pdf")

    def test_export_cover_page_returns_none_when_layout_is_none(self):
        """_export_cover_page returns None when build_cover_layout returns None."""
        layer = _make_cover_atlas_layer(feature_count=0)
        with patch("qfit.atlas_export_task.build_cover_layout", return_value=None):
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

        with patch("qfit.atlas_export_task.build_cover_layout", return_value=cover_layout), \
             patch("qfit.atlas_export_task.QgsLayoutExporter", exporter_cls):
            result = AtlasExportTask._export_cover_page(layer, "/tmp/atlas.pdf")

        self.assertIsNone(result)

    def test_export_cover_page_returns_none_on_exception(self):
        """_export_cover_page swallows exceptions and returns None."""
        layer = _make_cover_atlas_layer()
        with patch("qfit.atlas_export_task.build_cover_layout", side_effect=RuntimeError("boom")):
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
        with patch("qfit.atlas_export_task.build_atlas_layout", return_value=layout_mock), \
             patch("qfit.atlas_export_task.QgsLayoutExporter", exporter_cls_mock), \
             patch("qfit.atlas_export_task.AtlasExportTask._export_cover_page",
                   return_value=cover_path), \
             patch("qfit.atlas_export_task.AtlasExportTask._merge_pdfs",
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
        with patch("qfit.atlas_export_task.build_atlas_layout", return_value=layout_mock), \
             patch("qfit.atlas_export_task.QgsLayoutExporter", exporter_cls_mock), \
             patch("qfit.atlas_export_task.AtlasExportTask._export_cover_page",
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
        with patch("qfit.atlas_export_task.build_atlas_layout", return_value=layout_mock), \
             patch("qfit.atlas_export_task.QgsLayoutExporter", side_effect=OSError("disk full")), \
             patch("os.makedirs"):
            _run_task(task)
        self.assertIn("disk full", received.get("error", ""))

    def test_cover_page_catches_runtime_error(self):
        """_export_cover_page returns None on RuntimeError."""
        layer = _make_cover_atlas_layer()
        with patch("qfit.atlas_export_task.build_cover_layout", side_effect=RuntimeError("layout fail")):
            result = AtlasExportTask._export_cover_page(layer, "/tmp/atlas.pdf")
        self.assertIsNone(result)

    def test_cover_page_catches_os_error(self):
        """_export_cover_page returns None on OSError."""
        layer = _make_cover_atlas_layer()
        with patch("qfit.atlas_export_task.build_cover_layout", side_effect=OSError("no space")):
            result = AtlasExportTask._export_cover_page(layer, "/tmp/atlas.pdf")
        self.assertIsNone(result)


class TestLayoutGeometry(unittest.TestCase):
    """Verify A4 portrait layout dimensions and square map frame."""

    def test_page_dimensions_are_a4_portrait(self):
        from qfit.atlas_export_task import PAGE_WIDTH_MM, PAGE_HEIGHT_MM

        self.assertAlmostEqual(PAGE_WIDTH_MM, 210.0)
        self.assertAlmostEqual(PAGE_HEIGHT_MM, 297.0)
        self.assertGreater(PAGE_HEIGHT_MM, PAGE_WIDTH_MM, "Page should be portrait (taller than wide)")

    def test_map_frame_is_square(self):
        from qfit.atlas_export_task import MAP_W, MAP_H

        self.assertAlmostEqual(MAP_W, MAP_H, places=3, msg="Map frame should be square")
        self.assertGreater(MAP_W, 0)

    def test_map_target_aspect_ratio_is_one(self):
        from qfit.atlas_export_task import BUILTIN_ATLAS_MAP_TARGET_ASPECT_RATIO

        self.assertAlmostEqual(BUILTIN_ATLAS_MAP_TARGET_ASPECT_RATIO, 1.0, places=3)

    def test_map_frame_fits_within_page(self):
        from qfit.atlas_export_task import (
            MAP_X, MAP_Y, MAP_W, MAP_H,
            PAGE_WIDTH_MM, PAGE_HEIGHT_MM, MARGIN_MM,
        )

        self.assertGreaterEqual(MAP_X, MARGIN_MM)
        self.assertLessEqual(MAP_X + MAP_W, PAGE_WIDTH_MM - MARGIN_MM)
        self.assertGreater(MAP_Y, MARGIN_MM)
        self.assertLess(MAP_Y + MAP_H, PAGE_HEIGHT_MM - MARGIN_MM)

    def test_footer_space_below_map(self):
        from qfit.atlas_export_task import (
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
        from qfit.atlas_export_task import (
            MAP_Y, MAP_H, PROFILE_X, PROFILE_Y, PROFILE_W, PROFILE_H, MARGIN_MM,
        )

        self.assertGreater(PROFILE_Y, MAP_Y + MAP_H, "Profile must start below map")
        self.assertGreaterEqual(PROFILE_X, MARGIN_MM)
        self.assertGreater(PROFILE_W, 0)
        self.assertGreater(PROFILE_H, 0)

    def test_profile_area_does_not_overlap_footer(self):
        from qfit.atlas_export_task import (
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
        from qfit.atlas_export_task import PROFILE_H

        self.assertGreaterEqual(PROFILE_H, 40.0, "Profile area should be at least 40mm tall")

    def test_layout_items_do_not_overlap_vertically(self):
        from qfit.atlas_export_task import (
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


if __name__ == "__main__":
    unittest.main()
