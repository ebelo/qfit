from __future__ import annotations

from collections.abc import Callable, Collection, Sequence
from dataclasses import dataclass
from typing import TypeVar

from qfit.ui.application.dock_workflow_sections import (
    DockWizardProgress,
    DockWorkflowStepStatus,
    build_progress_wizard_step_statuses,
)
from qfit.ui.application.stepper_presenter import (
    can_request_step,
    step_index_for_key,
)
from qfit.ui.application.wizard_footer_status import (
    WizardFooterFacts,
    build_wizard_footer_facts_from_progress_facts,
    build_wizard_footer_status,
)
from qfit.ui.application.wizard_page_specs import (
    DockWizardPageSpec,
    build_default_wizard_page_specs,
)
from qfit.ui.application.wizard_progress import (
    WizardProgressFacts,
    build_wizard_progress_from_facts_and_settings,
    build_wizard_progress_from_facts,
)
from qfit.ui.application.wizard_settings import WizardSettingsSnapshot

from .analysis_page import (
    AnalysisPageContent,
    AnalysisPageState,
    install_analysis_page_content,
)
from .atlas_page import AtlasPageContent, AtlasPageState, install_atlas_page_content
from .connection_page import (
    ConnectionPageContent,
    ConnectionPageState,
    install_connection_page_content,
)
from .map_page import MapPageContent, MapPageState, install_map_page_content
from .sync_page import SyncPageContent, SyncPageState, install_sync_page_content
from .step_page import (
    WizardStepPage,
    apply_wizard_step_page_statuses,
    install_wizard_step_pages,
)
from .wizard_page import WizardPage, install_wizard_pages
from .wizard_shell import WizardShell
from .wizard_shell_presenter import WizardShellPresenter


_StateT = TypeVar("_StateT")
WizardCompositionPage = WizardPage | WizardStepPage
_SYNC_IN_PROGRESS_TOOLTIP = "Wait for the current synchronization to finish."


@dataclass(frozen=True)
class WizardActionCallbacks:
    """Optional adapters for concrete wizard page actions.

    The placeholder shell can now expose visible CTAs without importing the
    current dock widget. A future dock swap can pass bound methods here while
    pure tests keep the page widgets independent from the long-scroll dock.
    """

    configure_connection: Callable[[], None] | None = None
    sync_activities: Callable[[], None] | None = None
    sync_saved_routes: Callable[[], None] | None = None
    clear_database: Callable[[], None] | None = None
    load_activity_layers: Callable[[], None] | None = None
    apply_map_filters: Callable[[], None] | None = None
    run_analysis: Callable[[], None] | None = None
    set_analysis_mode: Callable[[str], None] | None = None
    export_atlas: Callable[[], None] | None = None
    update_atlas_document_settings: Callable[[str, str], None] | None = None


@dataclass(frozen=True)
class WizardPageStateSnapshots:
    """Concrete wizard page state defaults derived from workflow facts."""

    connection_state: ConnectionPageState
    sync_state: SyncPageState
    map_state: MapPageState
    analysis_state: AnalysisPageState
    atlas_state: AtlasPageState


@dataclass
class WizardShellComposition:
    """Concrete placeholder wizard assembly for the future dock replacement.

    The composition keeps the shell, page placeholders, and presenter wiring in
    one reusable unit without replacing the current production dock yet. That
    gives #609 a safe integration seam for the eventual dock swap while keeping
    this slice focused on wizard-forward UI structure.
    """

    shell: WizardShell
    pages: tuple[WizardCompositionPage, ...]
    presenter: WizardShellPresenter
    connection_content: ConnectionPageContent | None = None
    sync_content: SyncPageContent | None = None
    map_content: MapPageContent | None = None
    analysis_content: AnalysisPageContent | None = None
    atlas_content: AtlasPageContent | None = None
    action_callbacks: WizardActionCallbacks | None = None
    connection_state: ConnectionPageState | None = None
    sync_state: SyncPageState | None = None
    map_state: MapPageState | None = None
    analysis_state: AnalysisPageState | None = None
    atlas_state: AtlasPageState | None = None
    on_current_step_changed: Callable[[int], None] | None = None


