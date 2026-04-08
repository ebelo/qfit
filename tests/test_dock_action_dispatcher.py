from types import SimpleNamespace
from unittest.mock import MagicMock

from qfit.activities.domain.activity_query import ActivityQuery
from qfit.ui.application import (
    ApplyVisualizationAction,
    DockActionDispatcher,
    RunAnalysisAction,
)
from qfit.visualization.application import BackgroundConfig, LayerRefs


class TestDockActionDispatcher:
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
        action = ApplyVisualizationAction(
            layers=LayerRefs(activities=object(), starts=starts_layer),
            query=ActivityQuery(),
            style_preset="By activity type",
            temporal_mode="By month",
            background_config=BackgroundConfig(enabled=True, preset_name="Outdoors"),
            filtered_count=3,
            analysis_mode="Most frequent starting points",
            starts_layer=starts_layer,
            apply_subset_filters=False,
        )

        result = dispatcher.dispatch(action)

        save_settings.assert_called_once_with()
        visual_apply.build_request.assert_called_once_with(
            layers=action.layers,
            query=action.query,
            style_preset="By activity type",
            temporal_mode="By month",
            background_config=action.background_config,
            apply_subset_filters=False,
            filtered_count=3,
        )
        visual_apply.apply_request.assert_called_once_with("request")
        run_analysis.assert_called_once_with(
            "Most frequent starting points",
            starts_layer,
        )
        assert result.status == (
            "Applied current filters. Showing top 2 frequent starting-point clusters"
        )
        assert result.background_layer == "background-layer"
        assert result.analysis_status == "Showing top 2 frequent starting-point clusters"

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
            query=ActivityQuery(),
            style_preset="By activity type",
            temporal_mode="By month",
            background_config=BackgroundConfig(),
            filtered_count=1,
            analysis_mode="None",
            apply_subset_filters=True,
        )

        result = dispatcher.dispatch(action)

        assert result.status == "Applied current filters"
        assert result.background_layer is None
        assert result.background_error == ""

    def test_dispatch_returns_structured_result_for_unsupported_action(self):
        dispatcher = DockActionDispatcher(
            visual_apply=MagicMock(),
            save_settings=MagicMock(),
            run_analysis=MagicMock(),
        )

        result = dispatcher.dispatch(object())

        assert result.unsupported_reason == "Unsupported dock action: object"
