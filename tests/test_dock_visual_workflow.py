import unittest
from unittest.mock import MagicMock

from tests import _path  # noqa: F401
from qfit.activities.application.activity_selection_state import ActivitySelectionState
from qfit.activities.domain.activity_query import ActivityQuery
from qfit.ui.application import (
    ApplyVisualizationAction,
    DockVisualWorkflowCoordinator,
    DockVisualWorkflowRequest,
    RunAnalysisAction,
    VisualWorkflowBackgroundInputs,
    build_visual_layer_refs,
    build_visual_workflow_settings_snapshot,
)


class DockVisualWorkflowCoordinatorTests(unittest.TestCase):
    def setUp(self):
        self.dispatcher = MagicMock()
        self.dispatcher.dispatch.return_value = "dispatch-result"
        self.coordinator = DockVisualWorkflowCoordinator(dispatcher=self.dispatcher)
        self.request = DockVisualWorkflowRequest(
            layers=build_visual_layer_refs(activities_layer=object(), starts_layer=object()),
            selection_state=ActivitySelectionState(query=ActivityQuery(), filtered_count=3),
            settings=build_visual_workflow_settings_snapshot(
                style_preset="By activity type",
                temporal_mode="By month",
                analysis_mode="Most frequent starting points",
            ),
            background=VisualWorkflowBackgroundInputs(
                enabled=True,
                preset_name="Outdoors",
                access_token="tok",
                style_owner="mapbox",
                style_id="outdoors-v12",
                tile_mode="raster",
            ),
        )

    def test_build_action_returns_normalized_apply_action(self):
        action = self.coordinator.build_action(ApplyVisualizationAction, self.request)

        self.assertIsInstance(action, ApplyVisualizationAction)
        self.assertEqual(action.style_preset, "By activity type")
        self.assertEqual(action.temporal_mode, "By month")
        self.assertEqual(action.analysis_mode, "Most frequent starting points")
        self.assertTrue(action.background_config.enabled)
        self.assertIs(action.starts_layer, self.request.layers.starts)

    def test_dispatch_action_delegates_to_dispatcher(self):
        result = self.coordinator.dispatch_action(RunAnalysisAction, self.request)

        self.assertEqual(result, "dispatch-result")
        dispatched_action = self.dispatcher.dispatch.call_args.args[0]
        self.assertIsInstance(dispatched_action, RunAnalysisAction)
        self.assertEqual(dispatched_action.filtered_count, 3)

    def test_dispatch_action_can_skip_empty_layers(self):
        request = DockVisualWorkflowRequest(
            layers=build_visual_layer_refs(),
            selection_state=ActivitySelectionState(query=ActivityQuery(), filtered_count=0),
            settings=self.request.settings,
            background=self.request.background,
        )

        result = self.coordinator.dispatch_action(
            ApplyVisualizationAction,
            request,
            require_layers=True,
        )

        self.assertIsNone(result)
        self.dispatcher.dispatch.assert_not_called()


if __name__ == "__main__":
    unittest.main()
