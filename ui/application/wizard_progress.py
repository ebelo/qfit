from __future__ import annotations

from .dock_workflow_sections import DockWizardProgress, WIZARD_WORKFLOW_STEPS
from .workflow_progress_facts import (
    WorkflowProgressFacts,
    build_workflow_progress_facts_from_runtime_state,
)
from .wizard_settings import (
    WizardSettingsSnapshot,
    preferred_current_key_from_settings,
)


WizardProgressFacts = WorkflowProgressFacts
"""Compatibility alias for wizard progress callers during the #805 migration."""


build_wizard_progress_facts_from_runtime_state = (
    build_workflow_progress_facts_from_runtime_state
)
"""Compatibility alias for wizard-named progress fact construction."""


def build_wizard_progress_from_facts(facts: WizardProgressFacts) -> DockWizardProgress:
    """Build a safe wizard progress snapshot from current workflow facts.

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


def build_wizard_progress_from_facts_and_settings(
    facts: WizardProgressFacts,
    settings: WizardSettingsSnapshot,
) -> DockWizardProgress:
    """Build wizard progress while honoring a persisted step preference.

    The persisted step is a preference, not an unlock rule. The normal progress
    builder still gates it behind completed prerequisites so the wizard cannot
    restore into a page that should remain locked.
    """

    if facts.preferred_current_key is not None:
        return build_wizard_progress_from_facts(facts)
    return build_wizard_progress_from_facts(
        _wizard_progress_facts_with_preferred_current_key(
            facts,
            preferred_current_key=preferred_current_key_from_settings(settings),
        )
    )


def build_startup_wizard_progress_facts(
    facts: WizardProgressFacts,
    settings: WizardSettingsSnapshot,
) -> WizardProgressFacts:
    """Return startup-only facts for the first visible wizard page.

    Persisted step settings still control normal refreshes. Startup is the one
    place where a saved default Connection target should not make configured
    users reconfirm an already-completed prerequisite before continuing.
    """

    preferred_current_key = preferred_current_key_from_settings(settings)
    if (
        preferred_current_key == "connection"
        and facts.connection_configured
        and not settings.last_step_index_user_selected
    ):
        progress = build_wizard_progress_from_facts(facts)
        return _wizard_progress_facts_with_preferred_current_key(
            facts,
            preferred_current_key=progress.current_key,
        )
    return facts


def _wizard_progress_facts_with_preferred_current_key(
    facts: WizardProgressFacts,
    *,
    preferred_current_key: str | None,
) -> WizardProgressFacts:
    return WizardProgressFacts(
        connection_configured=facts.connection_configured,
        activities_fetched=facts.activities_fetched,
        activities_stored=facts.activities_stored,
        activity_layers_loaded=facts.activity_layers_loaded,
        analysis_generated=facts.analysis_generated,
        atlas_exported=facts.atlas_exported,
        sync_in_progress=facts.sync_in_progress,
        route_sync_in_progress=facts.route_sync_in_progress,
        atlas_export_in_progress=facts.atlas_export_in_progress,
        preferred_current_key=preferred_current_key,
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


def _completed_keys_from_facts(facts: WizardProgressFacts) -> tuple[str, ...]:
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


__all__ = [
    "WizardProgressFacts",
    "build_startup_wizard_progress_facts",
    "build_wizard_progress_facts_from_runtime_state",
    "build_wizard_progress_from_facts_and_settings",
    "build_wizard_progress_from_facts",
]
