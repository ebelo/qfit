from __future__ import annotations

from dataclasses import dataclass, field

from ...activities.application.activity_selection_state import ActivitySelectionState

FREQUENT_STARTING_POINTS_MODE = "Most frequent starting points"


@dataclass(frozen=True)
class RunAnalysisRequest:
    analysis_mode: str = ""
    starts_layer: object = None
    selection_state: ActivitySelectionState = field(default_factory=ActivitySelectionState)


@dataclass(frozen=True)
class RunAnalysisResult:
    status: str = ""
    layer: object = None


class AnalysisController:
    """Coordinates dock-triggered analysis workflows behind a small seam."""

    @staticmethod
    def build_request(
        analysis_mode: str,
        starts_layer: object,
        selection_state: ActivitySelectionState | None = None,
    ) -> RunAnalysisRequest:
        return RunAnalysisRequest(
            analysis_mode=analysis_mode or "",
            starts_layer=starts_layer,
            selection_state=selection_state or ActivitySelectionState(),
        )

    def run(self, request: RunAnalysisRequest | None = None, **legacy_kwargs) -> RunAnalysisResult:
        if request is None:
            request = self.build_request(**legacy_kwargs)

        if request.analysis_mode != FREQUENT_STARTING_POINTS_MODE:
            return RunAnalysisResult()
        if request.starts_layer is None:
            return RunAnalysisResult()

        layer, clusters = _build_frequent_start_points_layer(request.starts_layer)
        if layer is None or not clusters:
            return RunAnalysisResult(
                status="No frequent starting points matched the current filters"
            )

        return RunAnalysisResult(
            status="Showing top {count} frequent starting-point clusters".format(
                count=len(clusters)
            ),
            layer=layer,
        )

    def run_request(self, request: RunAnalysisRequest) -> RunAnalysisResult:
        return self.run(request=request)


def _build_frequent_start_points_layer(starts_layer):
    from ..infrastructure.frequent_start_points_layer import (
        build_frequent_start_points_layer,
    )

    return build_frequent_start_points_layer(starts_layer)
