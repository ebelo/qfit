from __future__ import annotations

from .analysis_execution_dispatch import (
    FREQUENT_STARTING_POINTS_MODE,
    HEATMAP_MODE,
)
from .analysis_models import RunAnalysisRequest, RunAnalysisResult
from .analysis_policy_facade import (
    build_analysis_controller_request,
    run_analysis_controller_request,
)


class AnalysisController:
    """Coordinates dock-triggered analysis workflows behind a small seam."""

    @staticmethod
    def build_request(
        analysis_mode: str,
        starts_layer: object,
        selection_state=None,
        activities_layer: object = None,
        points_layer: object = None,
    ) -> RunAnalysisRequest:
        return build_analysis_controller_request(
            analysis_mode=analysis_mode,
            starts_layer=starts_layer,
            selection_state=selection_state,
            activities_layer=activities_layer,
            points_layer=points_layer,
        )

    def run(self, request: RunAnalysisRequest | None = None, **legacy_kwargs) -> RunAnalysisResult:
        return run_analysis_controller_request(
            request=request,
            legacy_kwargs=legacy_kwargs,
        )

    def run_request(self, request: RunAnalysisRequest) -> RunAnalysisResult:
        return self.run(request=request)
