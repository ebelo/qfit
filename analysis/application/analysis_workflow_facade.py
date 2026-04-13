from ...activities.application.activity_selection_state import ActivitySelectionState
from .analysis_workflow_building import build_analysis_workflow
from .analysis_workflow_execution import run_analysis_workflow


def build_analysis_workflow_request(
    *,
    analysis_mode: str,
    starts_layer,
    selection_state: ActivitySelectionState | None = None,
    activities_layer: object = None,
    points_layer: object = None,
):
    return build_analysis_workflow(
        analysis_mode=analysis_mode,
        starts_layer=starts_layer,
        selection_state=selection_state,
        activities_layer=activities_layer,
        points_layer=points_layer,
    )


def run_analysis_workflow_request(*, request=None, legacy_kwargs=None):
    return run_analysis_workflow(
        build_request=build_analysis_workflow_request,
        request=request,
        legacy_kwargs=legacy_kwargs,
    )
