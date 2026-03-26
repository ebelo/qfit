"""Tests for FetchResultService and FetchResult."""
import unittest
from unittest.mock import MagicMock

from tests import _path  # noqa: F401

from qfit.fetch_result_service import FetchResult, FetchResultService


# ---------------------------------------------------------------------------
# FetchResult – dataclass and property tests
# ---------------------------------------------------------------------------


class FetchResultDefaultsTests(unittest.TestCase):
    def test_default_values(self):
        result = FetchResult()
        self.assertEqual(result.activities, [])
        self.assertIsNone(result.error)
        self.assertFalse(result.cancelled)
        self.assertEqual(result.metadata, {})
        self.assertEqual(result.status_text, "")

    def test_ok_is_true_by_default(self):
        self.assertTrue(FetchResult().ok)


class FetchResultCancelledTests(unittest.TestCase):
    def setUp(self):
        self.result = FetchResult(cancelled=True)

    def test_ok_is_false(self):
        self.assertFalse(self.result.ok)

    def test_activity_count_is_zero(self):
        self.assertEqual(self.result.activity_count, 0)


class FetchResultErrorTests(unittest.TestCase):
    def setUp(self):
        self.result = FetchResult(error="rate limited")

    def test_ok_is_false(self):
        self.assertFalse(self.result.ok)

    def test_activity_count_is_zero(self):
        self.assertEqual(self.result.activity_count, 0)


class FetchResultSuccessTests(unittest.TestCase):
    def setUp(self):
        self.result = FetchResult(
            activities=["a1", "a2", "a3"],
            metadata={
                "detailed_count": 2,
                "today_str": "2026-03-26",
            },
            status_text="Fetched 3 activities",
        )

    def test_ok_is_true(self):
        self.assertTrue(self.result.ok)

    def test_activity_count(self):
        self.assertEqual(self.result.activity_count, 3)

    def test_detailed_count(self):
        self.assertEqual(self.result.detailed_count, 2)

    def test_today_str(self):
        self.assertEqual(self.result.today_str, "2026-03-26")

    def test_count_label_text(self):
        text = self.result.count_label_text
        self.assertIn("3 activities loaded", text)
        self.assertIn("2026-03-26", text)
        self.assertIn("detailed tracks: 2", text)


# ---------------------------------------------------------------------------
# FetchResultService.build_result
# ---------------------------------------------------------------------------


class BuildResultCancelledTests(unittest.TestCase):
    def setUp(self):
        self.sync = MagicMock()
        self.service = FetchResultService(self.sync)
        self.result = self.service.build_result(
            activities=None, error=None, cancelled=True, provider=MagicMock(),
        )

    def test_cancelled_flag(self):
        self.assertTrue(self.result.cancelled)

    def test_status_text(self):
        self.assertEqual(self.result.status_text, "Fetch cancelled.")

    def test_ok_is_false(self):
        self.assertFalse(self.result.ok)

    def test_sync_controller_not_called(self):
        self.sync.build_sync_metadata.assert_not_called()


class BuildResultErrorTests(unittest.TestCase):
    def setUp(self):
        self.sync = MagicMock()
        self.service = FetchResultService(self.sync)
        self.result = self.service.build_result(
            activities=None, error="Connection timeout", cancelled=False,
            provider=MagicMock(),
        )

    def test_error_stored(self):
        self.assertEqual(self.result.error, "Connection timeout")

    def test_status_text(self):
        self.assertEqual(self.result.status_text, "Strava fetch failed")

    def test_ok_is_false(self):
        self.assertFalse(self.result.ok)

    def test_sync_controller_not_called(self):
        self.sync.build_sync_metadata.assert_not_called()


class BuildResultSuccessTests(unittest.TestCase):
    def setUp(self):
        self.sync = MagicMock()
        self.sync.build_sync_metadata.return_value = {
            "detailed_count": 5,
            "today_str": "2026-03-26",
            "fetched_count": 10,
        }
        self.sync.fetch_status_text.return_value = "Fetched 10 from Strava"
        self.provider = MagicMock()
        self.activities = list(range(10))
        self.service = FetchResultService(self.sync)
        self.result = self.service.build_result(
            activities=self.activities, error=None, cancelled=False,
            provider=self.provider,
        )

    def test_ok_is_true(self):
        self.assertTrue(self.result.ok)

    def test_activities_stored(self):
        self.assertEqual(self.result.activities, self.activities)

    def test_metadata_stored(self):
        self.assertEqual(self.result.metadata["detailed_count"], 5)

    def test_status_text_from_sync_controller(self):
        self.assertEqual(self.result.status_text, "Fetched 10 from Strava")

    def test_sync_controller_called_with_args(self):
        self.sync.build_sync_metadata.assert_called_once_with(
            self.activities, self.provider,
        )
        self.sync.fetch_status_text.assert_called_once_with(
            self.provider, 10, 5,
        )

    def test_count_label_text(self):
        text = self.result.count_label_text
        self.assertIn("10 activities loaded", text)
        self.assertIn("2026-03-26", text)
        self.assertIn("detailed tracks: 5", text)


if __name__ == "__main__":
    unittest.main()
