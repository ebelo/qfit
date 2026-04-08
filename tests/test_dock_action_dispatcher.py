import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from tests import _path  # noqa: F401
from qfit.activities.application.activity_selection_state import ActivitySelectionState
from qfit.activities.domain.activity_query import ActivityQuery
from qfit.ui.application import (
    ApplyVisualizationAction,
    DockActionDispatcher,
    RunAnalysisAction,
)
from qfit.visualization.application import BackgroundConfig, LayerRefs


class TestDockActionDispatcher(unittest.TestCase):
    def test_dispatch_apply_visualization_routes_through_visual_service(self):
        visual_apply = MagicMock()
        visual_apply.build_request.return_value = "request"
        visual_apply.apply_request.return_value = SimpleNamespace(
            status="Applied current filters",
            background_layer="background-layer",
            background_error="",
        )
        visual_apply.should_update_background.return_value = True
        save_settings = MagicMock()
        run_analysis = MagicMock(return_value="Showing top 2 frequent starting-point clusters")
        dispatcher = DockActionDispatcher(
            visual_apply=visual_apply,
            save_settings=save_settings,
            run_analysis=run_analysis,
        )
        starts_layer = object()
        selection_state = ActivitySelectionState(query=ActivityQuery(), filtered_count=3)
        action = ApplyVisualizationAction(
            layers=LayerRefs(activities=object(), starts=starts_layer),
            selection_state=selection_state,
            style_preset="By activity type",
            temporal_mode="By month",
            background_config=BackgroundConfig(enabled=True, preset_name="Outdoors"),
            analysis_mode="Most frequent starting points",
            starts_layer=starts_layer,
            apply_subset_filters=False,
        )

        result = dispatcher.dispatch(action)

        save_settings.assert_called_once_with()
        visual_apply.build_request.assert_called_once_with(
            layers=action.layers,
            selection_state=selection_state,
            style_preset="By activity type",
            temporal_mode="By month",
            background_config=action.background_config,
            apply_subset_filters=False,
        )
        visual_apply.apply_request.assert_called_once_with("request")
        run_analysis.assert_called_once_with(
            "Most frequent starting points",
            starts_layer,
            selection_state,
        )
        self.assertEqual(
            result.status,
            "Applied current filters. Showing top 2 frequent starting-point clusters",
        )
        self.assertEqual(result.background_layer, "background-layer")
        self.assertEqual(
            result.analysis_status,
            "Showing top 2 frequent starting-point clusters",
        )

    def test_dispatch_run_analysis_skips_background_updates_for_subset_apply(self):
        visual_apply = MagicMock()
        visual_apply.build_request.return_value = "request"
        visual_apply.apply_request.return_value = SimpleNamespace(
            status="Applied current filters",
            background_layer="ignored-layer",
            background_error="ignored-error",
        )
        visual_apply.should_update_background.return_value = False
        dispatcher = DockActionDispatcher(
            visual_apply=visual_apply,
            save_settings=MagicMock(),
            run_analysis=MagicMock(return_value=""),
        )
        action = RunAnalysisAction(
            layers=LayerRefs(activities=object()),
            selection_state=ActivitySelectionState(query=ActivityQuery(), filtered_count=1),
            style_preset="By activity type",
            temporal_mode="By month",
            background_config=BackgroundConfig(),
            analysis_mode="None",
            apply_subset_filters=True,
        )

        result = dispatcher.dispatch(action)

        self.assertEqual(result.status, "Applied current filters")
        self.assertIsNone(result.background_layer)
        self.assertEqual(result.background_error, "")

    def test_dispatch_returns_structured_result_for_unsupported_action(self):
        dispatcher = DockActionDispatcher(
            visual_apply=MagicMock(),
            save_settings=MagicMock(),
            run_analysis=MagicMock(),
        )

        result = dispatcher.dispatch(object())

        self.assertEqual(result.unsupported_reason, "Unsupported dock action: object")


if __name__ == "__main__":
    unittest.main()
