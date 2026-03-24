"""Tests for StravaFetchTask.

These tests exercise the task logic without a live QGIS instance by
subclassing StravaFetchTask and stubbing out the QgsTask infrastructure
(``isCanceled``, ``finished``).
"""

import unittest
from unittest.mock import MagicMock, patch

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
sys.modules.setdefault("qgis", _qgis)
sys.modules.setdefault("qgis.core", _qgis_core)

from qfit.fetch_task import StravaFetchTask  # noqa: E402  (import after stub)


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

class TestStravaFetchTaskSuccess(unittest.TestCase):
    def setUp(self):
        self.received = {}

        def on_finished(**kwargs):
            self.received.update(kwargs)

        mock_activity = MagicMock()
        mock_activity.geometry_source = "summary_polyline"

        self.mock_client = MagicMock()
        self.mock_client.fetch_activities.return_value = [mock_activity]
        self.mock_client.last_stream_enrichment_stats = {}
        self.mock_client.last_rate_limit = None

        self.task = StravaFetchTask(
            client=self.mock_client,
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

    def test_fetch_activities_called_with_correct_params(self):
        _run_task(self.task)
        self.mock_client.fetch_activities.assert_called_once_with(
            per_page=200,
            max_pages=0,
            before=None,
            after=None,
            use_detailed_streams=False,
            max_detailed_activities=0,
        )


class TestStravaFetchTaskError(unittest.TestCase):
    def setUp(self):
        self.received = {}

        def on_finished(**kwargs):
            self.received.update(kwargs)

        from qfit.strava_client import StravaClientError

        self.mock_client = MagicMock()
        self.mock_client.fetch_activities.side_effect = StravaClientError("rate limit hit")

        self.task = StravaFetchTask(
            client=self.mock_client,
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


class TestStravaFetchTaskCancellation(unittest.TestCase):
    def setUp(self):
        self.received = {}

        def on_finished(**kwargs):
            self.received.update(kwargs)

        mock_activity = MagicMock()
        mock_activity.geometry_source = "summary_polyline"

        self.mock_client = MagicMock()
        self.mock_client.fetch_activities.return_value = [mock_activity]

        self.task = StravaFetchTask(
            client=self.mock_client,
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


class TestStravaFetchTaskNoCallback(unittest.TestCase):
    """finished() must not raise even if on_finished is None."""

    def test_finished_without_callback(self):
        mock_client = MagicMock()
        mock_client.fetch_activities.return_value = []
        task = StravaFetchTask(
            client=mock_client,
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


class TestStravaFetchTaskUnexpectedError(unittest.TestCase):
    """The worker-thread safety net catches unexpected errors and reports them."""

    def test_unexpected_exception_caught_and_reported(self):
        received = {}
        mock_client = MagicMock()
        mock_client.fetch_activities.side_effect = ValueError("bad data")

        task = StravaFetchTask(
            client=mock_client,
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


if __name__ == "__main__":
    unittest.main()