def build_placeholder_wizard_shell(
    *,
    parent=None,
    footer_text: str = "",
    progress: DockWizardProgress | None = None,
    progress_facts: WizardProgressFacts | None = None,
    wizard_settings: WizardSettingsSnapshot | None = None,
    specs: Sequence[DockWizardPageSpec] | None = None,
    use_step_pages: bool = True,
    connection_state: ConnectionPageState | None = None,
    sync_state: SyncPageState | None = None,
    map_state: MapPageState | None = None,
    analysis_state: AnalysisPageState | None = None,
    atlas_state: AtlasPageState | None = None,
    on_current_step_changed: Callable[[int], None] | None = None,
) -> WizardShellComposition:
    """Build the placeholder #609 wizard shell with pages and presenter wired.

    Pages are installed before the presenter renders so the initial progress
    snapshot selects the matching visible page immediately. The helper does not
    bind any current long-scroll dock controls into the shell; page content can
    migrate later through the stable ``WizardPage.body_layout()`` seams. The
    optional step-change callback is the future dock's seam for persisting
    ``ui/last_step_index`` when users navigate the wizard. The shell now uses
    the richer StepPage chrome from the Option B spec by default while preserving
    the same content-installer and presenter seams; pass ``use_step_pages=False``
    only for legacy placeholder-page compatibility tests.
    """

    page_state_defaults = _page_state_defaults_from_progress_facts(progress_facts)
    connection_state = _resolve_state(
        connection_state,
        page_state_defaults.connection_state if page_state_defaults is not None else None,
        ConnectionPageState,
    )
    sync_state = _resolve_state(
        sync_state,
        page_state_defaults.sync_state if page_state_defaults is not None else None,
        SyncPageState,
    )
    map_state = _resolve_state(
        map_state,
        page_state_defaults.map_state if page_state_defaults is not None else None,
        MapPageState,
    )
    analysis_state = _resolve_state(
        analysis_state,
        page_state_defaults.analysis_state if page_state_defaults is not None else None,
        AnalysisPageState,
    )
    atlas_state = _resolve_state(
        atlas_state,
        page_state_defaults.atlas_state if page_state_defaults is not None else None,
        AtlasPageState,
    )
    resolved_progress = _resolve_progress(
        progress=progress,
        progress_facts=progress_facts,
        wizard_settings=wizard_settings,
    )
    footer_facts = _footer_facts_from_progress_facts(progress_facts)
    page_specs = _resolve_page_specs(specs)
    shell = WizardShell(
        parent=parent,
        footer_text=footer_text
        or _build_default_footer_text(
            installed_keys={spec.key for spec in page_specs},
            connection_state=connection_state,
            sync_state=sync_state,
            map_state=map_state,
            analysis_state=analysis_state,
            atlas_state=atlas_state,
        ),
    )
    _apply_footer_facts(shell.footer_bar, footer_facts)
    pages = _install_shell_pages(shell, specs=page_specs, use_step_pages=use_step_pages)
    connection_content = _install_connection_content(
        pages,
        connection_state=connection_state,
    )
    sync_content = _install_sync_content(pages, sync_state=sync_state)
    map_content = _install_map_content(pages, map_state=map_state)
    analysis_content = _install_analysis_content(
        pages,
        analysis_state=analysis_state,
    )
    atlas_content = _install_atlas_content(pages, atlas_state=atlas_state)
    _validate_progress_targets_installed_page(resolved_progress, pages)
    presenter = WizardShellPresenter(
        shell,
        resolved_progress,
        page_indices_by_key=_build_page_indices_by_key(pages),
        on_current_step_changed=on_current_step_changed,
    )
    _connect_step_page_navigation(shell, pages, presenter)
    return WizardShellComposition(
        shell=shell,
        pages=pages,
        presenter=presenter,
        connection_content=connection_content,
        sync_content=sync_content,
        map_content=map_content,
        analysis_content=analysis_content,
        atlas_content=atlas_content,
        connection_state=connection_state,
        sync_state=sync_state,
        map_state=map_state,
        analysis_state=analysis_state,
        atlas_state=atlas_state,
        on_current_step_changed=on_current_step_changed,
    )


