import unittest
from unittest.mock import Mock, patch

from tests import _path  # noqa: F401
from qfit.analysis.application.analysis_request_execution import execute_analysis_request


class TestAnalysisRequestExecution(unittest.TestCase):
    def test_execute_analysis_request_dispatches_prebuilt_request(self):
        build_request = Mock()
        request = object()

        with patch(
            "qfit.analysis.application.analysis_request_execution.dispatch_analysis_request",
            return_value="result",
        ) as dispatch_request:
            result = execute_analysis_request(
                build_request=build_request,
                request=request,
            )

        self.assertEqual(result, "result")
        build_request.assert_not_called()
        dispatch_request.assert_called_once_with(request)

    def test_execute_analysis_request_builds_request_from_legacy_kwargs(self):
        request = object()
        build_request = Mock(return_value=request)

        with patch(
            "qfit.analysis.application.analysis_request_execution.dispatch_analysis_request",
            return_value="result",
        ) as dispatch_request:
            result = execute_analysis_request(
                build_request=build_request,
                legacy_kwargs={
                    "analysis_mode": "Heatmap",
                    "starts_layer": "starts-layer",
                    "activities_layer": "activities-layer",
                    "points_layer": "points-layer",
                },
            )

        self.assertEqual(result, "result")
        build_request.assert_called_once_with(
            analysis_mode="Heatmap",
            starts_layer="starts-layer",
            activities_layer="activities-layer",
            points_layer="points-layer",
        )
        dispatch_request.assert_called_once_with(request)


if __name__ == "__main__":
    unittest.main()
