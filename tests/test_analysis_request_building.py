import unittest
from unittest.mock import patch

from tests import _path  # noqa: F401
from qfit.activities.application.activity_selection_state import ActivitySelectionState
from qfit.activities.domain.activity_query import ActivityQuery
from qfit.analysis.application.analysis_request_building import build_analysis_workflow


class TestAnalysisRequestBuilding(unittest.TestCase):
    def test_build_analysis_workflow_delegates_to_request_builder_helpers(self):
        selection_state = ActivitySelectionState(query=ActivityQuery(search_text="gravel"), filtered_count=4)

        with patch(
            "qfit.analysis.application.analysis_request_builder.build_analysis_workflow_request_inputs",
            return_value="request-inputs",
        ) as build_inputs, patch(
            "qfit.analysis.application.analysis_request_builder.build_run_analysis_request",
            return_value="request",
        ) as build_request:
            request = build_analysis_workflow(
                analysis_mode="Heatmap",
                starts_layer="starts-layer",
                selection_state=selection_state,
                activities_layer="activities-layer",
                points_layer="points-layer",
            )

        self.assertEqual(request, "request")
        build_inputs.assert_called_once_with(
            analysis_mode="Heatmap",
            starts_layer="starts-layer",
            selection_state=selection_state,
            activities_layer="activities-layer",
            points_layer="points-layer",
        )
        build_request.assert_called_once_with("request-inputs")


if __name__ == "__main__":
    unittest.main()
