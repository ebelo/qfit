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

from qfit.atlas_export_task import AtlasExportTask  # noqa: E402


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
    layer.fields.return_value = MagicMock()
    layer.fields.return_value.indexOf = lambda name: 0  # all fields exist
    return layer


# ---------------------------------------------------------------------------
# Tests: successful export
# ---------------------------------------------------------------------------


class TestAtlasExportTaskSuccess(unittest.TestCase):
    def setUp(self):
        self.received = {}

        def on_finished(**kwargs):
            self.received.update(kwargs)

        self.atlas_layer = _make_atlas_layer(feature_count=5)

        # Make QgsLayoutExporter.exportToPdf return Success (0)
        exporter_instance = MagicMock()
        exporter_instance.exportToPdf.return_value = (0, "")  # Success tuple
        _qgis_core.QgsLayoutExporter.return_value = exporter_instance

        # Make QgsPrintLayout return a usable mock
        layout_mock = MagicMock()
        layout_mock.atlas.return_value = MagicMock()
        layout_mock.pageCollection.return_value.pageCount.return_value = 1
        layout_mock.pageCollection.return_value.page.return_value = MagicMock()
        layout_mock.mapLayers = MagicMock(return_value={})
        _qgis_core.QgsPrintLayout.return_value = layout_mock

        self.task = AtlasExportTask(
            atlas_layer=self.atlas_layer,
            output_path="/tmp/qfit_test_atlas.pdf",
            on_finished=on_finished,
        )

    def test_run_returns_true_on_success(self):
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

            result = self.task.run()

        self.assertTrue(result)

    def test_finished_callback_receives_output_path(self):
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

            _run_task(self.task)

        self.assertEqual(self.received.get("output_path"), "/tmp/qfit_test_atlas.pdf")
        self.assertIsNone(self.received.get("error"))
        self.assertFalse(self.received.get("cancelled"))
        self.assertEqual(self.received.get("page_count"), 5)

    def test_page_count_matches_feature_count(self):
        layer = _make_atlas_layer(feature_count=12)
        received = {}
        task = AtlasExportTask(
            atlas_layer=layer,
            output_path="/tmp/qfit_test_atlas.pdf",
            on_finished=lambda **kw: received.update(kw),
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
            _run_task(task)
        self.assertEqual(received.get("page_count"), 12)


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
        layer = _make_atlas_layer(feature_count=3)
        task = AtlasExportTask(
            atlas_layer=layer,
            output_path="/tmp/qfit_test_atlas.pdf",
            on_finished=lambda **kw: received.update(kw),
        )
        with patch("qfit.atlas_export_task.build_atlas_layout") as mock_build, \
             patch("os.path.exists", return_value=True), \
             patch("qfit.atlas_export_task.QgsLayoutExporter") as mock_exporter_cls:
            mock_layout = MagicMock()
            mock_layout.atlas.return_value = MagicMock()
            mock_build.return_value = mock_layout
            mock_exporter_cls.Success = 0
            exporter_mock = MagicMock()
            exporter_mock.exportToPdf.return_value = (1, "mock export error")  # failure tuple
            mock_exporter_cls.return_value = exporter_mock
            _run_task(task)

        self.assertIsNone(received.get("output_path"))
        self.assertIsNotNone(received.get("error"))
        self.assertIn("error code 1", received["error"])


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
# Tests: subset_string applies visualization filter to atlas layer
# ---------------------------------------------------------------------------


class TestAtlasExportTaskSubsetFilter(unittest.TestCase):
    def test_subset_string_is_applied_and_restored(self):
        """Atlas export applies the provided subset string and restores the original."""
        received = {}
        layer = _make_atlas_layer(feature_count=5)
        layer.subsetString.return_value = "original_subset"
        layer.setSubsetString = MagicMock()

        task = AtlasExportTask(
            atlas_layer=layer,
            output_path="/tmp/qfit_test_atlas.pdf",
            on_finished=lambda **kw: received.update(kw),
            subset_string="activity_type = 'Ride'",
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
            _run_task(task)

        # Should have applied the filter subset, then restored the original
        calls = layer.setSubsetString.call_args_list
        self.assertEqual(calls[0][0][0], "activity_type = 'Ride'")
        self.assertEqual(calls[1][0][0], "original_subset")
        self.assertIsNotNone(received.get("output_path"))

    def test_no_subset_string_does_not_call_set_subset(self):
        """When subset_string=None, setSubsetString is never called."""
        received = {}
        layer = _make_atlas_layer(feature_count=3)
        layer.setSubsetString = MagicMock()

        task = AtlasExportTask(
            atlas_layer=layer,
            output_path="/tmp/qfit_test_atlas.pdf",
            on_finished=lambda **kw: received.update(kw),
            subset_string=None,
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
            _run_task(task)

        layer.setSubsetString.assert_not_called()


if __name__ == "__main__":
    unittest.main()
