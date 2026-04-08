import unittest
from unittest.mock import patch

from tests import _path  # noqa: F401
from qfit.analysis.application.analysis_controller import (
    AnalysisController,
    FREQUENT_STARTING_POINTS_MODE,
)


class TestAnalysisController(unittest.TestCase):
    def setUp(self):
        self.controller = AnalysisController()

    def test_build_request_returns_dataclass(self):
        request = self.controller.build_request("None", "starts-layer")

        self.assertEqual(request.analysis_mode, "None")
        self.assertEqual(request.starts_layer, "starts-layer")

    def test_run_request_returns_empty_result_for_non_matching_mode(self):
        request = self.controller.build_request("None", object())

        result = self.controller.run_request(request)

        self.assertEqual(result.status, "")
        self.assertIsNone(result.layer)

    def test_run_request_returns_empty_result_without_starts_layer(self):
        request = self.controller.build_request(
            FREQUENT_STARTING_POINTS_MODE,
            None,
        )

        result = self.controller.run_request(request)

        self.assertEqual(result.status, "")
        self.assertIsNone(result.layer)

    def test_run_request_reports_no_matches(self):
        request = self.controller.build_request(
            FREQUENT_STARTING_POINTS_MODE,
            object(),
        )

        with patch(
            "qfit.analysis.application.analysis_controller._build_frequent_start_points_layer",
            return_value=(None, []),
        ):
            result = self.controller.run_request(request)

        self.assertEqual(
            result.status,
            "No frequent starting points matched the current filters",
        )
        self.assertIsNone(result.layer)

    def test_run_request_returns_layer_for_matching_mode(self):
        request = self.controller.build_request(
            FREQUENT_STARTING_POINTS_MODE,
            object(),
        )
        layer = object()

        with patch(
            "qfit.analysis.application.analysis_controller._build_frequent_start_points_layer",
            return_value=(layer, [object(), object()]),
        ):
            result = self.controller.run_request(request)

        self.assertEqual(
            result.status,
            "Showing top 2 frequent starting-point clusters",
        )
        self.assertIs(result.layer, layer)


if __name__ == "__main__":
    unittest.main()
