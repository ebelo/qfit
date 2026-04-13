from __future__ import annotations

from ...activities.application.activity_selection_state import ActivitySelectionState
from .analysis_models import RunAnalysisRequest, RunAnalysisResult
from .analysis_result_builder import (
    build_activity_heatmap_result,
    build_empty_analysis_result,
)

FREQUENT_STARTING_POINTS_MODE = "Most frequent starting points"
HEATMAP_MODE = "Heatmap"


class AnalysisController:
    """Coordinates dock-triggered analysis workflows behind a small seam."""

    @staticmethod
    def build_request(
        analysis_mode: str,
        starts_layer: object,
        selection_state: ActivitySelectionState | None = None,
        activities_layer: object = None,
        points_layer: object = None,
    ) -> RunAnalysisRequest:
        from .analysis_request_builder import (
            build_analysis_controller_request_inputs,
            build_run_analysis_request,
        )

        return build_run_analysis_request(
            build_analysis_controller_request_inputs(
                analysis_mode=analysis_mode,
                starts_layer=starts_layer,
                selection_state=selection_state,
                activities_layer=activities_layer,
                points_layer=points_layer,
            )
        )

    def run(self, request: RunAnalysisRequest | None = None, **legacy_kwargs) -> RunAnalysisResult:
        if request is None:
            request = self.build_request(**legacy_kwargs)

        if request.analysis_mode == FREQUENT_STARTING_POINTS_MODE:
            return _run_frequent_start_points_analysis(request.starts_layer)

        if request.analysis_mode == HEATMAP_MODE:
            if request.activities_layer is None and request.points_layer is None:
                return build_empty_analysis_result()

            layer, sample_count = _build_activity_heatmap_layer(
                request.activities_layer,
                request.points_layer,
            )
            return build_activity_heatmap_result(layer, sample_count)

        return build_empty_analysis_result()

    def run_request(self, request: RunAnalysisRequest) -> RunAnalysisResult:
        return self.run(request=request)


def _run_frequent_start_points_analysis(starts_layer):
    from .frequent_start_points_analysis import run_frequent_start_points_analysis

    return run_frequent_start_points_analysis(starts_layer)


def _build_activity_heatmap_layer(activities_layer, points_layer):
    from ..infrastructure.activity_heatmap_layer import build_activity_heatmap_layer

    return build_activity_heatmap_layer(
        activities_layer=activities_layer,
        points_layer=points_layer,
    )
