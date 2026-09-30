import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock

import pytest

from tests import _path  # noqa: F401
from tests.test_store_task_pure import _FakeQgsTask


@pytest.fixture
def task_module(monkeypatch):
    core = ModuleType("qgis.core")
    core.QgsTask = _FakeQgsTask
    monkeypatch.setitem(sys.modules, "qgis.core", core)
    name = "qfit.activities.application.activity_name_refresh_task_pure_test"
    spec = importlib.util.spec_from_file_location(name, Path(__file__).parents[1] /
                                               "activities/application/activity_name_refresh_task.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_task_runs_in_worker_and_reports_success(task_module, monkeypatch):
    workflow = Mock(return_value={"updated": 2})
    monkeypatch.setattr(task_module, "refresh_activity_names", workflow)
    callback = Mock()
    provider = object()
    task = task_module.ActivityNameRefreshTask(provider, "store.gpkg", ("42",), on_finished=callback)
    assert task.run()
    workflow.assert_called_once_with(provider, "store.gpkg", ("42",),
                                     cancelled=task.isCanceled, progress=task._progress)
    task.finished(True)
    callback.assert_called_once_with({"updated": 2}, None, False)


def test_task_reports_failure_without_success(task_module, monkeypatch):
    monkeypatch.setattr(task_module, "refresh_activity_names", Mock(side_effect=RuntimeError("locked")))
    callback = Mock()
    task = task_module.ActivityNameRefreshTask(object(), "store.gpkg", on_finished=callback)
    assert not task.run()
    task.finished(False)
    callback.assert_called_once_with(None, "locked", False)


def test_task_reports_cancel_without_committed_result(task_module, monkeypatch):
    monkeypatch.setattr(task_module, "refresh_activity_names", Mock(side_effect=InterruptedError()))
    callback = Mock()
    task = task_module.ActivityNameRefreshTask(object(), "store.gpkg", on_finished=callback)
    task.cancel()
    assert not task.run()
    task.finished(False)
    callback.assert_called_once_with(None, None, True)


def test_cancellation_after_commit_reports_success(task_module, monkeypatch):
    monkeypatch.setattr(task_module, "refresh_activity_names", Mock(return_value={"updated": 1}))
    callback = Mock()
    task = task_module.ActivityNameRefreshTask(object(), "store.gpkg", on_finished=callback)
    assert task.run()
    task.cancel()
    task.finished(True)
    callback.assert_called_once_with({"updated": 1}, None, False)
