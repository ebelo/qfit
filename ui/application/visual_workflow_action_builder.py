from dataclasses import dataclass

from .dock_action_dispatcher import ApplyVisualizationAction, RunAnalysisAction
from ...activities.application.activity_selection_state import ActivitySelectionState
from ...visualization.application import BackgroundConfig, LayerRefs


@dataclass(frozen=True)
class VisualWorkflowActionInputs:
    layers: LayerRefs
    selection_state: object
    style_preset: str
    temporal_mode: str
    background_config: BackgroundConfig
    analysis_mode: str
    apply_subset_filters: bool = True


@dataclass(frozen=True)
class VisualWorkflowBackgroundInputs:
    enabled: bool = False
    preset_name: str = ""
    access_token: str = ""
    style_owner: str = ""
    style_id: str = ""
    tile_mode: str = ""


@dataclass(frozen=True)
class VisualWorkflowSettingsSnapshot:
    style_preset: str = ""
    temporal_mode: str = ""
    analysis_mode: str = ""


def build_visual_layer_refs(
    *,
    activities_layer=None,
    starts_layer=None,
    points_layer=None,
    atlas_layer=None,
) -> LayerRefs:
    """Build a normalized snapshot of the current visual workflow layers."""

    return LayerRefs(
        activities=activities_layer,
        starts=starts_layer,
        points=points_layer,
        atlas=atlas_layer,
    )


def build_visual_workflow_settings_snapshot(
    *,
    style_preset: str,
    temporal_mode: str,
    analysis_mode: str,
) -> VisualWorkflowSettingsSnapshot:
    """Build a normalized snapshot of the current visual workflow settings."""

    return VisualWorkflowSettingsSnapshot(
        style_preset=style_preset,
        temporal_mode=temporal_mode,
        analysis_mode=analysis_mode,
    )


def build_visual_workflow_background_inputs(
    *,
    enabled: bool,
    preset_name: str,
    access_token: str,
    style_owner: str,
    style_id: str,
    tile_mode: str,
) -> VisualWorkflowBackgroundInputs:
    """Build a normalized snapshot of the current visual workflow background inputs."""

    return VisualWorkflowBackgroundInputs(
        enabled=enabled,
        preset_name=preset_name,
        access_token=access_token,
        style_owner=style_owner,
        style_id=style_id,
        tile_mode=tile_mode,
    )


def build_visual_workflow_selection_state_handoff(
    selection_state=None,
) -> ActivitySelectionState:
    """Normalize the current visual workflow selection-state handoff."""

    return selection_state or ActivitySelectionState()


def build_visual_workflow_action_inputs(
    *,
    layers: LayerRefs,
    selection_state,
    settings: VisualWorkflowSettingsSnapshot,
    background: VisualWorkflowBackgroundInputs,
    apply_subset_filters: bool = True,
) -> VisualWorkflowActionInputs:
    """Build normalized visual workflow inputs from dock-edge values."""

    return VisualWorkflowActionInputs(
        layers=layers,
        selection_state=build_visual_workflow_selection_state_handoff(selection_state),
        style_preset=settings.style_preset,
        temporal_mode=settings.temporal_mode,
        background_config=BackgroundConfig(
            enabled=background.enabled,
            preset_name=background.preset_name,
            access_token=background.access_token,
            style_owner=background.style_owner,
            style_id=background.style_id,
            tile_mode=background.tile_mode,
        ),
        analysis_mode=settings.analysis_mode,
        apply_subset_filters=apply_subset_filters,
    )


def build_visual_workflow_action(
    action_type,
    inputs: VisualWorkflowActionInputs,
):
    """Build a normalized visual workflow action from dock-edge inputs."""

    if action_type not in (ApplyVisualizationAction, RunAnalysisAction):
        raise TypeError(f"Unsupported visual workflow action type: {action_type!r}")

    return action_type(
        layers=inputs.layers,
        selection_state=inputs.selection_state,
        style_preset=inputs.style_preset,
        temporal_mode=inputs.temporal_mode,
        background_config=inputs.background_config,
        analysis_mode=inputs.analysis_mode,
        starts_layer=inputs.layers.starts,
        apply_subset_filters=inputs.apply_subset_filters,
    )
