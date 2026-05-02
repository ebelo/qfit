from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .wizard_progress import WizardProgressFacts


@dataclass(frozen=True)
class LocalFirstDockPageDefinition:
    """Stable navigation metadata for the #748 local-first dock."""

    key: str
    title: str
    description: str


@dataclass(frozen=True)
class LocalFirstDockPageState:
    """Render-neutral state for one local-first dock navigation page."""

    key: str
    title: str
    description: str
    status_text: str
    ready: bool = False
    enabled: bool = True
    current: bool = False


@dataclass(frozen=True)
class LocalFirstDockNavigationState:
    """Render-neutral state for the local-first dock navigation model."""

    current_key: str
    pages: tuple[LocalFirstDockPageState, ...]


LOCAL_FIRST_DOCK_PAGE_DEFINITIONS: tuple[LocalFirstDockPageDefinition, ...] = (
    LocalFirstDockPageDefinition(
        key="data",
        title="Data",
        description="Load local GeoPackages or sync Strava activities and routes.",
    ),
    LocalFirstDockPageDefinition(
        key="map",
        title="Map",
        description="Load layers, choose styles, backgrounds, and filters.",
    ),
    LocalFirstDockPageDefinition(
        key="analysis",
        title="Analysis",
        description="Run optional analysis on loaded activity layers.",
    ),
    LocalFirstDockPageDefinition(
        key="atlas",
        title="Atlas",
        description="Configure and export the qfit PDF atlas.",
    ),
    LocalFirstDockPageDefinition(
        key="settings",
        title="Settings",
        description="Review qfit and Strava connection settings.",
    ),
)


_DEFAULT_CURRENT_PAGE_KEY = "data"


def build_local_first_dock_navigation_state(
    facts: WizardProgressFacts | None = None,
    *,
    preferred_current_key: str | None = None,
) -> LocalFirstDockNavigationState:
    """Build unlocked local-first navigation state for the #748 dock.

    Unlike the retired wizard stepper model, these pages are always reachable.
    Page readiness only describes available work/results; it must not lock
    navigation because local loading, syncing, styling, analysis, and atlas
    export are not a strictly linear workflow.
    """

    resolved_facts = facts or WizardProgressFacts()
    current_key = _resolve_current_key(preferred_current_key)
    return LocalFirstDockNavigationState(
        current_key=current_key,
        pages=tuple(
            LocalFirstDockPageState(
                key=definition.key,
                title=definition.title,
                description=definition.description,
                status_text=_status_text(definition.key, resolved_facts),
                ready=_page_ready(definition.key, resolved_facts),
                current=definition.key == current_key,
            )
            for definition in LOCAL_FIRST_DOCK_PAGE_DEFINITIONS
        ),
    )


def local_first_dock_page_keys(
    definitions: Iterable[LocalFirstDockPageDefinition] = LOCAL_FIRST_DOCK_PAGE_DEFINITIONS,
) -> tuple[str, ...]:
    """Return stable page keys for navigation widgets and persistence."""

    return tuple(definition.key for definition in definitions)


def _resolve_current_key(preferred_current_key: str | None) -> str:
    if preferred_current_key in local_first_dock_page_keys():
        return str(preferred_current_key)
    return _DEFAULT_CURRENT_PAGE_KEY


def _page_ready(key: str, facts: WizardProgressFacts) -> bool:
    if key == "data":
        return facts.activities_stored or facts.activities_fetched
    if key == "map":
        return facts.activity_layers_loaded
    if key == "analysis":
        return facts.analysis_generated
    if key == "atlas":
        return facts.atlas_exported
    if key == "settings":
        return facts.connection_configured
    return False


def _status_text(key: str, facts: WizardProgressFacts) -> str:
    if key == "data":
        if facts.sync_in_progress:
            return "Sync in progress"
        if facts.activities_stored:
            return "Activity data available"
        if facts.activities_fetched:
            return "Activities fetched; store them in a GeoPackage"
        return "Choose a local GeoPackage or sync from Strava"
    if key == "map":
        return "Map layers loaded" if facts.activity_layers_loaded else "Map controls available"
    if key == "analysis":
        return "Analysis generated" if facts.analysis_generated else "Analysis is optional"
    if key == "atlas":
        return "Atlas exported" if facts.atlas_exported else "Atlas export available"
    if key == "settings":
        return "Strava configured" if facts.connection_configured else "Settings available"
    return "Available"


__all__ = [
    "LOCAL_FIRST_DOCK_PAGE_DEFINITIONS",
    "LocalFirstDockNavigationState",
    "LocalFirstDockPageDefinition",
    "LocalFirstDockPageState",
    "build_local_first_dock_navigation_state",
    "local_first_dock_page_keys",
]
