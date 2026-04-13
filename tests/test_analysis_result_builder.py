import unittest

from tests import _path  # noqa: F401
from qfit.analysis.application.analysis_result_builder import (
    build_frequent_start_points_result,
)


class TestAnalysisResultBuilder(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
