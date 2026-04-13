from __future__ import annotations

from dataclasses import dataclass, field

from ...activities.application.activity_selection_state import ActivitySelectionState
from .analysis_controller import RunAnalysisRequest


@dataclass(frozen=True)
class RunAnalysisRequestInputs:
    analysis_mode: str = ""
    activities_layer: object = None
    starts_layer: object = None
    points_layer: object = None
    selection_state: ActivitySelectionState = field(default_factory=ActivitySelectionState)


def build_run_analysis_request(inputs: RunAnalysisRequestInputs) -> RunAnalysisRequest:
    """Build a normalized analysis request from dock-edge inputs."""

    return RunAnalysisRequest(
        analysis_mode=inputs.analysis_mode or "",
        activities_layer=inputs.activities_layer,
        starts_layer=inputs.starts_layer,
        points_layer=inputs.points_layer,
        selection_state=inputs.selection_state or ActivitySelectionState(),
    )
