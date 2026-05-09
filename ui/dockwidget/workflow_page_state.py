from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from qfit.ui.application.workflow_progress import build_workflow_progress_from_facts
from qfit.ui.application.workflow_progress_facts import WorkflowProgressFacts

from .analysis_page import AnalysisPageState
from .atlas_page import AtlasPageState
from .connection_page import ConnectionPageState
from .map_page import MapPageState
from .sync_page import SyncPageState


_SYNC_IN_PROGRESS_TOOLTIP = "Wait for the current synchronization to finish."


@dataclass(frozen=True)
class DockWorkflowActionCallbacks:
    """Optional adapters for concrete dock workflow page actions.

    Local-first and compatibility wizard shells can expose visible CTAs without
    importing the current dock widget. Production wiring passes bound methods
    here while pure tests keep page widgets independent from the long-scroll dock.
    """

    configure_connection: Callable[[], None] | None = None
    sync_activities: Callable[[], None] | None = None
    store_activities: Callable[[], None] | None = None
    sync_saved_routes: Callable[[], None] | None = None
    clear_database: Callable[[], None] | None = None
    load_activity_layers: Callable[[], None] | None = None
    apply_map_filters: Callable[[], None] | None = None
    run_analysis: Callable[[], None] | None = None
    clear_analysis: Callable[[], None] | None = None
    set_analysis_mode: Callable[[str], None] | None = None
    export_atlas: Callable[[], None] | None = None
    update_atlas_document_settings: Callable[[str, str], None] | None = None


@dataclass(frozen=True)
class WorkflowPageStateSnapshots:
    """Concrete workflow page state defaults derived from workflow facts."""

    connection_state: ConnectionPageState
    sync_state: SyncPageState
    map_state: MapPageState
    analysis_state: AnalysisPageState
    atlas_state: AtlasPageState


def build_workflow_page_states_from_facts(
    facts: WorkflowProgressFacts,
) -> WorkflowPageStateSnapshots:
    """Build page status and CTA defaults from render-neutral progress facts.

    The progress facts model completed workflow milestones. Page CTAs need the
    related prerequisite availability too: for example, the sync step is not
    complete until activities are stored, but its primary action becomes
    available as soon as the connection is configured.
    """

    facts = completed_prefix_facts(facts)
    return WorkflowPageStateSnapshots(
        connection_state=_connection_state_from_facts(facts),
        sync_state=_sync_state_from_facts(facts),
        map_state=_map_state_from_facts(facts),
        analysis_state=_analysis_state_from_facts(facts),
        atlas_state=_atlas_state_from_facts(facts),
    )


def connect_optional_signal(content, signal_name: str, callback) -> None:
    if content is None or callback is None:
        return
    getattr(content, signal_name).connect(callback)


def completed_prefix_facts(facts: WorkflowProgressFacts) -> WorkflowProgressFacts:
    completed = build_workflow_progress_from_facts(facts).completed_keys
    return WorkflowProgressFacts(
        connection_configured=facts.connection_configured,
        activities_fetched=facts.activities_fetched,
        activities_stored="sync" in completed,
        activity_layers_loaded="map" in completed,
        analysis_generated="analysis" in completed,
        atlas_exported="atlas" in completed,
        sync_in_progress=facts.sync_in_progress,
        route_sync_in_progress=facts.route_sync_in_progress,
        atlas_export_in_progress=facts.atlas_export_in_progress,
        preferred_current_key=facts.preferred_current_key,
        fetched_activity_count=facts.fetched_activity_count,
        activity_count=facts.activity_count,
        output_name=facts.output_name,
        analysis_output_name=facts.analysis_output_name,
        atlas_output_name=facts.atlas_output_name,
        background_enabled=facts.background_enabled,
        background_layer_loaded=facts.background_layer_loaded,
        background_name=facts.background_name,
        filters_active=facts.filters_active,
        filtered_activity_count=facts.filtered_activity_count,
        filter_description=facts.filter_description,
        activity_style_preset=facts.activity_style_preset,
        loaded_layer_count=facts.loaded_layer_count,
        last_sync_date=facts.last_sync_date,
    )


