import unittest

from tests import _path  # noqa: F401

from qfit.activities.application.layer_summary import (
    build_loaded_activities_summary,
    build_stored_activities_summary,
)


class LoadedActivitiesSummaryTests(unittest.TestCase):
    def test_builds_loaded_activities_summary_text(self):
        self.assertEqual(
            build_loaded_activities_summary(total_activities=12, last_sync_date="2026-04-12"),
            "12 activities loaded (last sync: 2026-04-12)",
        )

    def test_preserves_unknown_last_sync_text(self):
        self.assertEqual(
            build_loaded_activities_summary(total_activities=0, last_sync_date="unknown"),
            "0 activities loaded (last sync: unknown)",
        )


class StoredActivitiesSummaryTests(unittest.TestCase):
    def test_builds_stored_activities_summary_text(self):
        self.assertEqual(
            build_stored_activities_summary(total_activities=12, last_sync_date="2026-04-12"),
            "12 activities stored in database (last sync: 2026-04-12)",
        )

    def test_preserves_unknown_last_sync_text(self):
        self.assertEqual(
            build_stored_activities_summary(total_activities=0, last_sync_date="unknown"),
            "0 activities stored in database (last sync: unknown)",
        )


if __name__ == "__main__":
    unittest.main()
