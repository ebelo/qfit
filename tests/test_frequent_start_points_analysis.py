import unittest
from unittest.mock import patch

from tests import _path  # noqa: F401
from qfit.analysis.application.frequent_start_points_analysis import (
    run_frequent_start_points_analysis,
)


class TestFrequentStartPointsAnalysis(unittest.TestCase):
    def test_run_frequent_start_points_analysis_returns_empty_result_without_layer(self):
        with patch(
            "qfit.analysis.application.frequent_start_points_analysis.build_empty_analysis_result",
            return_value="result",
        ) as build_empty:
            result = run_frequent_start_points_analysis(None)

        self.assertEqual(result, "result")
        build_empty.assert_called_once_with()

    def test_run_frequent_start_points_analysis_builds_result_from_layer_output(self):
        clusters = [object(), object()]

        with patch(
            "qfit.analysis.application.frequent_start_points_analysis._build_frequent_start_points_layer",
            return_value=("layer", clusters),
        ) as build_layer, patch(
            "qfit.analysis.application.frequent_start_points_analysis.build_frequent_start_points_result",
            return_value="result",
        ) as build_result:
            result = run_frequent_start_points_analysis("starts-layer")

        self.assertEqual(result, "result")
        build_layer.assert_called_once_with("starts-layer")
        build_result.assert_called_once_with("layer", clusters)


if __name__ == "__main__":
    unittest.main()
