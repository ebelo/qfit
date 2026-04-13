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
            "qfit.analysis.application.analysis_controller.build_analysis_request",
            return_value="request",
        ) as build_request:
            request = self.controller.build_request(
                "Heatmap",
                "starts-layer",
                selection_state="selection-state",
                activities_layer="activities-layer",
                points_layer="points-layer",
            )

        self.assertEqual(request, "request")
        build_request.assert_called_once_with(
            analysis_mode="Heatmap",
            starts_layer="starts-layer",
            selection_state="selection-state",
            activities_layer="activities-layer",
            points_layer="points-layer",
        )

    def test_build_request_keeps_selection_state(self):
        selection_state = ActivitySelectionState(query=ActivityQuery(search_text="gravel"), filtered_count=4)

        request = self.controller.build_request("None", "starts-layer", selection_state)

        self.assertIs(request.selection_state, selection_state)

    def test_run_request_returns_empty_result_for_non_matching_mode(self):
        request = self.controller.build_request("None", object())

        with patch(
            "qfit.analysis.application.analysis_controller.execute_analysis_request",
            return_value="result",
        ) as execute_request:
            result = self.controller.run_request(request)

        self.assertEqual(result, "result")
        execute_request.assert_called_once_with(
            build_request=self.controller.build_request,
            request=request,
            legacy_kwargs={},
        )

    def test_run_request_returns_empty_result_without_starts_layer(self):
        request = self.controller.build_request(
            FREQUENT_STARTING_POINTS_MODE,
            None,
        )

        with patch(
            "qfit.analysis.application.analysis_controller.execute_analysis_request",
            return_value="result",
        ) as execute_request:
            result = self.controller.run_request(request)

        self.assertEqual(result, "result")
        execute_request.assert_called_once_with(
            build_request=self.controller.build_request,
            request=request,
            legacy_kwargs={},
        )

    def test_run_request_reports_no_matches(self):
        request = self.controller.build_request(
            FREQUENT_STARTING_POINTS_MODE,
            object(),
        )

        with patch(
            "qfit.analysis.application.analysis_controller.execute_analysis_request",
            return_value="result",
        ) as execute_request:
            result = self.controller.run_request(request)

        self.assertEqual(result, "result")
        execute_request.assert_called_once_with(
            build_request=self.controller.build_request,
            request=request,
            legacy_kwargs={},
        )

    def test_run_request_returns_layer_for_matching_mode(self):
        request = self.controller.build_request(
            FREQUENT_STARTING_POINTS_MODE,
            object(),
        )
        built_result = object()

        with patch(
            "qfit.analysis.application.analysis_controller.execute_analysis_request",
            return_value=built_result,
        ) as execute_request:
            result = self.controller.run_request(request)

        self.assertIs(result, built_result)
        execute_request.assert_called_once_with(
            build_request=self.controller.build_request,
            request=request,
            legacy_kwargs={},
        )

    def test_run_delegates_to_dispatch_helper(self):
        request = self.controller.build_request(
            FREQUENT_STARTING_POINTS_MODE,
            "starts-layer",
            activities_layer="activities-layer",
            points_layer="points-layer",
        )

        with patch(
            "qfit.analysis.application.analysis_controller.execute_analysis_request",
            return_value="result",
        ) as execute_request:
            result = self.controller.run(request)

        self.assertEqual(result, "result")
        execute_request.assert_called_once_with(
            build_request=self.controller.build_request,
            request=request,
            legacy_kwargs={},
        )

    def test_run_builds_request_via_execution_use_case_when_request_missing(self):
        with patch(
            "qfit.analysis.application.analysis_controller.execute_analysis_request",
            return_value="result",
        ) as execute_request:
            result = self.controller.run(
                analysis_mode="Heatmap",
                starts_layer="starts-layer",
                activities_layer="activities-layer",
                points_layer="points-layer",
            )

        self.assertEqual(result, "result")
        execute_request.assert_called_once_with(
            build_request=self.controller.build_request,
            request=None,
            legacy_kwargs={
                "analysis_mode": "Heatmap",
                "starts_layer": "starts-layer",
                "activities_layer": "activities-layer",
                "points_layer": "points-layer",
            },
        )

    def test_run_request_returns_empty_result_without_heatmap_layers(self):
        request = self.controller.build_request(
            HEATMAP_MODE,
            None,
            activities_layer=None,
            points_layer=None,
        )

        with patch(
            "qfit.analysis.application.analysis_controller.execute_analysis_request",
            return_value="result",
        ) as execute_request:
            result = self.controller.run_request(request)

        self.assertEqual(result, "result")
        execute_request.assert_called_once_with(
            build_request=self.controller.build_request,
            request=request,
            legacy_kwargs={},
        )

    def test_run_request_reports_no_heatmap_matches(self):
        request = self.controller.build_request(
            HEATMAP_MODE,
            None,
            activities_layer=object(),
            points_layer=None,
        )

        with patch(
            "qfit.analysis.application.analysis_controller.execute_analysis_request",
            return_value="result",
        ) as execute_request:
            result = self.controller.run_request(request)

        self.assertEqual(result, "result")
        execute_request.assert_called_once_with(
            build_request=self.controller.build_request,
            request=request,
            legacy_kwargs={},
        )

    def test_run_request_returns_heatmap_layer(self):
        request = self.controller.build_request(
            HEATMAP_MODE,
            None,
            activities_layer=object(),
            points_layer=object(),
        )
        built_result = object()

        with patch(
            "qfit.analysis.application.analysis_controller.execute_analysis_request",
            return_value=built_result,
        ) as execute_request:
            result = self.controller.run_request(request)

        self.assertIs(result, built_result)
        execute_request.assert_called_once_with(
            build_request=self.controller.build_request,
            request=request,
            legacy_kwargs={},
        )


if __name__ == "__main__":
    unittest.main()
