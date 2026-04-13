import unittest

from tests import _path  # noqa: F401
from qfit.activities.application.activity_selection_state import ActivitySelectionState
from qfit.activities.domain.activity_query import ActivityQuery
from qfit.analysis.application.analysis_request_builder import (
    ApplyAnalysisConfigurationInputs,
    RunAnalysisCurrentInputs,
    RunAnalysisRequestInputs,
    build_apply_analysis_configuration_inputs,
    build_run_analysis_current_inputs,
    build_run_analysis_request,
    build_run_analysis_request_inputs,
)


class TestAnalysisRequestBuilder(unittest.TestCase):
    def test_build_apply_analysis_configuration_inputs_keeps_overrides(self):
        current_selection_state = ActivitySelectionState(query=ActivityQuery(search_text="current"), filtered_count=1)
        selection_state = ActivitySelectionState(query=ActivityQuery(search_text="override"), filtered_count=4)

        inputs = build_apply_analysis_configuration_inputs(
            current_mode="Most frequent starting points",
            current_starts_layer="current-starts-layer",
            current_selection_state=current_selection_state,
            analysis_mode="Heatmap",
            starts_layer="starts-layer",
            selection_state=selection_state,
        )

        self.assertIsInstance(inputs, ApplyAnalysisConfigurationInputs)
        self.assertEqual(inputs.analysis_mode, "Heatmap")
        self.assertEqual(inputs.starts_layer, "starts-layer")
        self.assertIs(inputs.selection_state, selection_state)

    def test_build_apply_analysis_configuration_inputs_defaults_to_current_values(self):
        current_selection_state = ActivitySelectionState(query=ActivityQuery(search_text="current"), filtered_count=2)

        inputs = build_apply_analysis_configuration_inputs(
            current_mode="Most frequent starting points",
            current_starts_layer="current-starts-layer",
            current_selection_state=current_selection_state,
        )

        self.assertEqual(inputs.analysis_mode, "Most frequent starting points")
        self.assertEqual(inputs.starts_layer, "current-starts-layer")
        self.assertIs(inputs.selection_state, current_selection_state)

    def test_build_apply_analysis_configuration_inputs_defaults_empty_state(self):
        inputs = build_apply_analysis_configuration_inputs()

        self.assertEqual(inputs.analysis_mode, "")
        self.assertIsNone(inputs.starts_layer)
        self.assertEqual(inputs.selection_state.filtered_count, 0)

    def test_build_run_analysis_current_inputs_keeps_inputs(self):
        current = build_run_analysis_current_inputs(
            activities_layer="activities-layer",
            points_layer="points-layer",
        )

        self.assertIsInstance(current, RunAnalysisCurrentInputs)
        self.assertEqual(current.activities_layer, "activities-layer")
        self.assertEqual(current.points_layer, "points-layer")

    def test_build_run_analysis_request_inputs_keeps_inputs(self):
        selection_state = ActivitySelectionState(query=ActivityQuery(search_text="gravel"), filtered_count=4)

        inputs = build_run_analysis_request_inputs(
            current=RunAnalysisCurrentInputs(
                activities_layer="activities-layer",
                points_layer="points-layer",
            ),
            analysis_mode="Heatmap",
            starts_layer="starts-layer",
            selection_state=selection_state,
        )

        self.assertIsInstance(inputs, RunAnalysisRequestInputs)
        self.assertEqual(inputs.analysis_mode, "Heatmap")
        self.assertEqual(inputs.activities_layer, "activities-layer")
        self.assertEqual(inputs.starts_layer, "starts-layer")
        self.assertEqual(inputs.points_layer, "points-layer")
        self.assertIs(inputs.selection_state, selection_state)

    def test_build_run_analysis_request_inputs_defaults_empty_values(self):
        inputs = build_run_analysis_request_inputs()

        self.assertEqual(inputs.analysis_mode, "")
        self.assertIsNone(inputs.activities_layer)
        self.assertIsNone(inputs.starts_layer)
        self.assertIsNone(inputs.points_layer)
        self.assertEqual(inputs.selection_state.filtered_count, 0)

    def test_build_run_analysis_request_keeps_inputs(self):
        selection_state = ActivitySelectionState(query=ActivityQuery(search_text="gravel"), filtered_count=4)

        request = build_run_analysis_request(
            RunAnalysisRequestInputs(
                analysis_mode="Heatmap",
                activities_layer="activities-layer",
                starts_layer="starts-layer",
                points_layer="points-layer",
                selection_state=selection_state,
            )
        )

        self.assertEqual(request.analysis_mode, "Heatmap")
        self.assertEqual(request.activities_layer, "activities-layer")
        self.assertEqual(request.starts_layer, "starts-layer")
        self.assertEqual(request.points_layer, "points-layer")
        self.assertIs(request.selection_state, selection_state)

    def test_build_run_analysis_request_defaults_empty_values(self):
        request = build_run_analysis_request(RunAnalysisRequestInputs())

        self.assertEqual(request.analysis_mode, "")
        self.assertIsNone(request.activities_layer)
        self.assertIsNone(request.starts_layer)
        self.assertIsNone(request.points_layer)
        self.assertEqual(request.selection_state.filtered_count, 0)


if __name__ == "__main__":
    unittest.main()
