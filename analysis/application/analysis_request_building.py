from ...activities.application.activity_selection_state import ActivitySelectionState


def build_analysis_request(
    *,
    analysis_mode: str,
    starts_layer,
    selection_state: ActivitySelectionState | None = None,
    activities_layer=None,
    points_layer=None,
):
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
