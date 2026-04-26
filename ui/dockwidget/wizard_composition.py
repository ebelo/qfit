from __future__ import annotations

from collections.abc import Callable, Collection, Sequence
from dataclasses import dataclass
from typing import TypeVar

from qfit.ui.application.dock_workflow_sections import (
    DockWizardProgress,
    build_progress_wizard_step_statuses,
)
from qfit.ui.application.wizard_footer_status import build_wizard_footer_status
from qfit.ui.application.wizard_page_specs import (
    DockWizardPageSpec,
    build_default_wizard_page_specs,
)
from qfit.ui.application.wizard_progress import (
    WizardProgressFacts,
    build_wizard_progress_from_facts,
)

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
from .wizard_page import WizardPage, install_wizard_pages
from .wizard_shell import WizardShell
from .wizard_shell_presenter import WizardShellPresenter


_StateT = TypeVar("_StateT")


@dataclass(frozen=True)
class WizardActionCallbacks:
    """Optional adapters for concrete wizard page actions.

    The placeholder shell can now expose visible CTAs without importing the
    current dock widget. A future dock swap can pass bound methods here while
    pure tests keep the page widgets independent from the long-scroll dock.
    """

    configure_connection: Callable[[], None] | None = None
    sync_activities: Callable[[], None] | None = None
    load_activity_layers: Callable[[], None] | None = None
    apply_map_filters: Callable[[], None] | None = None
    run_analysis: Callable[[], None] | None = None
    export_atlas: Callable[[], None] | None = None


@dataclass
class WizardShellComposition:
    """Concrete placeholder wizard assembly for the future dock replacement.

    The composition keeps the shell, page placeholders, and presenter wiring in
    one reusable unit without replacing the current production dock yet. That
    gives #609 a safe integration seam for the eventual dock swap while keeping
    this slice focused on wizard-forward UI structure.
    """

    shell: WizardShell
    pages: tuple[WizardPage, ...]
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


def build_placeholder_wizard_shell(
    *,
    parent=None,
    footer_text: str = "",
    progress: DockWizardProgress | None = None,
    progress_facts: WizardProgressFacts | None = None,
    specs: Sequence[DockWizardPageSpec] | None = None,
    connection_state: ConnectionPageState | None = None,
    sync_state: SyncPageState | None = None,
    map_state: MapPageState | None = None,
    analysis_state: AnalysisPageState | None = None,
    atlas_state: AtlasPageState | None = None,
) -> WizardShellComposition:
    """Build the placeholder #609 wizard shell with pages and presenter wired.

    Pages are installed before the presenter renders so the initial progress
    snapshot selects the matching visible page immediately. The helper does not
    bind any current long-scroll dock controls into the shell; page content can
    migrate later through the stable ``WizardPage.body_layout()`` seams.
    """

    connection_state = connection_state or ConnectionPageState()
    sync_state = sync_state or SyncPageState()
    map_state = map_state or MapPageState()
    analysis_state = analysis_state or AnalysisPageState()
    atlas_state = atlas_state or AtlasPageState()
    resolved_progress = _resolve_progress(
        progress=progress,
        progress_facts=progress_facts,
    )
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
    pages = install_wizard_pages(shell, specs=page_specs)
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
    )
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
) -> WizardShellComposition:
    """Refresh installed wizard page state without rebuilding the shell.

    This is the small adapter seam the future dock can use when real workflow
    facts change: update only the installed page widgets, then refresh the
    persistent footer and optional stepper progress from the same render-neutral
    state snapshots. Missing page content is skipped so partial/spec-filtered
    wizard assemblies remain valid.
    """

    next_connection_state = _resolve_state(
        connection_state,
        composition.connection_state,
        ConnectionPageState,
    )
    next_sync_state = _resolve_state(sync_state, composition.sync_state, SyncPageState)
    next_map_state = _resolve_state(map_state, composition.map_state, MapPageState)
    next_analysis_state = _resolve_state(
        analysis_state,
        composition.analysis_state,
        AnalysisPageState,
    )
    next_atlas_state = _resolve_state(
        atlas_state,
        composition.atlas_state,
        AtlasPageState,
    )
    resolved_progress = _resolve_progress(
        progress=progress,
        progress_facts=progress_facts,
    )
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
    if resolved_progress is not None:
        composition.presenter.set_progress(resolved_progress)

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
    if connection_content is not None and callbacks.configure_connection is not None:
        connection_content.configureRequested.connect(callbacks.configure_connection)
    if sync_content is not None and callbacks.sync_activities is not None:
        sync_content.syncRequested.connect(callbacks.sync_activities)
    if map_content is not None and callbacks.load_activity_layers is not None:
        map_content.loadLayersRequested.connect(callbacks.load_activity_layers)
    if map_content is not None and callbacks.apply_map_filters is not None:
        map_content.applyFiltersRequested.connect(callbacks.apply_map_filters)
    if analysis_content is not None and callbacks.run_analysis is not None:
        analysis_content.runAnalysisRequested.connect(callbacks.run_analysis)
    if atlas_content is not None and callbacks.export_atlas is not None:
        atlas_content.exportAtlasRequested.connect(callbacks.export_atlas)


def _resolve_progress(
    *,
    progress: DockWizardProgress | None,
    progress_facts: WizardProgressFacts | None,
) -> DockWizardProgress | None:
    if progress is not None and progress_facts is not None:
        raise ValueError("Pass progress or progress_facts, not both")
    if progress_facts is None:
        return progress
    return build_wizard_progress_from_facts(progress_facts)


def _validate_progress_targets_installed_page(
    progress: DockWizardProgress | None,
    pages: Sequence[WizardPage],
) -> None:
    if progress is None:
        return
    build_progress_wizard_step_statuses(progress)
    if progress.current_key not in {page.spec.key for page in pages}:
        raise ValueError(f"No installed wizard page for {progress.current_key!r}")


def _build_page_indices_by_key(pages: Sequence[WizardPage]) -> dict[str, int]:
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


def _install_connection_content(
    pages: Sequence[WizardPage],
    *,
    connection_state: ConnectionPageState | None,
) -> ConnectionPageContent | None:
    for page in pages:
        if page.spec.key == "connection":
            return install_connection_page_content(page, state=connection_state)
    return None


def _install_sync_content(
    pages: Sequence[WizardPage],
    *,
    sync_state: SyncPageState | None,
) -> SyncPageContent | None:
    for page in pages:
        if page.spec.key == "sync":
            return install_sync_page_content(page, state=sync_state)
    return None


def _install_map_content(
    pages: Sequence[WizardPage],
    *,
    map_state: MapPageState | None,
) -> MapPageContent | None:
    for page in pages:
        if page.spec.key == "map":
            return install_map_page_content(page, state=map_state)
    return None


def _install_analysis_content(
    pages: Sequence[WizardPage],
    *,
    analysis_state: AnalysisPageState | None,
) -> AnalysisPageContent | None:
    for page in pages:
        if page.spec.key == "analysis":
            return install_analysis_page_content(page, state=analysis_state)
    return None


def _install_atlas_content(
    pages: Sequence[WizardPage],
    *,
    atlas_state: AtlasPageState | None,
) -> AtlasPageContent | None:
    for page in pages:
        if page.spec.key == "atlas":
            return install_atlas_page_content(page, state=atlas_state)
    return None


__all__ = [
    "WizardActionCallbacks",
    "WizardProgressFacts",
    "WizardShellComposition",
    "build_placeholder_wizard_shell",
    "connect_wizard_action_callbacks",
    "refresh_wizard_shell_composition",
]
