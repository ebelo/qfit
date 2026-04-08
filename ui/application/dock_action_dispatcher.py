from dataclasses import dataclass
from typing import Any, Callable

from ...activities.application.activity_selection_state import ActivitySelectionState
from ...visualization.application import BackgroundConfig, LayerRefs, VisualApplyService


@dataclass(frozen=True)
class _BaseVisualWorkflowAction:
    layers: LayerRefs
    selection_state: ActivitySelectionState
    style_preset: str
    temporal_mode: str
    background_config: BackgroundConfig
    analysis_mode: str
    starts_layer: object = None
    apply_subset_filters: bool = True

    @property
    def query(self):
        return self.selection_state.query

    @property
    def filtered_count(self):
        return self.selection_state.filtered_count


@dataclass(frozen=True)
class ApplyVisualizationAction(_BaseVisualWorkflowAction):
    """Normalized request for an apply-visualization dock action."""


@dataclass(frozen=True)
class RunAnalysisAction(_BaseVisualWorkflowAction):
    """Normalized request for a run-analysis dock action."""


@dataclass(frozen=True)
class DockActionResult:
    """Structured result returned to the dock widget UI."""

    status: str = ""
    background_layer: object = None
    background_error: str = ""
    analysis_status: str = ""
    unsupported_reason: str = ""


class DockActionDispatcher:
    """Routes normalized dock actions to the right workflow collaborators."""

    def __init__(
        self,
        *,
        visual_apply: VisualApplyService,
        save_settings: Callable[[], None],
        run_analysis: Callable[[str, object, ActivitySelectionState], str],
    ) -> None:
        self.visual_apply = visual_apply
        self._save_settings = save_settings
        self._run_analysis = run_analysis

    def dispatch(self, action: Any) -> DockActionResult:
        if isinstance(action, (ApplyVisualizationAction, RunAnalysisAction)):
            return self._dispatch_visual_workflow(action)
        return DockActionResult(
            unsupported_reason="Unsupported dock action: {name}".format(
                name=type(action).__name__
            )
        )

    def _dispatch_visual_workflow(
        self, action: ApplyVisualizationAction | RunAnalysisAction
    ) -> DockActionResult:
        self._save_settings()
        request = self.visual_apply.build_request(
            layers=action.layers,
            selection_state=action.selection_state,
            style_preset=action.style_preset,
            temporal_mode=action.temporal_mode,
            background_config=action.background_config,
            apply_subset_filters=action.apply_subset_filters,
        )
        visual_result = self.visual_apply.apply_request(request)

        background_layer = None
        background_error = ""
        if self.visual_apply.should_update_background(action.apply_subset_filters):
            background_layer = visual_result.background_layer
            background_error = visual_result.background_error

        analysis_status = self._run_analysis(
            action.analysis_mode,
            action.starts_layer,
            action.selection_state,
        )
        return DockActionResult(
            status=self._combine_statuses(visual_result.status, analysis_status),
            background_layer=background_layer,
            background_error=background_error,
            analysis_status=analysis_status,
        )

    @staticmethod
    def _combine_statuses(primary: str, secondary: str) -> str:
        if primary and secondary:
            return f"{primary}. {secondary}"
        return primary or secondary or ""