def _connection_state_from_facts(facts: WorkflowProgressFacts) -> ConnectionPageState:
    default = ConnectionPageState()
    if facts.connection_configured:
        return ConnectionPageState(
            connected=True,
            connection_configured=True,
            status_text="Strava connected",
            detail_text="Connection is configured; continue to synchronization.",
            credential_summary_text="Strava OAuth credentials are stored in qfit settings",
            primary_action_label="Review connection",
            primary_action_enabled=True,
        )
    if facts.activities_stored:
        return ConnectionPageState(
            connected=True,
            status_text="Local GeoPackage available",
            detail_text=(
                "Strava credentials are optional while loading existing activities."
            ),
            credential_summary_text=(
                "Using an existing GeoPackage; configure Strava only to sync new data"
            ),
            primary_action_label="Configure Strava",
            primary_action_enabled=True,
        )
    return default


def _sync_state_from_facts(facts: WorkflowProgressFacts) -> SyncPageState:
    default = SyncPageState()
    status_text = default.status_text
    detail_text = default.detail_text
    sync_blocked_tooltip = default.primary_action_blocked_tooltip
    if facts.activities_fetched:
        status_text = "Activities fetched"
        detail_text = (
            "Finish synchronization to persist fetched activities in the GeoPackage."
        )
    elif facts.activities_stored:
        status_text = "Activities stored"
        detail_text = (
            "Stored activities are ready to load from the existing GeoPackage."
        )
    elif not facts.connection_configured:
        status_text = "Connection required before sync"
        detail_text = "Configure Strava credentials before syncing activities."
    primary_action_label = default.primary_action_label
    primary_action_kind = default.primary_action_kind
    routes_action_label = default.routes_action_label
    if facts.activities_fetched:
        primary_action_label = "Finish activity sync"
        primary_action_kind = "store"
        sync_blocked_tooltip = ""
    if facts.route_sync_in_progress:
        routes_action_label = "Cancel route sync"
    if facts.sync_in_progress:
        status_text = "Synchronization in progress"
        detail_text = (
            "Wait for the current synchronization to finish before starting another sync."
        )
        primary_action_label = "Sync in progress…"
        primary_action_kind = "sync"
        sync_blocked_tooltip = _SYNC_IN_PROGRESS_TOOLTIP
    return SyncPageState(
        ready=facts.activities_stored,
        status_text=status_text,
        detail_text=detail_text,
        activity_summary_text=_sync_activity_summary(facts, default),
        primary_action_label=primary_action_label,
        primary_action_kind=primary_action_kind,
        primary_action_enabled=(
            facts.activities_fetched or facts.connection_configured
        ) and not facts.sync_in_progress,
        primary_action_blocked_tooltip=sync_blocked_tooltip,
        local_action_enabled=facts.activities_stored and not facts.sync_in_progress,
        local_action_blocked_tooltip=_sync_local_action_blocked_tooltip(facts, default),
        routes_action_label=routes_action_label,
        routes_action_enabled=(
            facts.route_sync_in_progress
            or (facts.connection_configured and not facts.sync_in_progress)
        ),
        routes_action_blocked_tooltip=_sync_routes_action_blocked_tooltip(facts, default),
        clear_action_enabled=(
            bool(facts.output_name)
            and not facts.sync_in_progress
            and not facts.route_sync_in_progress
        ),
        clear_action_blocked_tooltip=_sync_clear_action_blocked_tooltip(facts, default),
    )


def _sync_local_action_blocked_tooltip(
    facts: WorkflowProgressFacts,
    default: SyncPageState,
) -> str:
    if facts.sync_in_progress or facts.route_sync_in_progress:
        return _SYNC_IN_PROGRESS_TOOLTIP
    if not facts.activities_stored:
        return default.local_action_blocked_tooltip
    return ""


def _sync_routes_action_blocked_tooltip(
    facts: WorkflowProgressFacts,
    default: SyncPageState,
) -> str:
    if facts.route_sync_in_progress:
        return ""
    if facts.sync_in_progress:
        return _SYNC_IN_PROGRESS_TOOLTIP
    if not facts.connection_configured:
        return default.routes_action_blocked_tooltip
    return ""


def _sync_clear_action_blocked_tooltip(
    facts: WorkflowProgressFacts,
    default: SyncPageState,
) -> str:
    if facts.sync_in_progress or facts.route_sync_in_progress:
        return _SYNC_IN_PROGRESS_TOOLTIP
    if not facts.output_name:
        return default.clear_action_blocked_tooltip
    return ""


def _sync_activity_summary(
    facts: WorkflowProgressFacts,
    default: SyncPageState,
) -> str:
    if facts.sync_in_progress:
        return _sync_in_progress_summary(facts)
    if facts.activities_stored:
        return _stored_activity_summary(facts)
    if not facts.connection_configured:
        return "Connect to Strava to enable synchronization"
    if facts.activities_fetched:
        return _fetched_activity_summary(facts)
    return default.activity_summary_text


