from .dock_action_dispatcher import ApplyVisualizationAction, RunAnalysisAction
from ...visualization.application import BackgroundConfig, LayerRefs


def build_visual_workflow_action(
    action_type,
    *,
    activities_layer,
    starts_layer,
    points_layer,
    atlas_layer,
    selection_state,
    style_preset,
    temporal_mode,
    background_enabled,
    background_preset_name,
    access_token,
    style_owner,
    style_id,
    tile_mode,
    analysis_mode,
    apply_subset_filters=True,
):
    """Build a normalized visual workflow action from dock-edge inputs."""

    if action_type not in (ApplyVisualizationAction, RunAnalysisAction):
        raise TypeError(f"Unsupported visual workflow action type: {action_type!r}")

    return action_type(
        layers=LayerRefs(
            activities=activities_layer,
            starts=starts_layer,
            points=points_layer,
            atlas=atlas_layer,
        ),
        selection_state=selection_state,
        style_preset=style_preset,
        temporal_mode=temporal_mode,
        background_config=BackgroundConfig(
            enabled=background_enabled,
            preset_name=background_preset_name,
            access_token=access_token,
            style_owner=style_owner,
            style_id=style_id,
            tile_mode=tile_mode,
        ),
        analysis_mode=analysis_mode,
        starts_layer=starts_layer,
        apply_subset_filters=apply_subset_filters,
    )
