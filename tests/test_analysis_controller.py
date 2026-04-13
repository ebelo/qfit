import unittest
from unittest.mock import patch

from tests import _path  # noqa: F401
from qfit.activities.application.activity_selection_state import ActivitySelectionState
from qfit.activities.domain.activity_query import ActivityQuery
from qfit.analysis.application.analysis_controller import (
    AnalysisController,
    FREQUENT_STARTING_POINTS_MODE,
    HEATMAP_MODE,
)


class TestAnalysisController(unittest.TestCase):
    def setUp(self):
        self.controller = AnalysisController()

    def test_build_request_returns_dataclass(self):
        request = self.controller.build_request(
            "None",
            "starts-layer",
            activities_layer="activities-layer",
            points_layer="points-layer",
        )

        self.assertEqual(request.analysis_mode, "None")
        self.assertEqual(request.activities_layer, "activities-layer")
        self.assertEqual(request.starts_layer, "starts-layer")
        self.assertEqual(request.points_layer, "points-layer")

    def test_build_request_delegates_to_request_builder_helper(self):
        with patch(
            "qfit.analysis.application.analysis_request_builder.build_run_analysis_request",
            return_value="request",
        ) as build_request, patch(
            "qfit.analysis.application.analysis_request_builder.build_analysis_controller_request_inputs",
            return_value="request-inputs",
        ) as build_inputs:
            request = self.controller.build_request(
                "Heatmap",
                "starts-layer",
                selection_state="selection-state",
                activities_layer="activities-layer",
                points_layer="points-layer",
            )

        self.assertEqual(request, "request")
        build_inputs.assert_called_once_with(
            analysis_mode="Heatmap",
            starts_layer="starts-layer",
            selection_state="selection-state",
            activities_layer="activities-layer",
            points_layer="points-layer",
        )
        build_request.assert_called_once_with("request-inputs")

    def test_build_request_keeps_selection_state(self):
        selection_state = ActivitySelectionState(query=ActivityQuery(search_text="gravel"), filtered_count=4)

        request = self.controller.build_request("None", "starts-layer", selection_state)

        self.assertIs(request.selection_state, selection_state)

    def test_run_request_returns_empty_result_for_non_matching_mode(self):
        request = self.controller.build_request("None", object())

        with patch(
            "qfit.analysis.application.analysis_controller.build_empty_analysis_result",
            return_value="result",
        ) as build_result:
            result = self.controller.run_request(request)

        self.assertEqual(result, "result")
        build_result.assert_called_once_with()

    def test_run_request_returns_empty_result_without_starts_layer(self):
        request = self.controller.build_request(
            FREQUENT_STARTING_POINTS_MODE,
            None,
        )

        with patch(
            "qfit.analysis.application.analysis_controller.build_empty_analysis_result",
            return_value="result",
        ) as build_result:
            result = self.controller.run_request(request)

        self.assertEqual(result, "result")
        build_result.assert_called_once_with()

    def test_run_request_reports_no_matches(self):
        request = self.controller.build_request(
            FREQUENT_STARTING_POINTS_MODE,
            object(),
        )

        with patch(
            "qfit.analysis.application.analysis_controller._build_frequent_start_points_layer",
            return_value=(None, []),
        ), patch(
            "qfit.analysis.application.analysis_controller.build_frequent_start_points_result",
            return_value="result",
        ) as build_result:
            result = self.controller.run_request(request)

        self.assertEqual(result, "result")
        build_result.assert_called_once_with(None, [])

    def test_run_request_returns_layer_for_matching_mode(self):
        request = self.controller.build_request(
            FREQUENT_STARTING_POINTS_MODE,
            object(),
        )
        layer = object()
        built_result = object()

        with patch(
            "qfit.analysis.application.analysis_controller._build_frequent_start_points_layer",
            return_value=(layer, [object(), object()]),
        ), patch(
            "qfit.analysis.application.analysis_controller.build_frequent_start_points_result",
            return_value=built_result,
        ) as build_result:
            result = self.controller.run_request(request)

        self.assertIs(result, built_result)
        build_result.assert_called_once()

    def test_run_request_returns_empty_result_without_heatmap_layers(self):
        request = self.controller.build_request(
            HEATMAP_MODE,
            None,
            activities_layer=None,
            points_layer=None,
        )

        with patch(
            "qfit.analysis.application.analysis_controller.build_empty_analysis_result",
            return_value="result",
        ) as build_result:
            result = self.controller.run_request(request)

        self.assertEqual(result, "result")
        build_result.assert_called_once_with()

    def test_run_request_reports_no_heatmap_matches(self):
        request = self.controller.build_request(
            HEATMAP_MODE,
            None,
            activities_layer=object(),
            points_layer=None,
        )

        with patch(
            "qfit.analysis.application.analysis_controller._build_activity_heatmap_layer",
            return_value=(None, 0),
        ), patch(
            "qfit.analysis.application.analysis_controller.build_activity_heatmap_result",
            return_value="result",
        ) as build_result:
            result = self.controller.run_request(request)

        self.assertEqual(result, "result")
        build_result.assert_called_once_with(None, 0)

    def test_run_request_returns_heatmap_layer(self):
        request = self.controller.build_request(
            HEATMAP_MODE,
            None,
            activities_layer=object(),
            points_layer=object(),
        )
        layer = object()
        built_result = object()

        with patch(
            "qfit.analysis.application.analysis_controller._build_activity_heatmap_layer",
            return_value=(layer, 42),
        ), patch(
            "qfit.analysis.application.analysis_controller.build_activity_heatmap_result",
            return_value=built_result,
        ) as build_result:
            result = self.controller.run_request(request)

        self.assertIs(result, built_result)
        build_result.assert_called_once_with(layer, 42)


if __name__ == "__main__":
    unittest.main()