def _sync_in_progress_summary(facts: WorkflowProgressFacts) -> str:
    if not facts.activities_stored:
        return "Synchronization in progress"
    if facts.output_name is None:
        return "Updating stored activities"
    return f"Updating activities in {facts.output_name}"


def _stored_activity_summary(facts: WorkflowProgressFacts) -> str:
    if facts.activity_count is None and facts.output_name is None:
        return "Activities stored in GeoPackage"
    if facts.activity_count is None:
        activity_summary = "Activities"
    else:
        noun = "activity" if facts.activity_count == 1 else "activities"
        activity_summary = f"{max(facts.activity_count, 0)} {noun}"
    output_summary = facts.output_name or "GeoPackage"
    return f"{activity_summary} stored in {output_summary}"


def _fetched_activity_summary(facts: WorkflowProgressFacts) -> str:
    if facts.fetched_activity_count is None:
        return "Fetched activities ready to finish sync"
    noun = "activity" if facts.fetched_activity_count == 1 else "activities"
    return f"{max(facts.fetched_activity_count, 0)} fetched {noun} ready to finish sync"


def _map_state_from_facts(facts: WorkflowProgressFacts) -> MapPageState:
    default = MapPageState()
    activity_layers_loaded = facts.activity_layers_loaded
    stored_without_loaded_layers = facts.activities_stored and not activity_layers_loaded
    return MapPageState(
        loaded=activity_layers_loaded,
        status_text=_map_status_text(facts),
        layer_summary_text=_map_layer_summary(facts),
        background_summary_text=_map_background_summary(facts, default),
        style_summary_text=_map_style_summary(facts, default),
        filter_summary_text=_map_filter_summary(facts, default),
        load_action_label=(
            "Reload stored map layers" if activity_layers_loaded else default.load_action_label
        ),
        load_action_enabled=activity_layers_loaded,
        load_action_blocked_tooltip=(
            "Use the primary action to load stored map layers."
            if stored_without_loaded_layers
            else default.load_action_blocked_tooltip
        ),
        primary_action_label=(
            "Load stored map layers"
            if stored_without_loaded_layers
            else default.primary_action_label
        ),
        apply_action_enabled=facts.activities_stored,
        apply_action_blocked_tooltip=(
            "Sync activities before loading stored map layers."
            if not facts.activities_stored
            else default.apply_action_blocked_tooltip
        ),
    )


def _map_status_text(facts: WorkflowProgressFacts) -> str:
    if facts.activity_layers_loaded:
        return "Stored map layers loaded"
    if facts.activities_stored:
        return "Stored map layers ready to load"
    return "Sync required before map loading"


def _map_layer_summary(facts: WorkflowProgressFacts) -> str:
    if facts.activity_layers_loaded:
        if facts.output_name is not None:
            return f"Stored map layers from {facts.output_name} are loaded on the map"
        return "Stored map layers are loaded on the map"
    if facts.activities_stored:
        if facts.output_name is not None:
            return f"Stored map layers in {facts.output_name} are ready to load"
        return "Stored map layers are ready to load"
    return "Sync activities before loading stored map layers"


def _map_background_summary(facts: WorkflowProgressFacts, default: MapPageState) -> str:
    if not facts.background_enabled:
        return default.background_summary_text
    if facts.background_layer_loaded:
        if facts.background_name is not None:
            return f"Basemap loaded: {facts.background_name}"
        return "Basemap loaded"
    if facts.background_name is not None:
        return f"Basemap ready to load: {facts.background_name}"
    return "Basemap enabled"


def _map_style_summary(facts: WorkflowProgressFacts, default: MapPageState) -> str:
    if facts.activity_style_preset is None:
        return default.style_summary_text
    return f"Selected activity style: {facts.activity_style_preset}"


def _map_filter_summary(facts: WorkflowProgressFacts, default: MapPageState) -> str:
    if not facts.activity_layers_loaded:
        return default.filter_summary_text
    if facts.filters_active:
        return _map_active_filter_summary(facts)
    return "All loaded activities are visible"


def _map_active_filter_summary(facts: WorkflowProgressFacts) -> str:
    if facts.filtered_activity_count is None:
        summary = "Subset filters are active"
    else:
        noun = "activity" if facts.filtered_activity_count == 1 else "activities"
        summary = f"Filters match {max(facts.filtered_activity_count, 0)} loaded {noun}"
    filter_description = (facts.filter_description or "").strip()
    if not filter_description:
        return summary
    return f"{summary} · {filter_description}"


