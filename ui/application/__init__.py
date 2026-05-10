"""Application-facing dock widget workflow helpers."""

from importlib import import_module

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
from .local_first_navigation import (
    LOCAL_FIRST_DOCK_PAGE_DEFINITIONS,
    LocalFirstDockNavigationState,
    LocalFirstDockPageDefinition,
    LocalFirstDockPageState,
    build_local_first_dock_navigation_state,
    local_first_dock_page_keys,
)
from .local_first_parity_audit import (
    ISSUE_805_REQUIRED_AREAS,
    LocalFirstParitySurface,
    build_issue805_local_first_parity_surfaces,
    issue805_local_first_coverage_by_area,
    missing_issue805_local_first_areas,
)
from .local_first_activity_controls import (
    build_current_activity_preview_request,
    configure_detailed_route_filter_options,
    configure_detailed_route_strategy_options,
    configure_local_first_activity_preview_options,
    configure_preview_sort_options,
)
from .local_first_analysis_controls import (
    ANALYSIS_MODE_LABELS,
    NONE_ANALYSIS_MODE_LABEL,
    bind_local_first_analysis_mode_controls,
    configure_local_first_analysis_mode_backing_controls,
    configure_local_first_temporal_mode_backing_controls,
    local_first_analysis_mode_options,
    set_local_first_analysis_mode,
)
from .local_first_atlas_controls import update_local_first_atlas_document_settings
from .local_first_basemap_controls import (
    bind_local_first_basemap_preset_controls,
    configure_local_first_basemap_options,
    sync_local_first_basemap_style_fields,
)
from .local_first_control_moves import (
    LOCAL_FIRST_CONTROL_MOVES,
    LOCAL_FIRST_WIDGET_MOVES,
    LocalFirstControlMove,
    LocalFirstWidgetMove,
    local_first_control_move_for_key,
    local_first_control_move_keys,
    local_first_widget_move_for_key,
    local_first_widget_move_keys,
)
from .local_first_connection_controls import request_local_first_connection_configuration
from .local_first_control_installer import (
    after_local_first_control_move_installed,
    install_local_first_audited_controls,
    install_local_first_control_move,
    install_local_first_group_controls,
    install_local_first_widget_move,
    install_local_first_widget_controls,
    local_first_control_move_layout,
    local_first_control_move_parent_panel,
    local_first_control_move_required_widgets_available,
    local_first_widget_move_widgets,
    refresh_local_first_control_visibility,
    remove_widget_from_current_layout,
    show_local_first_control_group,
    show_widget,
)
from .local_first_control_visibility import (
    ADVANCED_FETCH_VISIBILITY_WIDGETS,
    DETAILED_FETCH_VISIBILITY_WIDGETS,
    MAPBOX_CUSTOM_STYLE_VISIBILITY_WIDGETS,
    POINT_SAMPLING_VISIBILITY_WIDGETS,
    LocalFirstControlVisibilityUpdate,
    apply_local_first_visibility_update,
    bind_local_first_conditional_visibility_controls,
    build_advanced_fetch_visibility_update,
    build_detailed_fetch_visibility_update,
    build_local_first_conditional_visibility_updates,
    build_mapbox_custom_style_visibility_update,
    build_point_sampling_visibility_update,
    refresh_local_first_conditional_control_visibility,
    update_local_first_mapbox_custom_style_visibility,
)
from .local_first_filter_summary import build_local_first_filter_description

build_wizard_filter_description = build_local_first_filter_description

from .local_first_progress_facts import (
    LocalFirstProgressFacts,
    current_local_first_last_sync_date,
    runtime_state_with_local_first_output_path,
)
from .workflow_footer_status import (
    WorkflowFooterFacts,
    build_workflow_footer_facts_from_progress_facts,
    build_workflow_footer_status,
)

WizardFooterFacts = WorkflowFooterFacts
build_wizard_footer_facts_from_progress_facts = (
    build_workflow_footer_facts_from_progress_facts
)
build_wizard_footer_status = build_workflow_footer_status

