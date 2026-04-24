import unittest

from tests import _path  # noqa: F401
from qfit.ui.application.dock_summary_status import build_dock_summary_status


class DockSummaryStatusTests(unittest.TestCase):
    def test_builds_compact_summary_from_existing_status_labels(self):
        self.assertEqual(
            build_dock_summary_status(
                connection_status="Strava connection: connected",
                activity_summary="12 activities stored in database",
                query_summary="Visualize filters currently match 3 activities.",
                workflow_status="Ready",
            ),
            "Strava connection: connected · 12 activities stored in database · "
            "Visualize filters currently match 3 activities. · Ready",
        )

    def test_omits_empty_and_duplicate_parts(self):
        self.assertEqual(
            build_dock_summary_status(
                connection_status="",
                activity_summary="Ready",
                query_summary=None,
                workflow_status="Ready",
            ),
            "Ready",
        )

    def test_falls_back_to_ready_when_all_parts_are_empty(self):
        self.assertEqual(
            build_dock_summary_status(
                connection_status="",
                activity_summary="",
                query_summary=None,
                workflow_status="",
            ),
            "Ready",
        )


if __name__ == "__main__":
    unittest.main()