def _analysis_state_from_facts(facts: WorkflowProgressFacts) -> AnalysisPageState:
    default = AnalysisPageState()
    return AnalysisPageState(
        ready=facts.analysis_generated,
        status_text=_analysis_status_text(facts, default),
        input_summary_text=_analysis_input_summary(facts),
        result_summary_text=(
            _analysis_result_summary(facts)
            if facts.analysis_generated
            else default.result_summary_text
        ),
        primary_action_label=(
            "Refresh analysis" if facts.analysis_generated else default.primary_action_label
        ),
        primary_action_enabled=facts.activity_layers_loaded,
    )


def _analysis_status_text(
    facts: WorkflowProgressFacts,
    default: AnalysisPageState,
) -> str:
    if facts.analysis_generated:
        return "Analysis ready"
    if not facts.activity_layers_loaded:
        return "Map layers required before analysis"
    return default.status_text


def _analysis_input_summary(facts: WorkflowProgressFacts) -> str:
    if not facts.activity_layers_loaded:
        return "Load activity layers before running analysis"
    if facts.filters_active:
        return _analysis_filtered_input_summary(facts)
    return _with_analysis_input_context(
        _analysis_loaded_activity_layer_summary(facts),
        facts=facts,
    )


def _analysis_filtered_input_summary(facts: WorkflowProgressFacts) -> str:
    if facts.filtered_activity_count is None:
        summary = "Filtered activity subset ready for analysis"
    else:
        noun = "activity" if facts.filtered_activity_count == 1 else "activities"
        summary = (
            f"{max(facts.filtered_activity_count, 0)} filtered {noun} "
            "ready for analysis"
        )
    return _with_analysis_input_context(summary, facts=facts)


def _analysis_loaded_activity_layer_summary(facts: WorkflowProgressFacts) -> str:
    if facts.output_name is None:
        return "Activity layer ready for analysis"
    return f"Activity layer from {facts.output_name} ready for analysis"


def _with_analysis_input_context(summary: str, *, facts: WorkflowProgressFacts) -> str:
    details = tuple(
        detail
        for detail in (
            _analysis_filter_description(facts),
            _analysis_loaded_layer_count_summary(facts),
        )
        if detail
    )
    if not details:
        return summary
    return f"{summary} · {' · '.join(details)}"


def _analysis_filter_description(facts: WorkflowProgressFacts) -> str | None:
    if not facts.filters_active:
        return None
    description = (facts.filter_description or "").strip()
    return description or None


def _analysis_loaded_layer_count_summary(facts: WorkflowProgressFacts) -> str | None:
    if facts.loaded_layer_count is None:
        return None
    count = max(facts.loaded_layer_count, 0)
    noun = "qfit layer" if count == 1 else "qfit layers"
    return f"{count} {noun} loaded"


def _analysis_result_summary(facts: WorkflowProgressFacts) -> str:
    if facts.analysis_output_name is not None:
        return f"Analysis output {facts.analysis_output_name} is available"
    return "Analysis outputs are available"


def _atlas_state_from_facts(facts: WorkflowProgressFacts) -> AtlasPageState:
    default = AtlasPageState()
    status_text = _atlas_status_text(facts, default)
    output_summary_text = _atlas_output_summary(facts, default)
    atlas_blocked_tooltip = default.primary_action_blocked_tooltip
    primary_action_label = (
        "Refresh atlas PDF" if facts.atlas_exported else default.primary_action_label
    )
    primary_action_enabled = facts.activity_layers_loaded
    if facts.atlas_export_in_progress:
        status_text = "Atlas export in progress"
        primary_action_label = "Cancel export"
        primary_action_enabled = True
        atlas_blocked_tooltip = "Cancel the current atlas PDF export."
    return AtlasPageState(
        ready=facts.atlas_exported,
        status_text=status_text,
        input_summary_text=_atlas_input_summary(facts),
        output_summary_text=output_summary_text,
        primary_action_label=primary_action_label,
        primary_action_enabled=primary_action_enabled,
        primary_action_blocked_tooltip=atlas_blocked_tooltip,
    )


def _atlas_status_text(facts: WorkflowProgressFacts, default: AtlasPageState) -> str:
    if facts.atlas_exported:
        return "Atlas PDF exported"
    if not facts.activity_layers_loaded:
        return "Map layers required before atlas export"
    return default.status_text


