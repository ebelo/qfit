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

    def test_build_request_keeps_selection_state(self):
        selection_state = ActivitySelectionState(query=ActivityQuery(search_text="gravel"), filtered_count=4)

        request = self.controller.build_request("None", "starts-layer", selection_state)

        self.assertIs(request.selection_state, selection_state)

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

    def test_run_request_returns_empty_result_without_heatmap_layers(self):
        request = self.controller.build_request(
            HEATMAP_MODE,
            None,
            activities_layer=None,
            points_layer=None,
        )

        result = self.controller.run_request(request)

        self.assertEqual(result.status, "")
        self.assertIsNone(result.layer)

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
        ):
            result = self.controller.run_request(request)

        self.assertEqual(
            result.status,
            "No activity heatmap data matched the current filters",
        )
        self.assertIsNone(result.layer)

    def test_run_request_returns_heatmap_layer(self):
        request = self.controller.build_request(
            HEATMAP_MODE,
            None,
            activities_layer=object(),
            points_layer=object(),
        )
        layer = object()

        with patch(
            "qfit.analysis.application.analysis_controller._build_activity_heatmap_layer",
            return_value=(layer, 42),
        ):
            result = self.controller.run_request(request)

        self.assertEqual(
            result.status,
            "Showing activity heatmap from 42 sampled route points",
        )
        self.assertIs(result.layer, layer)


if __name__ == "__main__":
    unittest.main()
