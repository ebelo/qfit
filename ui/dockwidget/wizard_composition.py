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
from qfit.ui.application.workflow_progress import (
    build_workflow_progress_from_facts,
    build_workflow_progress_from_facts_and_settings,
)
from qfit.ui.application.workflow_progress_facts import WorkflowProgressFacts
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
from .workflow_page_state import (
    DockWorkflowActionCallbacks as WizardActionCallbacks,
    WorkflowPageStateSnapshots as WizardPageStateSnapshots,
    build_workflow_page_states_from_facts as build_wizard_page_states_from_facts,
    completed_prefix_facts,
    connect_optional_signal as _connect_optional_signal,
)


_StateT = TypeVar("_StateT")
WizardCompositionPage = WizardPage | WizardStepPage
WizardProgressFacts = WorkflowProgressFacts
"""Compatibility alias for wizard composition callers during the #805 migration."""


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
    progress_facts: WorkflowProgressFacts | None = None,
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
    progress_facts: WorkflowProgressFacts | None = None,
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
    _connect_optional_signal(sync_content, "storeRequested", callbacks.store_activities)
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
        "clearAnalysisRequested",
        callbacks.clear_analysis,
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




def _resolve_progress(
    *,
    progress: DockWizardProgress | None,
    progress_facts: WorkflowProgressFacts | None,
    wizard_settings: WizardSettingsSnapshot | None,
) -> DockWizardProgress | None:
    if progress is not None and (progress_facts is not None or wizard_settings is not None):
        raise ValueError("Pass progress or progress_facts/wizard_settings, not both")
    if progress_facts is None and wizard_settings is None:
        return progress
    facts = progress_facts or WorkflowProgressFacts()
    if wizard_settings is not None:
        return build_workflow_progress_from_facts_and_settings(facts, wizard_settings)
    return build_workflow_progress_from_facts(facts)


def _page_state_defaults_from_progress_facts(
    progress_facts: WorkflowProgressFacts | None,
) -> WizardPageStateSnapshots | None:
    if progress_facts is None:
        return None
    return build_wizard_page_states_from_facts(progress_facts)




def _footer_facts_from_progress_facts(
    progress_facts: WorkflowProgressFacts | None,
) -> WizardFooterFacts | None:
    if progress_facts is None:
        return None
    return build_wizard_footer_facts_from_progress_facts(
        completed_prefix_facts(progress_facts)
    )


def _apply_footer_facts(footer_bar, footer_facts: WizardFooterFacts | None) -> None:
    if footer_facts is None:
        return
    footer_bar.set_strava(footer_facts.strava_connected)
    footer_bar.set_activity_count(footer_facts.activity_count)
    footer_bar.set_sync_date(footer_facts.last_sync_date)
    footer_bar.set_layer_count(footer_facts.layer_count)
    footer_bar.set_gpkg_path(footer_facts.gpkg_path)


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
