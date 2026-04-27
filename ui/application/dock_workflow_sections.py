from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass
from enum import Enum


class DockWorkflowStepState(str, Enum):
    """Wizard step states shared by stepper UI implementations."""

    LOCKED = "locked"
    UNLOCKED = "unlocked"
    CURRENT = "current"
    DONE = "done"


@dataclass(frozen=True)
class DockWorkflowSection:
    """UI-neutral workflow section metadata shared by dock layouts."""

    key: str
    title: str
    current_dock_title: str
    current_dock_overview_title: str | None = None

    @property
    def overview_title(self) -> str:
        return self.current_dock_overview_title or self.current_dock_title


@dataclass(frozen=True)
class DockWorkflowStepStatus:
    """Render-neutral status for one wizard stepper item."""

    key: str
    index: int
    title: str
    state: DockWorkflowStepState


@dataclass(frozen=True)
class DockWizardProgress:
    """Render-neutral wizard progression inputs from the dock state store.

    ``completed_keys`` represent real workflow completion. ``visited_keys``
    represent pages the user has already opened in the current session; visited
    pages remain unlocked without being treated as done.
    """

    current_key: str = "connection"
    completed_keys: frozenset[str] = frozenset()
    visited_keys: frozenset[str] = frozenset()


WIZARD_WORKFLOW_STEPS: tuple[DockWorkflowSection, ...] = (
    DockWorkflowSection(
        key="connection",
        title="Connection",
        current_dock_title="Strava connection",
    ),
    DockWorkflowSection(
        key="sync",
        title="Synchronization",
        current_dock_title="Fetch and store",
        current_dock_overview_title="Fetch & store",
    ),
    DockWorkflowSection(
        key="map",
        title="Map & filters",
        current_dock_title="Visualize",
    ),
    DockWorkflowSection(
        key="analysis",
        title="Spatial analysis (optional)",
        current_dock_title="Analyze",
    ),
    DockWorkflowSection(
        key="atlas",
        title="Atlas PDF",
        current_dock_title="Publish / atlas",
        current_dock_overview_title="Publish",
    ),
)

CURRENT_DOCK_SECTION_KEYS: frozenset[str] = frozenset({"sync", "map", "analysis", "atlas"})
CURRENT_DOCK_SECTIONS: tuple[DockWorkflowSection, ...] = tuple(
    section for section in WIZARD_WORKFLOW_STEPS if section.key in CURRENT_DOCK_SECTION_KEYS
)


def build_current_dock_workflow_label() -> str:
    """Return the compact workflow overview label for the current dock shell."""

    titles = " · ".join(section.overview_title for section in CURRENT_DOCK_SECTIONS)
    return f"Sections: {titles}"


def get_workflow_section(key: str) -> DockWorkflowSection:
    """Return a workflow section by stable key."""

    for section in WIZARD_WORKFLOW_STEPS:
        if section.key == key:
            return section
    raise KeyError(key)


def build_initial_wizard_step_statuses() -> tuple[DockWorkflowStepStatus, ...]:
    """Return the first-launch wizard stepper state from the redesign spec."""

    return build_wizard_step_statuses(current_key="connection")


def build_wizard_step_statuses(
    *,
    current_key: str,
    completed_keys: Collection[str] = frozenset(),
    unlocked_keys: Collection[str] = frozenset(),
) -> tuple[DockWorkflowStepStatus, ...]:
    """Build render-neutral wizard step statuses.

    ``unlocked`` means the user may visit a step; it intentionally does not
    imply ``done`` so wizard pages can expose future steps without marking their
    workflow work complete.
    """

    _validate_workflow_keys(current_key, completed_keys, unlocked_keys)
    completed = set(completed_keys)
    unlocked = set(unlocked_keys)
    return _build_wizard_step_status_tuple(
        current_key=current_key,
        completed_keys=completed,
        unlocked_keys=unlocked,
    )


def build_progress_wizard_step_statuses(
    progress: DockWizardProgress,
) -> tuple[DockWorkflowStepStatus, ...]:
    """Build wizard step statuses from progress facts.

    This encodes the #609 progression rule without depending on concrete Qt
    widgets: a step is unlocked when its previous step is done or when the user
    has already visited it during the current session. Unlocked is kept distinct
    from done so future pages can expose reachable steps without over-reporting
    workflow completion.
    """

    completed = set(progress.completed_keys)
    visited = set(progress.visited_keys) | {progress.current_key}
    _validate_workflow_keys(progress.current_key, completed, visited)
    return _build_wizard_step_status_tuple(
        current_key=progress.current_key,
        completed_keys=completed,
        unlocked_keys=_derive_unlocked_step_keys(completed_keys=completed, visited_keys=visited),
    )


def _build_wizard_step_status_tuple(
    *,
    current_key: str,
    completed_keys: set[str],
    unlocked_keys: set[str],
) -> tuple[DockWorkflowStepStatus, ...]:
    statuses = []
    for index, section in enumerate(WIZARD_WORKFLOW_STEPS):
        statuses.append(
            DockWorkflowStepStatus(
                key=section.key,
                index=index,
                title=section.title,
                state=_resolve_step_state(section.key, current_key, completed_keys, unlocked_keys),
            )
        )
    return tuple(statuses)


def _derive_unlocked_step_keys(
    *,
    completed_keys: set[str],
    visited_keys: set[str],
) -> set[str]:
    unlocked = set(visited_keys)
    for previous, section in zip(WIZARD_WORKFLOW_STEPS, WIZARD_WORKFLOW_STEPS[1:]):
        if previous.key in completed_keys:
            unlocked.add(section.key)
    if "map" in completed_keys:
        unlocked.add("atlas")
    return unlocked


def _resolve_step_state(
    key: str,
    current_key: str,
    completed_keys: set[str],
    unlocked_keys: set[str],
) -> DockWorkflowStepState:
    if key == current_key:
        return DockWorkflowStepState.CURRENT
    if key in completed_keys:
        return DockWorkflowStepState.DONE
    if key in unlocked_keys:
        return DockWorkflowStepState.UNLOCKED
    return DockWorkflowStepState.LOCKED


def _validate_workflow_keys(
    current_key: str,
    completed_keys: Collection[str],
    unlocked_keys: Collection[str],
) -> None:
    known_keys = {section.key for section in WIZARD_WORKFLOW_STEPS}
    all_provided_keys = {current_key} | set(completed_keys) | set(unlocked_keys)
    unknown_keys = all_provided_keys - known_keys
    if unknown_keys:
        raise KeyError(min(unknown_keys))