def refresh_wizard_shell_composition(
    composition: WizardShellComposition,
    *,
    connection_state: ConnectionPageState | None = None,
    sync_state: SyncPageState | None = None,
    map_state: MapPageState | None = None,
    analysis_state: AnalysisPageState | None = None,
    atlas_state: AtlasPageState | None = None,
    footer_text: str | None = None,
    progress: DockWizardProgress | None = None,
    progress_facts: WizardProgressFacts | None = None,
    wizard_settings: WizardSettingsSnapshot | None = None,
) -> WizardShellComposition:
    """Refresh installed wizard page state without rebuilding the shell.

    This is the small adapter seam the future dock can use when real workflow
    facts change: update only the installed page widgets, then refresh the
    persistent footer and optional stepper progress from the same render-neutral
    state snapshots. Missing page content is skipped so partial/spec-filtered
    wizard assemblies remain valid. When ``progress_facts`` are provided, their
    derived page states intentionally replace prior composition state defaults;
    pass an explicit page state argument for any copy/availability override that
    should win for that refresh.
    """

    page_state_defaults = _page_state_defaults_from_progress_facts(progress_facts)
    existing_connection_state = (
        page_state_defaults.connection_state
        if page_state_defaults is not None
        else composition.connection_state
    )
    existing_sync_state = (
        page_state_defaults.sync_state
        if page_state_defaults is not None
        else composition.sync_state
    )
    existing_map_state = (
        page_state_defaults.map_state
        if page_state_defaults is not None
        else composition.map_state
    )
    existing_analysis_state = (
        page_state_defaults.analysis_state
        if page_state_defaults is not None
        else composition.analysis_state
    )
    existing_atlas_state = (
        page_state_defaults.atlas_state
        if page_state_defaults is not None
        else composition.atlas_state
    )
    next_connection_state = _resolve_state(
        connection_state,
        existing_connection_state,
        ConnectionPageState,
    )
    next_sync_state = _resolve_state(
        sync_state,
        existing_sync_state,
        SyncPageState,
    )
    next_map_state = _resolve_state(
        map_state,
        existing_map_state,
        MapPageState,
    )
    next_analysis_state = _resolve_state(
        analysis_state,
        existing_analysis_state,
        AnalysisPageState,
    )
    next_atlas_state = _resolve_state(
        atlas_state,
        existing_atlas_state,
        AtlasPageState,
    )
    resolved_progress = _resolve_progress(
        progress=progress,
        progress_facts=progress_facts,
        wizard_settings=wizard_settings,
    )
    footer_facts = _footer_facts_from_progress_facts(progress_facts)
    _validate_progress_targets_installed_page(resolved_progress, composition.pages)

    if composition.connection_content is not None:
        composition.connection_content.set_state(next_connection_state)
    if composition.sync_content is not None:
        composition.sync_content.set_state(next_sync_state)
    if composition.map_content is not None:
        composition.map_content.set_state(next_map_state)
    if composition.analysis_content is not None:
        composition.analysis_content.set_state(next_analysis_state)
    if composition.atlas_content is not None:
        composition.atlas_content.set_state(next_atlas_state)

    composition.shell.set_footer_text(
        footer_text
        if footer_text is not None
        else _build_default_footer_text(
            installed_keys={page.spec.key for page in composition.pages},
            connection_state=next_connection_state,
            sync_state=next_sync_state,
            map_state=next_map_state,
            analysis_state=next_analysis_state,
            atlas_state=next_atlas_state,
        )
    )
    _apply_footer_facts(composition.shell.footer_bar, footer_facts)
    if resolved_progress is not None:
        composition.presenter.set_progress(resolved_progress)
        _sync_step_page_navigation_buttons(composition.pages, composition.presenter)
        _sync_step_page_status_pills(composition.pages, composition.presenter)

    composition.connection_state = next_connection_state
    composition.sync_state = next_sync_state
    composition.map_state = next_map_state
    composition.analysis_state = next_analysis_state
    composition.atlas_state = next_atlas_state
    return composition


def connect_wizard_action_callbacks(
    composition: WizardShellComposition,
    callbacks: WizardActionCallbacks,
) -> WizardShellComposition:
    """Wire concrete action callbacks into an assembled wizard shell.

    This keeps the reusable #609 shell decoupled from ``QfitDockWidget`` while
    giving the future dock swap a single adapter seam for visible page CTAs.
    Missing page content is skipped so partial wizard assemblies remain safe.
    """

    if composition.action_callbacks is not None:
        return composition

    _connect_action_callbacks(
        connection_content=composition.connection_content,
        sync_content=composition.sync_content,
        map_content=composition.map_content,
        analysis_content=composition.analysis_content,
        atlas_content=composition.atlas_content,
        callbacks=callbacks,
    )
    composition.action_callbacks = callbacks
    return composition


def build_wizard_page_states_from_facts(
    facts: WizardProgressFacts,
) -> WizardPageStateSnapshots:
    """Build page status and CTA defaults from render-neutral progress facts.

    The progress facts model completed workflow milestones. Page CTAs need the
    related prerequisite availability too: for example, the sync step is not
    complete until activities are stored, but its primary action becomes
    available as soon as the connection is configured.
    """

    facts = _completed_prefix_facts(facts)
    return WizardPageStateSnapshots(
        connection_state=_connection_state_from_facts(facts),
        sync_state=_sync_state_from_facts(facts),
        map_state=_map_state_from_facts(facts),
        analysis_state=_analysis_state_from_facts(facts),
        atlas_state=_atlas_state_from_facts(facts),
    )


