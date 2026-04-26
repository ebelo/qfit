"""Application-facing dock widget workflow helpers."""

from .dock_action_dispatcher import (
    ApplyVisualizationAction,
    DockActionDispatcher,
    DockActionResult,
    RunAnalysisAction,
)
from .dock_activity_workflow import (
    DockActivityWorkflowCoordinator,
    DockFetchCompletionRequest,
    DockFetchCompletionResult,
    DockFetchRequest,
)
from .dock_atlas_workflow import (
    DockAtlasExportRequest,
    DockAtlasWorkflowCoordinator,
)
from .dock_visual_workflow import (
    DockVisualWorkflowCoordinator,
    DockVisualWorkflowRequest,
)
from .dock_runtime_state import (
    DockRuntimeLayers,
    DockRuntimeState,
    DockRuntimeStore,
    DockRuntimeTasks,
)
from .dock_summary_status import build_dock_summary_status
from .dock_workflow_sections import (
    CURRENT_DOCK_SECTIONS,
    WIZARD_WORKFLOW_STEPS,
    DockWizardProgress,
    DockWorkflowSection,
    DockWorkflowStepState,
    DockWorkflowStepStatus,
    build_current_dock_workflow_label,
    build_initial_wizard_step_statuses,
    build_progress_wizard_step_statuses,
    build_wizard_step_statuses,
    get_workflow_section,
)
from .stepper_presenter import (
    STEPPER_STATE_CURRENT,
    STEPPER_STATE_DONE,
    STEPPER_STATE_LOCKED,
    STEPPER_STATE_UPCOMING,
    STEPPER_STATES_BY_WORKFLOW_STATE,
    StepperItem,
    build_stepper_items,
    build_stepper_states,
    can_request_step,
    step_index_for_key,
    step_key_for_index,
)
from .wizard_settings import (
    COLLAPSED_GROUPS_KEY,
    DEFAULT_COLLAPSED_GROUP_OBJECT_NAMES,
    LAST_STEP_INDEX_KEY,
    WIZARD_STEP_COUNT,
    WIZARD_VERSION,
    WIZARD_VERSION_KEY,
    WizardSettingsSnapshot,
    clamp_wizard_step_index,
    ensure_wizard_settings,
    load_wizard_settings,
    preferred_current_key_from_settings,
    save_collapsed_groups,
    save_last_step_index,
    wizard_step_key_for_index,
)
from .wizard_progress import (
    WizardProgressFacts,
    build_wizard_progress_from_facts,
    build_wizard_progress_from_facts_and_settings,
)
from .visual_workflow_action_builder import build_visual_workflow_action
from .visual_workflow_action_builder import build_visual_workflow_action_inputs
from .visual_workflow_action_builder import build_visual_workflow_background_inputs
from .visual_workflow_action_builder import build_visual_workflow_selection_state_handoff
from .visual_workflow_action_builder import build_visual_layer_refs
from .visual_workflow_action_builder import VisualWorkflowActionInputs
from .visual_workflow_action_builder import VisualWorkflowBackgroundInputs
from .visual_workflow_action_builder import VisualWorkflowSettingsSnapshot
from .visual_workflow_action_builder import build_visual_workflow_settings_snapshot

__all__ = [
    "ApplyVisualizationAction",
    "COLLAPSED_GROUPS_KEY",
    "DEFAULT_COLLAPSED_GROUP_OBJECT_NAMES",
    "DockActionDispatcher",
    "DockActionResult",
    "DockActivityWorkflowCoordinator",
    "DockAtlasExportRequest",
    "DockAtlasWorkflowCoordinator",
    "DockFetchCompletionRequest",
    "DockFetchCompletionResult",
    "DockFetchRequest",
    "DockRuntimeLayers",
    "DockRuntimeState",
    "DockRuntimeStore",
    "DockRuntimeTasks",
    "DockVisualWorkflowCoordinator",
    "DockVisualWorkflowRequest",
    "DockWizardProgress",
    "DockWorkflowSection",
    "DockWorkflowStepState",
    "DockWorkflowStepStatus",
    "CURRENT_DOCK_SECTIONS",
    "LAST_STEP_INDEX_KEY",
    "WIZARD_WORKFLOW_STEPS",
    "WIZARD_STEP_COUNT",
    "WIZARD_VERSION",
    "WIZARD_VERSION_KEY",
    "RunAnalysisAction",
    "STEPPER_STATE_CURRENT",
    "STEPPER_STATE_DONE",
    "STEPPER_STATE_LOCKED",
    "STEPPER_STATE_UPCOMING",
    "STEPPER_STATES_BY_WORKFLOW_STATE",
    "StepperItem",
    "VisualWorkflowBackgroundInputs",
    "VisualWorkflowActionInputs",
    "VisualWorkflowSettingsSnapshot",
    "WizardProgressFacts",
    "WizardSettingsSnapshot",
    "build_current_dock_workflow_label",
    "build_dock_summary_status",
    "build_initial_wizard_step_statuses",
    "build_progress_wizard_step_statuses",
    "build_stepper_items",
    "build_stepper_states",
    "build_wizard_progress_from_facts",
    "build_wizard_progress_from_facts_and_settings",
    "build_wizard_step_statuses",
    "build_visual_layer_refs",
    "build_visual_workflow_action",
    "build_visual_workflow_action_inputs",
    "build_visual_workflow_background_inputs",
    "build_visual_workflow_selection_state_handoff",
    "build_visual_workflow_settings_snapshot",
    "can_request_step",
    "clamp_wizard_step_index",
    "ensure_wizard_settings",
    "get_workflow_section",
    "load_wizard_settings",
    "preferred_current_key_from_settings",
    "save_collapsed_groups",
    "save_last_step_index",
    "step_index_for_key",
    "step_key_for_index",
    "wizard_step_key_for_index",
]
