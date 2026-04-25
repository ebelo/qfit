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
        title="Spatial analysis",
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
    statuses = []
    for index, section in enumerate(WIZARD_WORKFLOW_STEPS):
        statuses.append(
            DockWorkflowStepStatus(
                key=section.key,
                index=index,
                title=section.title,
                state=_resolve_step_state(section.key, current_key, completed, unlocked),
            )
        )
    return tuple(statuses)


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
        raise KeyError(sorted(unknown_keys)[0])