def _connect_action_callbacks(
    *,
    connection_content: ConnectionPageContent | None,
    sync_content: SyncPageContent | None,
    map_content: MapPageContent | None,
    analysis_content: AnalysisPageContent | None,
    atlas_content: AtlasPageContent | None,
    callbacks: WizardActionCallbacks,
) -> None:
    _connect_optional_signal(
        connection_content,
        "configureRequested",
        callbacks.configure_connection,
    )
    _connect_optional_signal(sync_content, "syncRequested", callbacks.sync_activities)
    _connect_optional_signal(
        sync_content,
        "syncRoutesRequested",
        callbacks.sync_saved_routes,
    )
    _connect_optional_signal(
        sync_content,
        "loadActivitiesRequested",
        callbacks.load_activity_layers,
    )
    _connect_optional_signal(
        sync_content,
        "clearDatabaseRequested",
        callbacks.clear_database,
    )
    _connect_optional_signal(
        map_content,
        "loadLayersRequested",
        callbacks.load_activity_layers,
    )
    _connect_optional_signal(
        map_content,
        "applyFiltersRequested",
        callbacks.apply_map_filters,
    )
    _connect_optional_signal(
        analysis_content,
        "runAnalysisRequested",
        callbacks.run_analysis,
    )
    _connect_optional_signal(
        analysis_content,
        "analysisModeChanged",
        callbacks.set_analysis_mode,
    )
    _connect_optional_signal(atlas_content, "exportAtlasRequested", callbacks.export_atlas)
    _connect_optional_signal(
        atlas_content,
        "atlasDocumentSettingsChanged",
        callbacks.update_atlas_document_settings,
    )


def _connect_optional_signal(content, signal_name: str, callback) -> None:
    if content is None or callback is None:
        return
    getattr(content, signal_name).connect(callback)


def _resolve_progress(
    *,
    progress: DockWizardProgress | None,
    progress_facts: WizardProgressFacts | None,
    wizard_settings: WizardSettingsSnapshot | None,
) -> DockWizardProgress | None:
    if progress is not None and (progress_facts is not None or wizard_settings is not None):
        raise ValueError("Pass progress or progress_facts/wizard_settings, not both")
    if progress_facts is None and wizard_settings is None:
        return progress
    facts = progress_facts or WizardProgressFacts()
    if wizard_settings is not None:
        return build_wizard_progress_from_facts_and_settings(facts, wizard_settings)
    return build_wizard_progress_from_facts(facts)


def _page_state_defaults_from_progress_facts(
    progress_facts: WizardProgressFacts | None,
) -> WizardPageStateSnapshots | None:
    if progress_facts is None:
        return None
    return build_wizard_page_states_from_facts(progress_facts)


