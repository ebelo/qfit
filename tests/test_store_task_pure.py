import importlib.util
import sys
import unittest
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock, patch


class _FakeQgsTask:
    CanCancel = 1

    def __init__(self, description, flags=0):
        self.description = description
        self.flags = flags
        self._canceled = False

    def isCanceled(self):
        return self._canceled

    def cancel(self):
        self._canceled = True


class TestStoreTaskPure(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        qgis_mod = ModuleType("qgis")
        qgis_core = ModuleType("qgis.core")
        qgis_core.QgsTask = _FakeQgsTask
        qgis_mod.core = qgis_core

        load_workflow_stub = ModuleType("qfit.activities.application.load_workflow")
        load_workflow_stub.LoadWorkflowService = object
        load_workflow_stub.LoadResult = object
        load_workflow_stub.StoreActivitiesRequest = object

        module_path = (
            Path(__file__).resolve().parents[1]
            / "activities"
            / "application"
            / "store_task.py"
        )
        spec = importlib.util.spec_from_file_location(
            "qfit.activities.application.store_task_testmod", module_path
        )
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None

        with patch.dict(
            sys.modules,
            {
                "qgis": qgis_mod,
                "qgis.core": qgis_core,
                "qfit.activities.application.load_workflow": load_workflow_stub,
            },
            clear=False,
        ):
            spec.loader.exec_module(module)
        cls.module = module

    def test_run_calls_workflow_and_finishes_with_result(self):
        workflow = MagicMock()
        result = SimpleNamespace(status="ok")
        workflow.write_database_request.return_value = result
        finished = MagicMock()
        task = self.module.build_store_task(workflow, "request", on_finished=finished)

        ok = task.run()
        task.finished(ok)

        self.assertTrue(ok)
        workflow.write_database_request.assert_called_once_with("request")
        finished.assert_called_once_with(result, None, False)

    def test_run_reports_error_message(self):
        workflow = MagicMock()
        workflow.write_database_request.side_effect = RuntimeError("boom")
        finished = MagicMock()
        task = self.module.build_store_task(workflow, "request", on_finished=finished)

        ok = task.run()
        task.finished(ok)

        self.assertFalse(ok)
        finished.assert_called_once()
        self.assertIsNone(finished.call_args.args[0])
        self.assertIn("boom", finished.call_args.args[1])
        self.assertFalse(finished.call_args.args[2])


if __name__ == "__main__":
    unittest.main()
