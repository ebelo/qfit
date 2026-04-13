import unittest

from tests import _path  # noqa: F401
from qfit.analysis.application.analysis_status_messages import (
    build_activity_heatmap_empty_status,
    build_activity_heatmap_success_status,
    build_frequent_start_points_empty_status,
    build_frequent_start_points_success_status,
)


class TestAnalysisStatusMessages(unittest.TestCase):
    def test_build_frequent_start_points_empty_status(self):
        self.assertEqual(
            build_frequent_start_points_empty_status(),
            "No frequent starting points matched the current filters",
        )

    def test_build_frequent_start_points_success_status(self):
        self.assertEqual(
            build_frequent_start_points_success_status(2),
            "Showing top 2 frequent starting-point clusters",
        )

    def test_build_activity_heatmap_empty_status(self):
        self.assertEqual(
            build_activity_heatmap_empty_status(),
            "No activity heatmap data matched the current filters",
        )

    def test_build_activity_heatmap_success_status(self):
        self.assertEqual(
            build_activity_heatmap_success_status(42),
            "Showing activity heatmap from 42 sampled route points",
        )


if __name__ == "__main__":
    unittest.main()