def _completed_prefix_facts(facts: WizardProgressFacts) -> WizardProgressFacts:
    completed = build_wizard_progress_from_facts(facts).completed_keys
    return WizardProgressFacts(
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


def _footer_facts_from_progress_facts(
    progress_facts: WizardProgressFacts | None,
) -> WizardFooterFacts | None:
    if progress_facts is None:
        return None
    return build_wizard_footer_facts_from_progress_facts(
        _completed_prefix_facts(progress_facts)
    )


def _apply_footer_facts(footer_bar, footer_facts: WizardFooterFacts | None) -> None:
    if footer_facts is None:
        return
    footer_bar.set_strava(footer_facts.strava_connected)
    footer_bar.set_activity_count(footer_facts.activity_count)
    footer_bar.set_sync_date(footer_facts.last_sync_date)
    footer_bar.set_layer_count(footer_facts.layer_count)
    footer_bar.set_gpkg_path(footer_facts.gpkg_path)


def _connection_state_from_facts(facts: WizardProgressFacts) -> ConnectionPageState:
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


def _sync_state_from_facts(facts: WizardProgressFacts) -> SyncPageState:
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
    routes_action_label = default.routes_action_label
    if facts.activities_fetched:
        primary_action_label = "Finish activity sync"
    if facts.route_sync_in_progress:
        routes_action_label = "Cancel route sync"
    if facts.sync_in_progress:
        status_text = "Synchronization in progress"
        detail_text = (
            "Wait for the current synchronization to finish before starting another sync."
        )
        primary_action_label = "Sync in progress…"
        sync_blocked_tooltip = _SYNC_IN_PROGRESS_TOOLTIP
    return SyncPageState(
        ready=facts.activities_stored,
        status_text=status_text,
        detail_text=detail_text,
        activity_summary_text=_sync_activity_summary(facts, default),
        primary_action_label=primary_action_label,
        primary_action_enabled=facts.connection_configured and not facts.sync_in_progress,
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
    facts: WizardProgressFacts,
    default: SyncPageState,
) -> str:
    if facts.sync_in_progress or facts.route_sync_in_progress:
        return _SYNC_IN_PROGRESS_TOOLTIP
    if not facts.activities_stored:
        return default.local_action_blocked_tooltip
    return ""


def _sync_routes_action_blocked_tooltip(
    facts: WizardProgressFacts,
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
    facts: WizardProgressFacts,
    default: SyncPageState,
) -> str:
    if facts.sync_in_progress or facts.route_sync_in_progress:
        return _SYNC_IN_PROGRESS_TOOLTIP
    if not facts.output_name:
        return default.clear_action_blocked_tooltip
    return ""


def _sync_activity_summary(
    facts: WizardProgressFacts,
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


def _sync_in_progress_summary(facts: WizardProgressFacts) -> str:
    if not facts.activities_stored:
        return "Synchronization in progress"
    if facts.output_name is None:
        return "Updating stored activities"
    return f"Updating activities in {facts.output_name}"


def _stored_activity_summary(facts: WizardProgressFacts) -> str:
    if facts.activity_count is None and facts.output_name is None:
        return "Activities stored in GeoPackage"
    if facts.activity_count is None:
        activity_summary = "Activities"
    else:
        noun = "activity" if facts.activity_count == 1 else "activities"
        activity_summary = f"{max(facts.activity_count, 0)} {noun}"
    output_summary = facts.output_name or "GeoPackage"
    return f"{activity_summary} stored in {output_summary}"


def _fetched_activity_summary(facts: WizardProgressFacts) -> str:
    if facts.fetched_activity_count is None:
        return "Fetched activities ready to finish sync"
    noun = "activity" if facts.fetched_activity_count == 1 else "activities"
    return f"{max(facts.fetched_activity_count, 0)} fetched {noun} ready to finish sync"


def _map_state_from_facts(facts: WizardProgressFacts) -> MapPageState:
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
            "Reload activity layers" if activity_layers_loaded else default.load_action_label
        ),
        load_action_enabled=activity_layers_loaded,
        load_action_blocked_tooltip=(
            "Use the primary action to load activity layers."
            if stored_without_loaded_layers
            else default.load_action_blocked_tooltip
        ),
        primary_action_label=(
            "Load activity layers"
            if stored_without_loaded_layers
            else default.primary_action_label
        ),
        apply_action_enabled=facts.activities_stored,
        apply_action_blocked_tooltip=(
            "Sync activities before loading map layers."
            if not facts.activities_stored
            else default.apply_action_blocked_tooltip
        ),
    )


def _map_status_text(facts: WizardProgressFacts) -> str:
    if facts.activity_layers_loaded:
        return "Activity layers loaded"
    if facts.activities_stored:
        return "Stored activities ready to load"
    return "Sync required before map loading"


def _map_layer_summary(facts: WizardProgressFacts) -> str:
    if facts.activity_layers_loaded:
        if facts.output_name is not None:
            return f"Activity layers from {facts.output_name} are loaded on the map"
        return "Activity layers are loaded on the map"
    if facts.activities_stored:
        if facts.output_name is not None:
            return f"Stored activities in {facts.output_name} are ready to load"
        return "Stored activities are ready to load"
    return "Sync activities before loading map layers"


def _map_background_summary(facts: WizardProgressFacts, default: MapPageState) -> str:
    if not facts.background_enabled:
        return default.background_summary_text
    if facts.background_layer_loaded:
        if facts.background_name is not None:
            return f"Basemap loaded: {facts.background_name}"
        return "Basemap loaded"
    if facts.background_name is not None:
        return f"Basemap ready to load: {facts.background_name}"
    return "Basemap enabled"


def _map_style_summary(facts: WizardProgressFacts, default: MapPageState) -> str:
    if facts.activity_style_preset is None:
        return default.style_summary_text
    return f"Selected activity style: {facts.activity_style_preset}"


def _map_filter_summary(facts: WizardProgressFacts, default: MapPageState) -> str:
    if not facts.activity_layers_loaded:
        return default.filter_summary_text
    if facts.filters_active:
        return _map_active_filter_summary(facts)
    return "All loaded activities are visible"


def _map_active_filter_summary(facts: WizardProgressFacts) -> str:
    if facts.filtered_activity_count is None:
        summary = "Subset filters are active"
    else:
        noun = "activity" if facts.filtered_activity_count == 1 else "activities"
        summary = f"Filters match {max(facts.filtered_activity_count, 0)} loaded {noun}"
    filter_description = (facts.filter_description or "").strip()
    if not filter_description:
        return summary
    return f"{summary} · {filter_description}"