def _atlas_input_summary(facts: WorkflowProgressFacts) -> str:
    if not facts.activity_layers_loaded:
        return "Load activity layers before exporting atlas PDF"
    if facts.analysis_output_name is not None:
        return _with_atlas_selection_context(
            f"Analysis output {facts.analysis_output_name} ready for atlas export",
            facts=facts,
        )
    if facts.analysis_generated:
        return _with_atlas_selection_context(
            "Analysis outputs ready for atlas export",
            facts=facts,
        )
    return _atlas_activity_layer_input_summary(facts)


def _atlas_activity_layer_input_summary(facts: WorkflowProgressFacts) -> str:
    selected_activity_count = _atlas_selected_activity_count(facts)
    if selected_activity_count is not None:
        summary = _atlas_selected_activity_input_summary(
            facts,
            selected_activity_count=selected_activity_count,
        )
    elif facts.filters_active:
        summary = "Filtered activity subset ready for atlas export"
    elif facts.output_name is not None:
        summary = f"Activity layers from {facts.output_name} ready for atlas export"
    else:
        summary = "Activity layers ready for atlas export"
    details = tuple(
        detail
        for detail in (
            _analysis_filter_description(facts),
            _analysis_loaded_layer_count_summary(facts),
            _atlas_page_count_summary(selected_activity_count),
        )
        if detail
    )
    if not details:
        return summary
    return f"{summary} · {' · '.join(details)}"


def _with_atlas_selection_context(summary: str, *, facts: WorkflowProgressFacts) -> str:
    selected_activity_count = _atlas_selected_activity_count(facts)
    details = tuple(
        detail
        for detail in (
            _atlas_selected_activity_count_summary(selected_activity_count),
            _atlas_page_count_summary(selected_activity_count),
        )
        if detail
    )
    if not details:
        return summary
    return f"{summary} · {' · '.join(details)}"


def _atlas_selected_activity_count(facts: WorkflowProgressFacts) -> int | None:
    if facts.filters_active:
        if facts.filtered_activity_count is not None:
            return max(facts.filtered_activity_count, 0)
        return None
    if facts.activity_count is not None:
        return max(facts.activity_count, 0)
    return None


def _atlas_selected_activity_count_summary(
    selected_activity_count: int | None,
) -> str | None:
    if selected_activity_count is None:
        return None
    noun = "activity" if selected_activity_count == 1 else "activities"
    return f"{selected_activity_count} selected {noun}"


def _atlas_selected_activity_input_summary(
    facts: WorkflowProgressFacts,
    *,
    selected_activity_count: int,
) -> str:
    noun = "activity" if selected_activity_count == 1 else "activities"
    prefix = f"{selected_activity_count} selected {noun}"
    if facts.filters_active:
        return f"{prefix} ready for atlas export"
    if facts.output_name is not None:
        return f"{prefix} from {facts.output_name} ready for atlas export"
    return f"{prefix} ready for atlas export"


def _atlas_page_count_summary(selected_activity_count: int | None) -> str | None:
    if selected_activity_count is None:
        return None
    page_noun = "page" if selected_activity_count == 1 else "pages"
    return (
        f"Atlas exports {selected_activity_count} PDF {page_noun}, "
        "one per selected activity"
    )


def _atlas_output_summary(
    facts: WorkflowProgressFacts,
    default: AtlasPageState,
) -> str:
    if facts.atlas_export_in_progress:
        if facts.atlas_output_name is not None:
            return f"Exporting {facts.atlas_output_name}"
        return "PDF export is running."
    if facts.atlas_exported:
        if facts.atlas_output_name is not None:
            return f"Latest atlas PDF exported to {facts.atlas_output_name}"
        return "Latest atlas PDF has been exported"
    if facts.atlas_output_name is not None:
        return f"Ready to export {facts.atlas_output_name}"
    return default.output_summary_text


# Backward-compatible names while the retired wizard shell is still importable.
WizardActionCallbacks = DockWorkflowActionCallbacks
WizardPageStateSnapshots = WorkflowPageStateSnapshots
build_wizard_page_states_from_facts = build_workflow_page_states_from_facts


__all__ = [
    "DockWorkflowActionCallbacks",
    "WorkflowPageStateSnapshots",
    "WizardActionCallbacks",
    "WizardPageStateSnapshots",
    "build_workflow_page_states_from_facts",
    "build_wizard_page_states_from_facts",
    "completed_prefix_facts",
    "connect_optional_signal",
]
