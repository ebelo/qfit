"""Tests for FetchTask.

These tests exercise the task logic without a live QGIS instance by
subclassing FetchTask and stubbing out the QgsTask infrastructure
(``isCanceled``, ``finished``).
"""

import unittest
import importlib
from unittest.mock import MagicMock

from tests import _path  # noqa: F401


# ---------------------------------------------------------------------------
# Minimal stub so tests can import fetch_task without a running QGIS instance.
# ---------------------------------------------------------------------------

class _FakeQgsTask:
    """Minimal stand-in for QgsTask used in unit tests."""

    CanCancel = 1

    def __init__(self, description, flags=0):
        self._cancelled = False

    def isCanceled(self):
        return self._cancelled

    def setProgress(self, value):  # noqa: N802 – matches Qt naming
        pass


# Patch QgsTask before importing the module under test so the import succeeds
# in a non-QGIS environment.
import sys
from types import ModuleType

_qgis_core = ModuleType("qgis.core")
_qgis_core.QgsTask = _FakeQgsTask
_qgis = ModuleType("qgis")
_qgis.core = _qgis_core

_ORIGINAL_QGIS = sys.modules.get("qgis")
_ORIGINAL_QGIS_CORE = sys.modules.get("qgis.core")

sys.modules["qgis"] = _qgis
sys.modules["qgis.core"] = _qgis_core

from qfit.activities.application import fetch_task as fetch_task_module  # noqa: E402  (import after stub)
from qfit.providers.domain import ProviderError  # noqa: E402

fetch_task_module = importlib.reload(fetch_task_module)
FetchTask = fetch_task_module.FetchTask

if _ORIGINAL_QGIS is not None:
    sys.modules["qgis"] = _ORIGINAL_QGIS
else:
    sys.modules.pop("qgis", None)

if _ORIGINAL_QGIS_CORE is not None:
    sys.modules["qgis.core"] = _ORIGINAL_QGIS_CORE
else:
    sys.modules.pop("qgis.core", None)


# ---------------------------------------------------------------------------
# Helper to run a task synchronously (no QGIS event loop needed)
# ---------------------------------------------------------------------------

def _run_task(task):
    """Simulate QGIS task execution: call run() then finished(result)."""
    result = task.run()
    task.finished(result)
    return result


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestFetchTaskSuccess(unittest.TestCase):
    def setUp(self):
        self.received = {}

        def on_finished(**kwargs):
            self.received.update(kwargs)

        mock_activity = MagicMock()
        mock_activity.geometry_source = "summary_polyline"

        self.mock_provider = MagicMock()
        self.mock_provider.fetch_activities.return_value = [mock_activity]
        self.mock_provider.last_stream_enrichment_stats = {}
        self.mock_provider.last_rate_limit = None

        self.task = FetchTask(
            provider=self.mock_provider,
            per_page=200,
            max_pages=0,
            before=None,
            after=None,
            use_detailed_streams=False,
            max_detailed_activities=0,
            on_finished=on_finished,
        )

    def test_run_returns_true_on_success(self):
        result = self.task.run()
        self.assertTrue(result)

    def test_finished_callback_receives_activities(self):
        _run_task(self.task)
        self.assertIsNotNone(self.received.get("activities"))
        self.assertEqual(len(self.received["activities"]), 1)
        self.assertIsNone(self.received.get("error"))
        self.assertFalse(self.received.get("cancelled"))

    def test_finished_callback_receives_provider(self):
        _run_task(self.task)
        self.assertIs(self.received.get("provider"), self.mock_provider)

    def test_fetch_activities_called_with_correct_params(self):
        _run_task(self.task)
        self.mock_provider.fetch_activities.assert_called_once_with(
            per_page=200,
            max_pages=0,
            before=None,
            after=None,
            use_detailed_streams=False,
            max_detailed_activities=0,
            detailed_route_strategy="Missing routes only",
        )


class TestFetchTaskError(unittest.TestCase):
    def setUp(self):
        self.received = {}

        def on_finished(**kwargs):
            self.received.update(kwargs)

        self.mock_provider = MagicMock()
        self.mock_provider.fetch_activities.side_effect = ProviderError("rate limit hit")

        self.task = FetchTask(
            provider=self.mock_provider,
            per_page=200,
            max_pages=0,
            before=None,
            after=None,
            use_detailed_streams=False,
            max_detailed_activities=0,
            on_finished=on_finished,
        )

    def test_run_returns_false_on_error(self):
        result = self.task.run()
        self.assertFalse(result)

    def test_finished_callback_receives_error(self):
        _run_task(self.task)
        self.assertIsNone(self.received.get("activities"))
        self.assertIn("rate limit hit", self.received.get("error", ""))
        self.assertFalse(self.received.get("cancelled"))


class TestFetchTaskCancellation(unittest.TestCase):
    def setUp(self):
        self.received = {}

        def on_finished(**kwargs):
            self.received.update(kwargs)

        mock_activity = MagicMock()
        mock_activity.geometry_source = "summary_polyline"

        self.mock_provider = MagicMock()
        self.mock_provider.fetch_activities.return_value = [mock_activity]

        self.task = FetchTask(
            provider=self.mock_provider,
            per_page=200,
            max_pages=0,
            before=None,
            after=None,
            use_detailed_streams=False,
            max_detailed_activities=0,
            on_finished=on_finished,
        )
        # Simulate cancellation before finished() is called
        self.task._cancelled = True

    def test_finished_callback_sets_cancelled_true(self):
        # run() succeeds but isCanceled() is True → returns False
        result = self.task.run()
        self.assertFalse(result)
        _run_task(self.task)  # calls finished(False)
        self.assertTrue(self.received.get("cancelled"))


class TestFetchTaskNoCallback(unittest.TestCase):
    """finished() must not raise even if on_finished is None."""

    def test_finished_without_callback(self):
        mock_provider = MagicMock()
        mock_provider.fetch_activities.return_value = []
        task = FetchTask(
            provider=mock_provider,
            per_page=200,
            max_pages=0,
            before=None,
            after=None,
            use_detailed_streams=False,
            max_detailed_activities=0,
            on_finished=None,
        )
        # Should not raise
        task.run()
        task.finished(True)


class TestFetchTaskUnexpectedError(unittest.TestCase):
    """The worker-thread safety net catches unexpected errors and reports them."""

    def test_unexpected_exception_caught_and_reported(self):
        received = {}
        mock_provider = MagicMock()
        mock_provider.fetch_activities.side_effect = ValueError("bad data")

        task = FetchTask(
            provider=mock_provider,
            per_page=200,
            max_pages=0,
            before=None,
            after=None,
            use_detailed_streams=False,
            max_detailed_activities=0,
            on_finished=lambda **kw: received.update(kw),
        )
        result = task.run()
        self.assertFalse(result)
        task.finished(result)
        self.assertIn("bad data", received.get("error", ""))


class TestFetchTaskBackwardCompatibility(unittest.TestCase):
    def test_positional_on_finished_argument_still_works(self):
        received = {}
        mock_provider = MagicMock()
        mock_provider.fetch_activities.return_value = []

        task = FetchTask(
            mock_provider,
            200,
            0,
            None,
            None,
            False,
            0,
            lambda **kw: received.update(kw),
        )

        _run_task(task)

        self.assertIn("activities", received)
        mock_provider.fetch_activities.assert_called_once_with(
            per_page=200,
            max_pages=0,
            before=None,
            after=None,
            use_detailed_streams=False,
            max_detailed_activities=0,
            detailed_route_strategy="Missing routes only",
        )


if __name__ == "__main__":
    unittest.main()
