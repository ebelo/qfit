from __future__ import annotations

from dataclasses import dataclass

from ...activities.application.activity_selection_state import ActivitySelectionState
from ...visualization.application import LayerRefs
from .visual_workflow_action_builder import (
    VisualWorkflowBackgroundInputs,
    VisualWorkflowSettingsSnapshot,
    build_visual_workflow_action,
    build_visual_workflow_action_inputs,
)


@dataclass(frozen=True)
class DockVisualWorkflowRequest:
    layers: LayerRefs
    selection_state: ActivitySelectionState
    settings: VisualWorkflowSettingsSnapshot
    background: VisualWorkflowBackgroundInputs
    apply_subset_filters: bool = True


class DockVisualWorkflowCoordinator:
    """Build and dispatch dock visual-workflow actions from dock-edge snapshots."""

    def __init__(self, *, dispatcher) -> None:
        self.dispatcher = dispatcher

    def build_action(self, action_type, request: DockVisualWorkflowRequest):
        return build_visual_workflow_action(
            action_type,
            build_visual_workflow_action_inputs(
                layers=request.layers,
                selection_state=request.selection_state,
                settings=request.settings,
                background=request.background,
                apply_subset_filters=request.apply_subset_filters,
            ),
        )

    def dispatch_action(
        self,
        action_type,
        request: DockVisualWorkflowRequest,
        *,
        require_layers: bool = True,
    ):
        action = self.build_action(action_type, request)
        if require_layers and not action.layers.has_any():
            return None
        return self.dispatcher.dispatch(action)


__all__ = [
    "DockVisualWorkflowCoordinator",
    "DockVisualWorkflowRequest",
]
