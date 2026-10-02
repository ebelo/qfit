import importlib.util
import sys
import unittest
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, patch

from tests import _path  # noqa: F401
from tests.test_store_task_pure import _FakeQgsTask
from qfit.analysis.domain.route_density import HeatmapCancelled


class RouteHeatmapTaskTests(unittest.TestCase):
    def setUp(self):
        core = ModuleType("qgis.core")
        core.QgsTask = _FakeQgsTask
        spec = importlib.util.spec_from_file_location(
            "qfit.analysis.infrastructure.route_heatmap_task_pure_test",
            Path(__file__).parents[1] / "analysis/infrastructure/route_heatmap_task.py")
        self.module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {"qgis.core": core}):
            spec.loader.exec_module(self.module)

    def test_success_passes_cancellation_progress_and_artifact(self):
        callback = Mock()
        task = self.module.RouteHeatmapTask("request", callback)
        def build(request, cancelled, progress):
            self.assertEqual(request, "request")
            self.assertFalse(cancelled())
            progress(55)
            return "artifact"
        with patch.object(self.module, "build_route_heatmap", side_effect=build):
            self.assertTrue(task.run())
        self.assertEqual(task.progress, 55)
        task.finished(True)
        callback.assert_called_once_with(task, "artifact", None, False)

    def test_failure_and_cancellation_are_distinct(self):
        for failure, cancelled, error in ((RuntimeError("disk full"), False, "disk full"),
                                          (HeatmapCancelled(), True, None)):
            with self.subTest(cancelled=cancelled):
                callback = Mock()
                task = self.module.RouteHeatmapTask("request", callback)
                if cancelled:
                    task.cancel()
                with patch.object(self.module, "build_route_heatmap", side_effect=failure):
                    self.assertFalse(task.run())
                task.finished(False)
                callback.assert_called_once_with(task, None, error, cancelled)

    def test_cancel_after_computation_does_not_publish_to_dock(self):
        task = self.module.RouteHeatmapTask("request", Mock())
        task.cancel()
        with patch.object(self.module, "build_route_heatmap", return_value="artifact"):
            self.assertFalse(task.run())
        task.finished(False)
        task._on_finished.assert_called_once_with(task, "artifact", None, True)