from .workflow_progress import (
    build_startup_workflow_progress_facts,
    build_workflow_progress_from_facts,
    build_workflow_progress_from_facts_and_settings,
)
from .workflow_progress_facts import (
    WorkflowProgressFacts,
    build_workflow_progress_facts_from_runtime_state,
)
from .dock_workflow_sections import (
    CURRENT_DOCK_SECTIONS,
    WIZARD_WORKFLOW_STEPS,
    DockWizardProgress,
    DockWorkflowProgress,
    DockWorkflowSection,
    DockWorkflowStepState,
    DockWorkflowStepStatus,
    build_current_dock_workflow_label,
    build_initial_wizard_step_statuses,
    build_initial_workflow_step_statuses,
    build_progress_wizard_step_statuses,
    build_progress_workflow_step_statuses,
    build_wizard_step_statuses,
    build_workflow_step_statuses,
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
from .workflow_page_specs import (
    DockWorkflowPageSpec,
    build_default_workflow_page_specs,
)

DockWizardPageSpec = DockWorkflowPageSpec
build_default_wizard_page_specs = build_default_workflow_page_specs

from .workflow_settings import (
    COLLAPSED_GROUPS_KEY,
    DEFAULT_COLLAPSED_GROUP_OBJECT_NAMES,
    LAST_STEP_INDEX_KEY,
    LAST_STEP_INDEX_USER_SELECTED_KEY,
    WORKFLOW_SETTINGS_VERSION,
    WORKFLOW_SETTINGS_VERSION_KEY,
    WORKFLOW_STEP_COUNT,
    WorkflowSettingsSnapshot,
    clamp_workflow_step_index,
    ensure_workflow_settings,
    load_workflow_settings,
    preferred_current_key_from_workflow_settings,
    save_collapsed_groups,
    save_workflow_step_index,
    workflow_step_key_for_index,
)

WIZARD_VERSION = WORKFLOW_SETTINGS_VERSION
WIZARD_VERSION_KEY = WORKFLOW_SETTINGS_VERSION_KEY
WIZARD_STEP_COUNT = WORKFLOW_STEP_COUNT
WizardSettingsSnapshot = WorkflowSettingsSnapshot
clamp_wizard_step_index = clamp_workflow_step_index
ensure_wizard_settings = ensure_workflow_settings
load_wizard_settings = load_workflow_settings
preferred_current_key_from_settings = preferred_current_key_from_workflow_settings
save_last_step_index = save_workflow_step_index
wizard_step_key_for_index = workflow_step_key_for_index
from .visual_workflow_action_builder import build_visual_workflow_action
from .visual_workflow_action_builder import build_visual_workflow_action_inputs
from .visual_workflow_action_builder import build_visual_workflow_background_inputs
from .visual_workflow_action_builder import build_visual_workflow_selection_state_handoff
from .visual_workflow_action_builder import build_visual_layer_refs
from .visual_workflow_action_builder import VisualWorkflowActionInputs
from .visual_workflow_action_builder import VisualWorkflowBackgroundInputs
from .visual_workflow_action_builder import VisualWorkflowSettingsSnapshot
from .visual_workflow_action_builder import build_visual_workflow_settings_snapshot

_WIZARD_PROGRESS_COMPAT_EXPORTS = frozenset(
    {
        "WizardProgressFacts",
        "build_startup_wizard_progress_facts",
        "build_wizard_progress_facts_from_runtime_state",
        "build_wizard_progress_from_facts",
        "build_wizard_progress_from_facts_and_settings",
    }
)


def __getattr__(name: str) -> object:
    if name in _WIZARD_PROGRESS_COMPAT_EXPORTS:
        wizard_progress = import_module(".wizard_progress", __name__)
        value = getattr(wizard_progress, name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "ApplyVisualizationAction",
    "after_local_first_control_move_installed",
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
    "DockWizardPageSpec",
    "DockWorkflowPageSpec",
    "DockWorkflowProgress",
    "DockWorkflowSection",
    "DockWorkflowStepState",
    "DockWorkflowStepStatus",
    "CURRENT_DOCK_SECTIONS",
    "LAST_STEP_INDEX_KEY",
    "LAST_STEP_INDEX_USER_SELECTED_KEY",
    "ISSUE_805_REQUIRED_AREAS",
    "LOCAL_FIRST_CONTROL_MOVES",
    "LOCAL_FIRST_DOCK_PAGE_DEFINITIONS",
    "LOCAL_FIRST_WIDGET_MOVES",
    "NONE_ANALYSIS_MODE_LABEL",
    "ADVANCED_FETCH_VISIBILITY_WIDGETS",
    "ANALYSIS_MODE_LABELS",
    "DETAILED_FETCH_VISIBILITY_WIDGETS",
    "MAPBOX_CUSTOM_STYLE_VISIBILITY_WIDGETS",
    "POINT_SAMPLING_VISIBILITY_WIDGETS",
    "LocalFirstControlMove",
    "LocalFirstControlVisibilityUpdate",
    "LocalFirstDockNavigationState",
    "LocalFirstDockPageDefinition",
    "LocalFirstDockPageState",
    "LocalFirstParitySurface",
    "LocalFirstProgressFacts",
    "LocalFirstWidgetMove",
    "WIZARD_WORKFLOW_STEPS",
    "WORKFLOW_SETTINGS_VERSION",
    "WORKFLOW_SETTINGS_VERSION_KEY",
    "WORKFLOW_STEP_COUNT",
    "WIZARD_STEP_COUNT",
    "WIZARD_VERSION",
    "WIZARD_VERSION_KEY",
    "request_local_first_connection_configuration",
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
    "WizardFooterFacts",
    "WizardProgressFacts",
    "WorkflowFooterFacts",
    "WorkflowProgressFacts",
    "WorkflowSettingsSnapshot",
    "WizardSettingsSnapshot",
    "build_advanced_fetch_visibility_update",
    "apply_local_first_visibility_update",
    "bind_local_first_analysis_mode_controls",
    "bind_local_first_basemap_preset_controls",
    "bind_local_first_conditional_visibility_controls",
    "configure_detailed_route_filter_options",
    "configure_detailed_route_strategy_options",
    "configure_local_first_activity_preview_options",
    "configure_local_first_analysis_mode_backing_controls",
    "configure_local_first_temporal_mode_backing_controls",
    "configure_local_first_basemap_options",
    "configure_preview_sort_options",
    "build_current_dock_workflow_label",
    "build_current_activity_preview_request",
    "build_detailed_fetch_visibility_update",
    "build_dock_summary_status",
    "build_initial_wizard_step_statuses",
    "build_initial_workflow_step_statuses",
    "build_issue805_local_first_parity_surfaces",
    "build_local_first_dock_navigation_state",
    "build_local_first_conditional_visibility_updates",
    "build_local_first_filter_description",
    "build_mapbox_custom_style_visibility_update",
    "build_point_sampling_visibility_update",
    "build_progress_wizard_step_statuses",
    "build_progress_workflow_step_statuses",
    "build_stepper_items",
    "build_stepper_states",
    "build_startup_wizard_progress_facts",
    "build_startup_workflow_progress_facts",
    "current_local_first_last_sync_date",
    "build_wizard_filter_description",
    "build_wizard_footer_facts_from_progress_facts",
    "build_wizard_footer_status",
    "build_workflow_footer_facts_from_progress_facts",
    "build_workflow_footer_status",
    "build_default_wizard_page_specs",
    "build_default_workflow_page_specs",
    "build_workflow_progress_facts_from_runtime_state",
    "build_workflow_progress_from_facts",
    "build_workflow_progress_from_facts_and_settings",
    "build_wizard_progress_facts_from_runtime_state",
    "build_wizard_progress_from_facts",
    "build_wizard_progress_from_facts_and_settings",
    "build_wizard_step_statuses",
    "build_workflow_step_statuses",
    "build_visual_layer_refs",
    "build_visual_workflow_action",
    "build_visual_workflow_action_inputs",
    "build_visual_workflow_background_inputs",
    "build_visual_workflow_selection_state_handoff",
    "build_visual_workflow_settings_snapshot",
    "can_request_step",
    "clamp_workflow_step_index",
    "clamp_wizard_step_index",
    "ensure_workflow_settings",
    "ensure_wizard_settings",
    "get_workflow_section",
    "install_local_first_audited_controls",
    "install_local_first_control_move",
    "install_local_first_group_controls",
    "install_local_first_widget_move",
    "install_local_first_widget_controls",
    "issue805_local_first_coverage_by_area",
    "load_workflow_settings",
    "load_wizard_settings",
    "local_first_analysis_mode_options",
    "local_first_control_move_layout",
    "local_first_control_move_parent_panel",
    "local_first_control_move_for_key",
    "local_first_control_move_keys",
    "local_first_control_move_required_widgets_available",
    "local_first_dock_page_keys",
    "local_first_widget_move_widgets",
    "local_first_widget_move_for_key",
    "local_first_widget_move_keys",
    "preferred_current_key_from_settings",
    "preferred_current_key_from_workflow_settings",
    "missing_issue805_local_first_areas",
    "refresh_local_first_conditional_control_visibility",
    "refresh_local_first_control_visibility",
    "remove_widget_from_current_layout",
    "runtime_state_with_local_first_output_path",
    "save_collapsed_groups",
    "save_workflow_step_index",
    "save_last_step_index",
    "set_local_first_analysis_mode",
    "show_local_first_control_group",
    "sync_local_first_basemap_style_fields",
    "update_local_first_mapbox_custom_style_visibility",
    "show_widget",
    "step_index_for_key",
    "step_key_for_index",
    "update_local_first_atlas_document_settings",
    "workflow_step_key_for_index",
    "wizard_step_key_for_index",
]
