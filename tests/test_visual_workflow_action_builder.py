import unittest

from tests import _path  # noqa: F401
from qfit.activities.application.activity_selection_state import ActivitySelectionState
from qfit.activities.domain.activity_query import ActivityQuery
from qfit.ui.application import (
    ApplyVisualizationAction,
    RunAnalysisAction,
    VisualWorkflowActionInputs,
    build_visual_workflow_action,
)
from qfit.visualization.application import BackgroundConfig, LayerRefs


class TestVisualWorkflowActionBuilder(unittest.TestCase):
    def test_builds_apply_visualization_action(self):
        selection_state = ActivitySelectionState(query=ActivityQuery(), filtered_count=3)

        action = build_visual_workflow_action(
            ApplyVisualizationAction,
            VisualWorkflowActionInputs(
                layers=LayerRefs(
                    activities="activities",
                    starts="starts",
                    points="points",
                    atlas="atlas",
                ),
                selection_state=selection_state,
                style_preset="By activity type",
                temporal_mode="Off",
                background_config=BackgroundConfig(
                    enabled=True,
                    preset_name="Outdoors",
                    access_token="token",
                    style_owner="mapbox",
                    style_id="style-id",
                    tile_mode="Raster",
                ),
                analysis_mode="Most frequent starting points",
            ),
        )

        self.assertIsInstance(action, ApplyVisualizationAction)
        self.assertEqual(action.layers.activities, "activities")
        self.assertEqual(action.layers.starts, "starts")
        self.assertEqual(action.layers.points, "points")
        self.assertEqual(action.layers.atlas, "atlas")
        self.assertIs(action.selection_state, selection_state)
        self.assertEqual(action.style_preset, "By activity type")
        self.assertEqual(action.temporal_mode, "Off")
        self.assertTrue(action.background_config.enabled)
        self.assertEqual(action.background_config.access_token, "token")
        self.assertEqual(action.analysis_mode, "Most frequent starting points")
        self.assertEqual(action.filtered_count, 3)

    def test_builds_run_analysis_action(self):
        selection_state = ActivitySelectionState(query=ActivityQuery(), filtered_count=1)

        action = build_visual_workflow_action(
            RunAnalysisAction,
            VisualWorkflowActionInputs(
                layers=LayerRefs(starts="starts"),
                selection_state=selection_state,
                style_preset="Heatmap",
                temporal_mode="By month",
                background_config=BackgroundConfig(tile_mode="Raster"),
                analysis_mode="Heatmap",
                apply_subset_filters=False,
            ),
        )

        self.assertIsInstance(action, RunAnalysisAction)
        self.assertFalse(action.apply_subset_filters)
        self.assertEqual(action.starts_layer, "starts")
        self.assertFalse(action.background_config.enabled)

    def test_rejects_unsupported_action_types(self):
        with self.assertRaises(TypeError):
            build_visual_workflow_action(
                object,
                VisualWorkflowActionInputs(
                    layers=LayerRefs(),
                    selection_state=ActivitySelectionState(
                        query=ActivityQuery(),
                        filtered_count=0,
                    ),
                    style_preset="By activity type",
                    temporal_mode="Off",
                    background_config=BackgroundConfig(tile_mode="Raster"),
                    analysis_mode="None",
                ),
            )


if __name__ == "__main__":
    unittest.main()