def _analysis_state_from_facts(facts: WizardProgressFacts) -> AnalysisPageState:
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
    facts: WizardProgressFacts,
    default: AnalysisPageState,
) -> str:
    if facts.analysis_generated:
        return "Analysis ready"
    if not facts.activity_layers_loaded:
        return "Map layers required before analysis"
    return default.status_text


def _analysis_input_summary(facts: WizardProgressFacts) -> str:
    if not facts.activity_layers_loaded:
        return "Load activity layers before running analysis"
    if facts.filters_active:
        return _analysis_filtered_input_summary(facts)
    return _with_analysis_input_context(
        _analysis_loaded_activity_layer_summary(facts),
        facts=facts,
    )


def _analysis_filtered_input_summary(facts: WizardProgressFacts) -> str:
    if facts.filtered_activity_count is None:
        summary = "Filtered activity subset ready for analysis"
    else:
        noun = "activity" if facts.filtered_activity_count == 1 else "activities"
        summary = (
            f"{max(facts.filtered_activity_count, 0)} filtered {noun} "
            "ready for analysis"
        )
    return _with_analysis_input_context(summary, facts=facts)


def _analysis_loaded_activity_layer_summary(facts: WizardProgressFacts) -> str:
    if facts.output_name is None:
        return "Activity layer ready for analysis"
    return f"Activity layer from {facts.output_name} ready for analysis"


def _with_analysis_input_context(summary: str, *, facts: WizardProgressFacts) -> str:
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


def _analysis_filter_description(facts: WizardProgressFacts) -> str | None:
    if not facts.filters_active:
        return None
    description = (facts.filter_description or "").strip()
    return description or None


def _analysis_loaded_layer_count_summary(facts: WizardProgressFacts) -> str | None:
    if facts.loaded_layer_count is None:
        return None
    count = max(facts.loaded_layer_count, 0)
    noun = "qfit layer" if count == 1 else "qfit layers"
    return f"{count} {noun} loaded"


def _analysis_result_summary(facts: WizardProgressFacts) -> str:
    if facts.analysis_output_name is not None:
        return f"Analysis output {facts.analysis_output_name} is available"
    return "Analysis outputs are available"


def _atlas_state_from_facts(facts: WizardProgressFacts) -> AtlasPageState:
    default = AtlasPageState()
    status_text = _atlas_status_text(facts, default)
    output_summary_text = _atlas_output_summary(facts, default)
    atlas_blocked_tooltip = default.primary_action_blocked_tooltip
    primary_action_label = (
        "Refresh atlas PDF" if facts.atlas_exported else default.primary_action_label
    )
    if facts.atlas_export_in_progress:
        status_text = "Atlas export in progress"
        primary_action_label = "Export in progress…"
        atlas_blocked_tooltip = "Wait for the current atlas export to finish."
    return AtlasPageState(
        ready=facts.atlas_exported,
        status_text=status_text,
        input_summary_text=_atlas_input_summary(facts),
        output_summary_text=output_summary_text,
        primary_action_label=primary_action_label,
        primary_action_enabled=(
            facts.activity_layers_loaded and not facts.atlas_export_in_progress
        ),
        primary_action_blocked_tooltip=atlas_blocked_tooltip,
    )


def _atlas_status_text(facts: WizardProgressFacts, default: AtlasPageState) -> str:
    if facts.atlas_exported:
        return "Atlas PDF exported"
    if not facts.activity_layers_loaded:
        return "Map layers required before atlas export"
    return default.status_text


def _atlas_input_summary(facts: WizardProgressFacts) -> str:
    if not facts.activity_layers_loaded:
        return "Load activity layers before exporting atlas PDF"
    if facts.analysis_output_name is not None:
        return f"Analysis output {facts.analysis_output_name} ready for atlas export"
    if facts.analysis_generated:
        return "Analysis outputs ready for atlas export"
    return _atlas_activity_layer_input_summary(facts)


def _atlas_activity_layer_input_summary(facts: WizardProgressFacts) -> str:
    if facts.filters_active:
        summary = _atlas_filtered_activity_layer_summary(facts)
    elif facts.output_name is not None:
        summary = f"Activity layers from {facts.output_name} ready for atlas export"
    else:
        summary = "Activity layers ready for atlas export"
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


def _atlas_filtered_activity_layer_summary(facts: WizardProgressFacts) -> str:
    if facts.filtered_activity_count is None:
        return "Filtered activity subset ready for atlas export"
    noun = "activity" if facts.filtered_activity_count == 1 else "activities"
    return f"{max(facts.filtered_activity_count, 0)} filtered {noun} ready for atlas export"


