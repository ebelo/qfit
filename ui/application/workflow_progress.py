from __future__ import annotations

from .dock_workflow_sections import DockWizardProgress, WIZARD_WORKFLOW_STEPS
from .workflow_progress_facts import WorkflowProgressFacts


def build_workflow_progress_from_facts(
    facts: WorkflowProgressFacts,
) -> DockWizardProgress:
    """Build a safe workflow progress snapshot from current workflow facts.

    Completed steps are prefix-gated so a later fact cannot make the stepper
    skip over an incomplete prerequisite. The preferred current key is accepted
    only while that page is reachable from the completed prefix; otherwise the
    first incomplete step remains current.
    """

    completed_keys = _completed_keys_from_facts(facts)
    current_key = _resolve_current_key(
        completed_keys=completed_keys,
        preferred_current_key=facts.preferred_current_key,
    )
    return DockWizardProgress(
        current_key=current_key,
        completed_keys=frozenset(completed_keys),
        visited_keys=frozenset({current_key}),
    )


def _completed_keys_from_facts(facts: WorkflowProgressFacts) -> tuple[str, ...]:
    connection_complete = facts.connection_configured or facts.activities_stored
    completed: list[str] = []
    for key, complete in (
        ("connection", connection_complete),
        ("sync", facts.activities_stored),
        ("map", facts.activity_layers_loaded),
    ):
        if not complete:
            return tuple(completed)
        completed.append(key)

    if facts.analysis_generated:
        completed.append("analysis")
    if facts.atlas_exported:
        completed.append("atlas")
    return tuple(completed)


def _resolve_current_key(
    *,
    completed_keys: tuple[str, ...],
    preferred_current_key: str | None,
) -> str:
    known_keys = _workflow_keys()
    completed = set(completed_keys)
    first_incomplete_key = _first_incomplete_key(completed)
    if preferred_current_key is None:
        return first_incomplete_key
    if preferred_current_key not in known_keys:
        raise KeyError(preferred_current_key)
    reachable_keys = _reachable_preferred_keys(
        completed_keys=completed,
        first_incomplete_key=first_incomplete_key,
    )
    if preferred_current_key in reachable_keys:
        return preferred_current_key
    return first_incomplete_key


def _reachable_preferred_keys(
    *,
    completed_keys: set[str],
    first_incomplete_key: str,
) -> set[str]:
    reachable = completed_keys | {first_incomplete_key}
    if "map" in completed_keys:
        reachable.update({"analysis", "atlas"})
    return reachable


def _first_incomplete_key(completed_keys: set[str]) -> str:
    if "atlas" in completed_keys:
        return "atlas"
    for key in _workflow_keys():
        if key not in completed_keys:
            return key
    return _workflow_keys()[-1]


def _workflow_keys() -> tuple[str, ...]:
    return tuple(section.key for section in WIZARD_WORKFLOW_STEPS)


__all__ = ["build_workflow_progress_from_facts"]
