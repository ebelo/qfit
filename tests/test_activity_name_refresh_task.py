import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, patch

import unittest

from tests import _path  # noqa: F401
from tests.test_store_task_pure import _FakeQgsTask


class ActivityNameRefreshTaskTests(unittest.TestCase):
    def setUp(self):
        core = ModuleType("qgis.core")
        core.QgsTask = _FakeQgsTask
        name = "qfit.activities.application.activity_name_refresh_task_pure_test"
        spec = importlib.util.spec_from_file_location(
            name, Path(__file__).parents[1] / "activities/application/activity_name_refresh_task.py")
        self.module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {"qgis.core": core}):
            spec.loader.exec_module(self.module)

    def test_worker_success(self):
        workflow = Mock(return_value={"updated": 2})
        callback = Mock()
        provider = object()
        task = self.module.ActivityNameRefreshTask(provider, "store.gpkg", ("42",), on_finished=callback)
        with patch.object(self.module, "refresh_activity_names", workflow):
            self.assertTrue(task.run())
        workflow.assert_called_once_with(provider, "store.gpkg", ("42",),
                                         cancelled=task.isCanceled, progress=task._progress)
        task.finished(True)
        callback.assert_called_once_with({"updated": 2}, None, False)
        task._progress("names", 1, 2)
        self.assertEqual(task.progress, 40)
        task._progress("summaries", 1, None)
        self.assertEqual(task.progress, 30)

    def test_worker_failure(self):
        callback = Mock()
        task = self.module.ActivityNameRefreshTask(object(), "store.gpkg", on_finished=callback)
        with patch.object(self.module, "refresh_activity_names", side_effect=RuntimeError("locked")):
            self.assertFalse(task.run())
        task.finished(False)
        callback.assert_called_once_with(None, "locked", False)

    def test_worker_cancel(self):
        callback = Mock()
        task = self.module.ActivityNameRefreshTask(object(), "store.gpkg", on_finished=callback)
        task.cancel()
        with patch.object(self.module, "refresh_activity_names", side_effect=InterruptedError()):
            self.assertFalse(task.run())
        task.finished(False)
        callback.assert_called_once_with(None, None, True)

    def test_cancel_after_commit_reports_success(self):
        callback = Mock()
        task = self.module.ActivityNameRefreshTask(object(), "store.gpkg", on_finished=callback)
        with patch.object(self.module, "refresh_activity_names", return_value={"updated": 1}):
            self.assertTrue(task.run())
        task.cancel()
        task.finished(True)
        callback.assert_called_once_with({"updated": 1}, None, False)
