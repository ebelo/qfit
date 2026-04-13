import unittest
from unittest.mock import patch

from tests import _path  # noqa: F401
from qfit.activities.application.activity_selection_state import ActivitySelectionState
from qfit.activities.domain.activity_query import ActivityQuery
from qfit.analysis.application.analysis_policy_facade import (
    build_analysis_controller_request,
    run_analysis_controller_request,
)


class TestAnalysisPolicyFacade(unittest.TestCase):
    def test_build_analysis_controller_request_delegates_to_build_use_case(self):
        selection_state = ActivitySelectionState(query=ActivityQuery(search_text="gravel"), filtered_count=4)

        with patch(
            "qfit.analysis.application.analysis_policy_facade.build_analysis_request",
            return_value="request",
        ) as build_request:
            request = build_analysis_controller_request(
                analysis_mode="Heatmap",
                starts_layer="starts-layer",
                selection_state=selection_state,
                activities_layer="activities-layer",
                points_layer="points-layer",
            )

        self.assertEqual(request, "request")
        build_request.assert_called_once_with(
            analysis_mode="Heatmap",
            starts_layer="starts-layer",
            selection_state=selection_state,
            activities_layer="activities-layer",
            points_layer="points-layer",
        )

    def test_run_analysis_controller_request_delegates_to_execution_use_case(self):
        request = object()

        with patch(
            "qfit.analysis.application.analysis_policy_facade.execute_analysis_request",
            return_value="result",
        ) as execute_request:
            result = run_analysis_controller_request(
                request=request,
                legacy_kwargs={"analysis_mode": "Heatmap"},
            )

        self.assertEqual(result, "result")
        execute_request.assert_called_once_with(
            build_request=build_analysis_controller_request,
            request=request,
            legacy_kwargs={"analysis_mode": "Heatmap"},
        )


if __name__ == "__main__":
    unittest.main()
