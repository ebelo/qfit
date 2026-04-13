from ...activities.application.activity_selection_state import ActivitySelectionState
from .analysis_request_building import build_analysis_request
from .analysis_request_execution import execute_analysis_request


def build_analysis_controller_request(
    *,
    analysis_mode: str,
    starts_layer,
    selection_state: ActivitySelectionState | None = None,
    activities_layer: object = None,
    points_layer: object = None,
):
    return build_analysis_request(
        analysis_mode=analysis_mode,
        starts_layer=starts_layer,
        selection_state=selection_state,
        activities_layer=activities_layer,
        points_layer=points_layer,
    )


def run_analysis_controller_request(*, request=None, legacy_kwargs=None):
    return execute_analysis_request(
        build_request=build_analysis_controller_request,
        request=request,
        legacy_kwargs=legacy_kwargs,
    )
