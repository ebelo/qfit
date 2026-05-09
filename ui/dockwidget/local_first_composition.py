from __future__ import annotations

from dataclasses import dataclass, replace

from qfit.ui.application.local_first_navigation import (
    build_local_first_dock_navigation_state,
)
from qfit.ui.application.wizard_progress import WizardProgressFacts

from ._qt_compat import import_qt_module
from .analysis_page import AnalysisPageContent, build_analysis_page_content
from .atlas_page import AtlasPageContent, build_atlas_page_content
from .connection_page import (
    ConnectionPageContent,
    ConnectionPageState,
    build_connection_page_content,
)
from .local_first_shell import LocalFirstDockShell
from .map_page import MapPageContent, build_map_page_content
from .page_content_style import (
    LOCAL_FIRST_PAGE_MARGINS,
    LOCAL_FIRST_PAGE_SPACING,
    configure_top_aligned_panel_layout,
)
from .sync_page import SyncPageContent, build_sync_page_content
from .wizard_composition import (
    WizardActionCallbacks,
    _connect_optional_signal,
    build_wizard_page_states_from_facts,
)

_qtwidgets = import_qt_module(
    "qgis.PyQt.QtWidgets",
    "PyQt5.QtWidgets",
    ("QVBoxLayout", "QWidget"),
)

QVBoxLayout = _qtwidgets.QVBoxLayout
QWidget = _qtwidgets.QWidget


@dataclass(frozen=True)
class LocalFirstDockPageContent:
    """Installed reusable content widgets for the local-first dock pages."""

    data_content: SyncPageContent
    map_content: MapPageContent
    analysis_content: AnalysisPageContent
    atlas_content: AtlasPageContent
    settings_content: ConnectionPageContent


@dataclass
class LocalFirstDockComposition:
    """Assembled #748 local-first shell with reusable page content installed."""

    shell: LocalFirstDockShell
    pages: dict[str, QWidget]
    page_content: LocalFirstDockPageContent
    action_callbacks: WizardActionCallbacks | None = None

    @property
    def sync_content(self) -> SyncPageContent:
        """Compatibility alias for existing synchronization callback wiring."""

        return self.page_content.data_content

    @property
    def map_content(self) -> MapPageContent:
        return self.page_content.map_content

    @property
    def analysis_content(self) -> AnalysisPageContent:
        return self.page_content.analysis_content

    @property
    def atlas_content(self) -> AtlasPageContent:
        return self.page_content.atlas_content

    @property
    def settings_content(self) -> ConnectionPageContent:
        """Local-first Settings page content."""

        return self.page_content.settings_content

    @property
    def connection_content(self) -> ConnectionPageContent:
        """Settings page uses the existing connection/configuration content."""

        return self.settings_content


def build_local_first_dock_composition(
    *,
    parent=None,
    footer_text: str = "",
    progress_facts: WizardProgressFacts | None = None,
    atlas_title: str = "qfit Activity Atlas",
    atlas_subtitle: str = "",
) -> LocalFirstDockComposition:
    """Build the reusable local-first dock shell without swapping production UI."""

    facts = progress_facts or WizardProgressFacts()
    shell = LocalFirstDockShell(
        parent=parent,
        navigation_state=build_local_first_dock_navigation_state(facts),
        footer_text=footer_text,
    )
    pages = _install_local_first_pages(shell)
    page_content = _install_local_first_page_content(
        pages,
        facts=facts,
        atlas_title=atlas_title,
        atlas_subtitle=atlas_subtitle,
    )
    return LocalFirstDockComposition(
        shell=shell,
        pages=pages,
        page_content=page_content,
    )


def connect_local_first_action_callbacks(
    composition: LocalFirstDockComposition,
    callbacks: WizardActionCallbacks,
) -> LocalFirstDockComposition:
    """Connect concrete dock callbacks to local-first page content actions."""

    if composition.action_callbacks is not None:
        return composition
    _connect_optional_signal(
        composition.settings_content,
        "configureRequested",
        callbacks.configure_connection,
    )
    _connect_optional_signal(composition.sync_content, "syncRequested", callbacks.sync_activities)
    _connect_optional_signal(
        composition.sync_content,
        "storeRequested",
        callbacks.store_activities,
    )
    _connect_optional_signal(
        composition.sync_content,
        "syncRoutesRequested",
        callbacks.sync_saved_routes,
    )
    _connect_optional_signal(
        composition.sync_content,
        "loadActivitiesRequested",
        callbacks.load_activity_layers,
    )
    _connect_optional_signal(
        composition.sync_content,
        "clearDatabaseRequested",
        callbacks.clear_database,
    )
    _connect_optional_signal(
        composition.map_content,
        "loadLayersRequested",
        callbacks.load_activity_layers,
    )
    _connect_optional_signal(
        composition.map_content,
        "applyFiltersRequested",
        callbacks.apply_map_filters,
    )
    _connect_optional_signal(
        composition.analysis_content,
        "runAnalysisRequested",
        callbacks.run_analysis,
    )
    _connect_optional_signal(
        composition.analysis_content,
        "clearAnalysisRequested",
        callbacks.clear_analysis,
    )
    _connect_optional_signal(
        composition.analysis_content,
        "analysisModeChanged",
        callbacks.set_analysis_mode,
    )
    _connect_optional_signal(
        composition.atlas_content,
        "exportAtlasRequested",
        callbacks.export_atlas,
    )
    _connect_optional_signal(
        composition.atlas_content,
        "atlasDocumentSettingsChanged",
        callbacks.update_atlas_document_settings,
    )
    composition.action_callbacks = callbacks
    return composition


