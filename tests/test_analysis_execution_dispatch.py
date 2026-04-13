import unittest
from unittest.mock import patch

from tests import _path  # noqa: F401
from qfit.analysis.application.analysis_controller import (
    FREQUENT_STARTING_POINTS_MODE,
    HEATMAP_MODE,
)
from qfit.analysis.application.analysis_models import RunAnalysisRequest
from qfit.analysis.application.analysis_execution_dispatch import dispatch_analysis_request


class TestAnalysisExecutionDispatch(unittest.TestCase):
    def test_dispatch_analysis_request_routes_frequent_start_points_mode(self):
        request = RunAnalysisRequest(
            analysis_mode=FREQUENT_STARTING_POINTS_MODE,
            starts_layer="starts-layer",
        )

        with patch(
            "qfit.analysis.application.analysis_execution_dispatch.run_frequent_start_points_analysis",
            return_value="result",
        ) as run_analysis:
            result = dispatch_analysis_request(request)

        self.assertEqual(result, "result")
        run_analysis.assert_called_once_with("starts-layer")

    def test_dispatch_analysis_request_routes_heatmap_mode(self):
        request = RunAnalysisRequest(
            analysis_mode=HEATMAP_MODE,
            starts_layer=None,
            activities_layer="activities-layer",
            points_layer="points-layer",
        )

        with patch(
            "qfit.analysis.application.analysis_execution_dispatch.run_activity_heatmap_analysis",
            return_value="result",
        ) as run_analysis:
            result = dispatch_analysis_request(request)

        self.assertEqual(result, "result")
        run_analysis.assert_called_once_with(
            activities_layer="activities-layer",
            points_layer="points-layer",
        )

    def test_dispatch_analysis_request_returns_empty_result_for_unknown_mode(self):
        request = RunAnalysisRequest(
            analysis_mode="Unknown",
            starts_layer=None,
        )

        with patch(
            "qfit.analysis.application.analysis_execution_dispatch.build_empty_analysis_result",
            return_value="result",
        ) as build_empty:
            result = dispatch_analysis_request(request)

        self.assertEqual(result, "result")
        build_empty.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