def _atlas_output_summary(
    facts: WizardProgressFacts,
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


def _validate_progress_targets_installed_page(
    progress: DockWizardProgress | None,
    pages: Sequence[WizardCompositionPage],
) -> None:
    if progress is None:
        return
    build_progress_wizard_step_statuses(progress)
    if progress.current_key not in {page.spec.key for page in pages}:
        raise ValueError(f"No installed wizard page for {progress.current_key!r}")


def _build_page_indices_by_key(
    pages: Sequence[WizardCompositionPage],
) -> dict[str, int]:
    return {page.spec.key: index for index, page in enumerate(pages)}


def _resolve_state(
    provided: _StateT | None,
    existing: _StateT | None,
    default_factory: Callable[[], _StateT],
) -> _StateT:
    if provided is not None:
        return provided
    if existing is not None:
        return existing
    return default_factory()


def _resolve_page_specs(
    specs: Sequence[DockWizardPageSpec] | None,
) -> tuple[DockWizardPageSpec, ...]:
    if specs is None:
        return build_default_wizard_page_specs()
    return tuple(specs)


def _build_default_footer_text(
    *,
    installed_keys: Collection[str],
    connection_state: ConnectionPageState,
    sync_state: SyncPageState,
    map_state: MapPageState,
    analysis_state: AnalysisPageState,
    atlas_state: AtlasPageState,
) -> str:
    return build_wizard_footer_status(
        connection_status=(
            connection_state.status_text if "connection" in installed_keys else None
        ),
        activity_summary=(
            sync_state.activity_summary_text if "sync" in installed_keys else None
        ),
        map_summary=(
            map_state.layer_summary_text if "map" in installed_keys else None
        ),
        analysis_status=(
            analysis_state.status_text if "analysis" in installed_keys else None
        ),
        atlas_status=atlas_state.status_text if "atlas" in installed_keys else None,
    )


def _install_shell_pages(
    shell: WizardShell,
    *,
    specs: Sequence[DockWizardPageSpec],
    use_step_pages: bool,
) -> tuple[WizardCompositionPage, ...]:
    if use_step_pages:
        return install_wizard_step_pages(shell, specs=specs)
    return install_wizard_pages(shell, specs=specs)


def _connect_step_page_navigation(
    shell: WizardShell,
    pages: Sequence[WizardCompositionPage],
    presenter: WizardShellPresenter,
) -> None:
    step_pages = tuple(
        (index, page)
        for index, page in enumerate(pages)
        if isinstance(page, WizardStepPage)
    )
    if not step_pages:
        return

    def request_and_sync(index: int | None) -> None:
        if index is not None:
            presenter.request_step(index)
        _sync_step_page_navigation_and_status(pages, presenter)

    def navigation_target(installed_index: int, direction: str) -> int | None:
        previous_index, next_index = _step_page_navigation_targets(
            pages,
            installed_index=installed_index,
            statuses=build_progress_wizard_step_statuses(presenter.progress),
        )
        return previous_index if direction == "previous" else next_index

    for installed_index, page in step_pages:
        page.backRequested.connect(
            lambda _checked=False, page_index=installed_index: request_and_sync(
                navigation_target(page_index, "previous")
            )
        )
        page.nextRequested.connect(
            lambda _checked=False, page_index=installed_index: request_and_sync(
                navigation_target(page_index, "next")
            )
        )
    shell.stepper_bar.stepRequested.connect(
        lambda _index: _sync_step_page_navigation_and_status(pages, presenter)
    )
    _sync_step_page_navigation_and_status(pages, presenter)


def _sync_step_page_navigation_and_status(
    pages: Sequence[WizardCompositionPage],
    presenter: WizardShellPresenter,
) -> None:
    _sync_step_page_navigation_buttons(pages, presenter)
    _sync_step_page_status_pills(pages, presenter)


def _sync_step_page_navigation_buttons(
    pages: Sequence[WizardCompositionPage],
    presenter: WizardShellPresenter,
) -> None:
    statuses = build_progress_wizard_step_statuses(presenter.progress)
    last_index = len(statuses) - 1
    page_titles_by_index = _step_page_titles_by_workflow_index(pages)
    for installed_index, page in enumerate(pages):
        if not isinstance(page, WizardStepPage):
            continue
        previous_index, next_index = _step_page_navigation_targets(
            pages,
            installed_index=installed_index,
            statuses=statuses,
        )
        page.set_back(
            label=_navigation_label(
                prefix="Précédent",
                target_index=previous_index,
                titles_by_index=page_titles_by_index,
            ),
            enabled=(
                previous_index is not None
                and can_request_step(statuses, previous_index)
            ),
        )
        has_next_page = next_index is not None
        page.set_next(
            label=_navigation_label(
                prefix="Suivant",
                target_index=next_index,
                titles_by_index=page_titles_by_index,
            ),
            icon="→",
            enabled=(
                has_next_page
                and next_index <= last_index
                and can_request_step(statuses, next_index)
            ),
            visible=has_next_page,
        )


def _navigation_label(
    *,
    prefix: str,
    target_index: int | None,
    titles_by_index: dict[int, str],
) -> str:
    target_title = (
        titles_by_index.get(target_index) if target_index is not None else None
    )
    if target_title is None:
        return prefix
    return f"{prefix}: {target_title}"


def _step_page_titles_by_workflow_index(
    pages: Sequence[WizardCompositionPage],
) -> dict[int, str]:
    return {
        step_index_for_key(page.spec.key): page.spec.title
        for page in pages
        if isinstance(page, WizardStepPage)
    }


def _sync_step_page_status_pills(
    pages: Sequence[WizardCompositionPage],
    presenter: WizardShellPresenter,
) -> None:
    step_pages = tuple(page for page in pages if isinstance(page, WizardStepPage))
    if not step_pages:
        return
    apply_wizard_step_page_statuses(
        step_pages,
        build_progress_wizard_step_statuses(presenter.progress),
    )


def _step_page_navigation_targets(
    pages: Sequence[WizardCompositionPage],
    *,
    installed_index: int,
    statuses: Sequence[DockWorkflowStepStatus] | None = None,
) -> tuple[int | None, int | None]:
    current_page = pages[installed_index]
    previous_page = pages[installed_index - 1] if installed_index > 0 else None
    next_page = (
        pages[installed_index + 1]
        if installed_index + 1 < len(pages)
        else None
    )
    if _should_skip_optional_analysis_to_atlas(
        pages,
        current_page=current_page,
        next_page=next_page,
        installed_index=installed_index,
        statuses=statuses,
    ):
        next_page = pages[installed_index + 2]
    return _workflow_index_for_page(previous_page), _workflow_index_for_page(next_page)


def _should_skip_optional_analysis_to_atlas(
    pages: Sequence[WizardCompositionPage],
    *,
    current_page: WizardCompositionPage,
    next_page: WizardCompositionPage | None,
    installed_index: int,
    statuses: Sequence[DockWorkflowStepStatus] | None,
) -> bool:
    if not (
        current_page.spec.key == "map"
        and next_page is not None
        and next_page.spec.key == "analysis"
        and installed_index + 2 < len(pages)
        and pages[installed_index + 2].spec.key == "atlas"
    ):
        return False
    # The default wizard order is map -> optional analysis -> atlas; +2 is the
    # atlas page that follows the optional analysis page checked above.
    atlas_index = step_index_for_key("atlas")
    return statuses is not None and can_request_step(statuses, atlas_index)


def _workflow_index_for_page(page: WizardCompositionPage | None) -> int | None:
    if page is None:
        return None
    return step_index_for_key(page.spec.key)


def _install_connection_content(
    pages: Sequence[WizardCompositionPage],
    *,
    connection_state: ConnectionPageState | None,
) -> ConnectionPageContent | None:
    for page in pages:
        if page.spec.key == "connection":
            return install_connection_page_content(page, state=connection_state)
    return None


def _install_sync_content(
    pages: Sequence[WizardCompositionPage],
    *,
    sync_state: SyncPageState | None,
) -> SyncPageContent | None:
    for page in pages:
        if page.spec.key == "sync":
            return install_sync_page_content(page, state=sync_state)
    return None


def _install_map_content(
    pages: Sequence[WizardCompositionPage],
    *,
    map_state: MapPageState | None,
) -> MapPageContent | None:
    for page in pages:
        if page.spec.key == "map":
            return install_map_page_content(page, state=map_state)
    return None


def _install_analysis_content(
    pages: Sequence[WizardCompositionPage],
    *,
    analysis_state: AnalysisPageState | None,
) -> AnalysisPageContent | None:
    for page in pages:
        if page.spec.key == "analysis":
            return install_analysis_page_content(page, state=analysis_state)
    return None


def _install_atlas_content(
    pages: Sequence[WizardCompositionPage],
    *,
    atlas_state: AtlasPageState | None,
) -> AtlasPageContent | None:
    for page in pages:
        if page.spec.key == "atlas":
            return install_atlas_page_content(page, state=atlas_state)
    return None


__all__ = [
    "WizardActionCallbacks",
    "WizardPageStateSnapshots",
    "WizardProgressFacts",
    "WizardSettingsSnapshot",
    "WizardShellComposition",
    "build_placeholder_wizard_shell",
    "build_wizard_page_states_from_facts",
    "connect_wizard_action_callbacks",
    "refresh_wizard_shell_composition",
]