def refresh_local_first_dock_composition(
    composition: LocalFirstDockComposition,
    *,
    progress_facts: WizardProgressFacts | None = None,
) -> LocalFirstDockComposition:
    """Refresh navigation and page status from render-neutral workflow facts."""

    facts = progress_facts or WizardProgressFacts()
    page_states = build_wizard_page_states_from_facts(_content_facts(facts))
    current_key = facts.preferred_current_key or composition.shell.current_key()
    composition.shell.set_navigation_state(
        build_local_first_dock_navigation_state(
            facts,
            preferred_current_key=current_key,
        )
    )
    composition.sync_content.set_state(page_states.sync_state)
    composition.map_content.set_state(page_states.map_state)
    composition.analysis_content.set_state(page_states.analysis_state)
    composition.atlas_content.set_state(page_states.atlas_state)
    composition.settings_content.set_state(
        _settings_state_from_connection_state(page_states.connection_state)
    )
    return composition


def _content_facts(facts: WizardProgressFacts) -> WizardProgressFacts:
    """Adapt local-first page facts to legacy wizard content state helpers."""

    return replace(facts, preferred_current_key=None)


def _install_local_first_pages(shell: LocalFirstDockShell) -> dict[str, QWidget]:
    pages = {
        key: _LocalFirstDockPage(key=key, parent=shell)
        for key in ("data", "map", "analysis", "atlas", "settings")
    }
    for key, page in pages.items():
        shell.add_page(key, page)
    return pages


def _install_local_first_page_content(
    pages: dict[str, QWidget],
    *,
    facts: WizardProgressFacts,
    atlas_title: str,
    atlas_subtitle: str,
) -> LocalFirstDockPageContent:
    page_states = build_wizard_page_states_from_facts(_content_facts(facts))
    data_content = build_sync_page_content(
        parent=pages["data"],
        state=page_states.sync_state,
    )
    map_content = build_map_page_content(
        parent=pages["map"],
        state=page_states.map_state,
    )
    analysis_content = build_analysis_page_content(
        parent=pages["analysis"],
        state=page_states.analysis_state,
    )
    atlas_content = build_atlas_page_content(
        parent=pages["atlas"],
        state=page_states.atlas_state,
        atlas_title=atlas_title,
        atlas_subtitle=atlas_subtitle,
    )
    settings_content = build_connection_page_content(
        parent=pages["settings"],
        state=_settings_state_from_connection_state(page_states.connection_state),
    )
    _page_layout(pages["data"]).addWidget(data_content)
    _page_layout(pages["map"]).addWidget(map_content)
    _page_layout(pages["analysis"]).addWidget(analysis_content)
    _page_layout(pages["atlas"]).addWidget(atlas_content)
    _page_layout(pages["settings"]).addWidget(settings_content)
    return LocalFirstDockPageContent(
        data_content=data_content,
        map_content=map_content,
        analysis_content=analysis_content,
        atlas_content=atlas_content,
        settings_content=settings_content,
    )


def _settings_state_from_connection_state(
    state: ConnectionPageState,
) -> ConnectionPageState:
    """Adapt reusable connection controls for the local-first Settings page."""

    settings_action_label = (
        "Review settings"
        if state.connection_configured
        else "Configure settings"
    )
    return ConnectionPageState(
        connected=state.connected,
        connection_configured=state.connection_configured,
        status_text=state.status_text,
        detail_text=(
            "Review provider credentials and durable qfit preferences away from "
            "daily workflow panels."
        ),
        credential_summary_text=state.credential_summary_text,
        primary_action_label=settings_action_label,
        primary_action_enabled=state.primary_action_enabled,
        primary_action_blocked_tooltip=state.primary_action_blocked_tooltip,
    )


def _page_layout(page: QWidget):
    layout_getter = getattr(page, "body_layout", None)
    if not callable(layout_getter):
        raise TypeError("Local-first pages must expose body_layout()")
    return layout_getter()


class _LocalFirstDockPage(QWidget):
    def __init__(self, *, key: str, parent=None) -> None:
        super().__init__(parent)
        self.key = key
        self.setObjectName(f"qfitLocalFirstDockPage_{key}")
        self._layout = QVBoxLayout(self)
        if hasattr(self._layout, "setObjectName"):
            self._layout.setObjectName(f"qfitLocalFirstDockPageLayout_{key}")
        configure_top_aligned_panel_layout(
            self._layout,
            margins=LOCAL_FIRST_PAGE_MARGINS,
            spacing=LOCAL_FIRST_PAGE_SPACING,
        )

    def body_layout(self):
        return self._layout


__all__ = [
    "LocalFirstDockComposition",
    "LocalFirstDockPageContent",
    "WizardActionCallbacks",
    "build_local_first_dock_composition",
    "connect_local_first_action_callbacks",
    "refresh_local_first_dock_composition",
]
