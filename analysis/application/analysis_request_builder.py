from __future__ import annotations

from dataclasses import dataclass, field

from ...activities.application.activity_selection_state import ActivitySelectionState
from .analysis_controller import RunAnalysisRequest


@dataclass(frozen=True)
class ApplyAnalysisConfigurationInputs:
    analysis_mode: str = ""
    starts_layer: object = None
    selection_state: ActivitySelectionState = field(default_factory=ActivitySelectionState)


@dataclass(frozen=True)
class RunAnalysisCurrentInputs:
    activities_layer: object = None
    points_layer: object = None


@dataclass(frozen=True)
class RunAnalysisRequestInputs:
    analysis_mode: str = ""
    activities_layer: object = None
    starts_layer: object = None
    points_layer: object = None
    selection_state: ActivitySelectionState = field(default_factory=ActivitySelectionState)


def build_apply_analysis_configuration_inputs(
    *,
    current_mode: str = "",
    current_starts_layer=None,
    current_selection_state: ActivitySelectionState | None = None,
    analysis_mode: str | None = None,
    starts_layer=None,
    selection_state: ActivitySelectionState | None = None,
) -> ApplyAnalysisConfigurationInputs:
    """Build normalized analysis-configuration inputs from current dock state and overrides."""

    return ApplyAnalysisConfigurationInputs(
        analysis_mode=analysis_mode or current_mode or "",
        starts_layer=starts_layer if starts_layer is not None else current_starts_layer,
        selection_state=selection_state or current_selection_state or ActivitySelectionState(),
    )


def build_run_analysis_current_inputs(
    *,
    activities_layer=None,
    points_layer=None,
) -> RunAnalysisCurrentInputs:
    """Build normalized current layer inputs for analysis request shaping."""

    return RunAnalysisCurrentInputs(
        activities_layer=activities_layer,
        points_layer=points_layer,
    )


def build_run_analysis_request_inputs(
    *,
    current: RunAnalysisCurrentInputs | None = None,
    analysis_mode: str = "",
    starts_layer=None,
    selection_state: ActivitySelectionState | None = None,
) -> RunAnalysisRequestInputs:
    """Build normalized run-analysis request inputs from current dock state."""

    current = current or RunAnalysisCurrentInputs()
    return RunAnalysisRequestInputs(
        analysis_mode=analysis_mode or "",
        activities_layer=current.activities_layer,
        starts_layer=starts_layer,
        points_layer=current.points_layer,
        selection_state=selection_state or ActivitySelectionState(),
    )


def build_run_analysis_request(inputs: RunAnalysisRequestInputs) -> RunAnalysisRequest:
    """Build a normalized analysis request from dock-edge inputs."""

    return RunAnalysisRequest(
        analysis_mode=inputs.analysis_mode or "",
        activities_layer=inputs.activities_layer,
        starts_layer=inputs.starts_layer,
        points_layer=inputs.points_layer,
        selection_state=inputs.selection_state or ActivitySelectionState(),
    )
