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
    qgis_core.QgsPrintLayout = MagicMock()
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

from qfit.atlas_export_task import AtlasExportTask, build_atlas_layout  # noqa: E402


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
            output_path="/tmp/qfit_test_atlas.pdf",
            on_finished=lambda **kw: received.update(kw),
        )
        task._cancelled = True

        with patch("qfit.atlas_export_task.build_atlas_layout") as mock_build, \
             patch("os.path.exists", return_value=True), \
             patch("qfit.atlas_export_task.QgsLayoutExporter") as mock_exporter_cls:
            mock_layout = MagicMock()
            mock_layout.atlas.return_value = MagicMock()
            mock_build.return_value = mock_layout
            mock_exporter_cls.Success = 0
            exporter_mock = MagicMock()
            exporter_mock.exportToPdf.return_value = (0, "")  # Success tuple
            mock_exporter_cls.return_value = exporter_mock
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
            output_path="/tmp/qfit_test_atlas.pdf",
            on_finished=None,
        )
        with patch("qfit.atlas_export_task.build_atlas_layout") as mock_build, \
             patch("os.path.exists", return_value=True), \
             patch("qfit.atlas_export_task.QgsLayoutExporter") as mock_exporter_cls:
            mock_layout = MagicMock()
            mock_layout.atlas.return_value = MagicMock()
            mock_build.return_value = mock_layout
            mock_exporter_cls.Success = 0
            exporter_mock = MagicMock()
            exporter_mock.exportToPdf.return_value = (0, "")  # Success tuple
            mock_exporter_cls.return_value = exporter_mock
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
             patch("os.replace"), \
             patch("os.makedirs"):
            _run_task(task)
        layer.setSubsetString.assert_not_called()
        self.assertIsNotNone(received.get("output_path"))


if __name__ == "__main__":
    unittest.main()
