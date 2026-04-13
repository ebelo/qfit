import unittest

from tests import _path  # noqa: F401
from qfit.activities.application.activity_selection_state import ActivitySelectionState
from qfit.activities.domain.activity_query import ActivityQuery
from qfit.analysis.application.analysis_request_builder import (
    RunAnalysisRequestInputs,
    build_run_analysis_request,
)


class TestAnalysisRequestBuilder(unittest.TestCase):
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
