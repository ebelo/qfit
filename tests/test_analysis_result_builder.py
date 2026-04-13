import unittest

from tests import _path  # noqa: F401
from qfit.analysis.application.analysis_result_builder import (
    build_activity_heatmap_result,
    build_empty_analysis_result,
    build_frequent_start_points_result,
)


class TestAnalysisResultBuilder(unittest.TestCase):
    def test_build_empty_analysis_result(self):
        result = build_empty_analysis_result()

        self.assertEqual(result.status, "")
        self.assertIsNone(result.layer)

    def test_build_frequent_start_points_result_reports_empty(self):
        result = build_frequent_start_points_result(None, [])

        self.assertEqual(
            result.status,
            "No frequent starting points matched the current filters",
        )
        self.assertIsNone(result.layer)

    def test_build_frequent_start_points_result_reports_success(self):
        layer = object()

        result = build_frequent_start_points_result(layer, [object(), object()])

        self.assertEqual(
            result.status,
            "Showing top 2 frequent starting-point clusters",
        )
        self.assertIs(result.layer, layer)

    def test_build_activity_heatmap_result_reports_empty(self):
        result = build_activity_heatmap_result(None, 0)

        self.assertEqual(
            result.status,
            "No activity heatmap data matched the current filters",
        )
        self.assertIsNone(result.layer)

    def test_build_activity_heatmap_result_reports_success(self):
        layer = object()

        result = build_activity_heatmap_result(layer, 42)

        self.assertEqual(
            result.status,
            "Showing activity heatmap from 42 sampled route points",
        )
        self.assertIs(result.layer, layer)


if __name__ == "__main__":
    unittest.main()
