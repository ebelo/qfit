from dataclasses import dataclass

from .dock_action_dispatcher import ApplyVisualizationAction, RunAnalysisAction
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
