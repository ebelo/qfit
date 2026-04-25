from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from .dock_workflow_sections import (
    WIZARD_WORKFLOW_STEPS,
    DockWorkflowStepState,
    DockWorkflowStepStatus,
)

STEPPER_STATE_DONE = "done"
STEPPER_STATE_CURRENT = "current"
STEPPER_STATE_UPCOMING = "upcoming"
STEPPER_STATE_LOCKED = "locked"

STEPPER_STATES_BY_WORKFLOW_STATE = {
    DockWorkflowStepState.DONE: STEPPER_STATE_DONE,
    DockWorkflowStepState.CURRENT: STEPPER_STATE_CURRENT,
    DockWorkflowStepState.UNLOCKED: STEPPER_STATE_UPCOMING,
    DockWorkflowStepState.LOCKED: STEPPER_STATE_LOCKED,
}


@dataclass(frozen=True)
class StepperItem:
    """Render-neutral stepper item for the future wizard shell."""

    key: str
    index: int
    label: str
    state: str
    enabled: bool


def build_stepper_items(
    statuses: Iterable[DockWorkflowStepStatus],
) -> tuple[StepperItem, ...]:
    """Convert workflow statuses into the StepperBar presentation contract.

    Application workflow state deliberately uses ``unlocked`` to keep reachable
    pages distinct from completed pages. The #609 StepperBar API names that
    same visual state ``upcoming``; this adapter keeps that wording isolated at
    the widget boundary.
    """

    return tuple(_build_stepper_item(status) for status in statuses)


def build_stepper_states(statuses: Iterable[DockWorkflowStepStatus]) -> tuple[str, ...]:
    """Return StepperBar ``set_state`` values in workflow order."""

    return tuple(item.state for item in build_stepper_items(statuses))


def can_request_step(
    statuses: Sequence[DockWorkflowStepStatus],
    index: int,
) -> bool:
    """Return whether a StepperBar click should be accepted."""

    status = _status_for_index(statuses, index)
    return status.state is not DockWorkflowStepState.LOCKED


def step_key_for_index(index: int) -> str:
    """Return the stable wizard step key for a StepperBar index."""

    if index < 0 or index >= len(WIZARD_WORKFLOW_STEPS):
        raise IndexError(index)
    return WIZARD_WORKFLOW_STEPS[index].key


def step_index_for_key(key: str) -> int:
    """Return the StepperBar index for a stable wizard step key."""

    for section in WIZARD_WORKFLOW_STEPS:
        if section.key == key:
            return WIZARD_WORKFLOW_STEPS.index(section)
    raise KeyError(key)


def _build_stepper_item(status: DockWorkflowStepStatus) -> StepperItem:
    state = STEPPER_STATES_BY_WORKFLOW_STATE[status.state]
    return StepperItem(
        key=status.key,
        index=status.index,
        label=status.title,
        state=state,
        enabled=state != STEPPER_STATE_LOCKED,
    )


def _status_for_index(
    statuses: Sequence[DockWorkflowStepStatus],
    index: int,
) -> DockWorkflowStepStatus:
    if index < 0 or index >= len(statuses):
        raise IndexError(index)
    return statuses[index]


__all__ = [
    "STEPPER_STATE_CURRENT",
    "STEPPER_STATE_DONE",
    "STEPPER_STATE_LOCKED",
    "STEPPER_STATE_UPCOMING",
    "STEPPER_STATES_BY_WORKFLOW_STATE",
    "StepperItem",
    "build_stepper_items",
    "build_stepper_states",
    "can_request_step",
    "step_index_for_key",
    "step_key_for_index",
]
