from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PureWindowsPath

from .dock_runtime_state import DockRuntimeState
from .dock_workflow_sections import DockWizardProgress, WIZARD_WORKFLOW_STEPS
from .wizard_settings import (
    WizardSettingsSnapshot,
    preferred_current_key_from_settings,
)


@dataclass(frozen=True)
class WizardProgressFacts:
    """Render-neutral workflow facts for deriving #609 wizard progress.

    The facts deliberately model completed work, not enabled buttons. This keeps
    the future wizard stepper from marking a step done just because a downstream
    page is reachable.
    """

    connection_configured: bool = False
    activities_fetched: bool = False
    activities_stored: bool = False
    activity_layers_loaded: bool = False
    analysis_generated: bool = False
    atlas_exported: bool = False
    sync_in_progress: bool = False
    atlas_export_in_progress: bool = False
    preferred_current_key: str | None = None
    fetched_activity_count: int | None = None
    activity_count: int | None = None
    output_name: str | None = None
    analysis_output_name: str | None = None
    atlas_output_name: str | None = None
    background_enabled: bool = False
    background_layer_loaded: bool = False
    background_name: str | None = None
    filters_active: bool = False
    filtered_activity_count: int | None = None
    filter_description: str | None = None
    activity_style_preset: str | None = None
    loaded_layer_count: int | None = None
    last_sync_date: str | None = None


def build_wizard_progress_facts_from_runtime_state(
    state: DockRuntimeState,
    *,
    connection_configured: bool = False,
    atlas_exported: bool = False,
    preferred_current_key: str | None = None,
    atlas_output_path: str | None = None,
    background_enabled: bool = False,
    background_layer_loaded: bool = False,
    background_name: str | None = None,
    filters_active: bool = False,
    filtered_activity_count: int | None = None,
    filter_description: str | None = None,
    activity_style_preset: str | None = None,
    last_sync_date: str | None = None,
) -> WizardProgressFacts:
    """Derive #609 wizard progress facts from the dock runtime snapshot.

    The future wizard dock needs a small, render-neutral adapter from the real
    workflow state into ``WizardProgressFacts``. Keep connection and atlas
    completion explicit because they live outside the current runtime snapshot:
    connection is persisted in configuration settings, and atlas exports do not
    yet retain a durable output artifact after the task completes. The runtime
    ``activities`` tuple is a fetch payload, not a persisted dataset count, so
    this adapter reports it separately as fetched work. Persisted dataset totals
    come from the stored activity count captured during store/load transitions.
    Atlas output is supplied separately because it currently lives in the dock
    export controls, not the runtime snapshot.
    """

    output_name = _output_name(state.output_path)
    analysis_output_name = _layer_name(state.analysis_layer)
    atlas_output_name = _output_name(atlas_output_path)
    return WizardProgressFacts(
        connection_configured=connection_configured,
        activities_fetched=bool(state.activities),
        activities_stored=_has_output_path(state),
        activity_layers_loaded=state.activities_layer is not None,
        analysis_generated=state.analysis_layer is not None,
        atlas_exported=atlas_exported,
        sync_in_progress=_has_sync_task(state),
        atlas_export_in_progress=state.atlas_export_task is not None,
        preferred_current_key=preferred_current_key,
        fetched_activity_count=len(state.activities) if state.activities else None,
        activity_count=_stored_activity_count(state),
        output_name=output_name,
        analysis_output_name=analysis_output_name,
        atlas_output_name=atlas_output_name,
        background_enabled=background_enabled,
        background_layer_loaded=background_layer_loaded,
        background_name=_optional_text(background_name),
        filters_active=filters_active,
        filtered_activity_count=filtered_activity_count,
        filter_description=_optional_text(filter_description),
        activity_style_preset=_optional_text(activity_style_preset),
        loaded_layer_count=_loaded_dataset_layer_count(state),
        last_sync_date=_optional_text(last_sync_date),
    )


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
    preferred_current_key = _startup_preferred_current_key(facts, settings)
    return build_wizard_progress_from_facts(
        _wizard_progress_facts_with_preferred_current_key(
            facts,
            preferred_current_key=preferred_current_key,
        )
    )


def _startup_preferred_current_key(
    facts: WizardProgressFacts,
    settings: WizardSettingsSnapshot,
) -> str | None:
    preferred_current_key = preferred_current_key_from_settings(settings)
    if preferred_current_key == "connection" and facts.connection_configured:
        return None
    return preferred_current_key


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
        ("analysis", facts.analysis_generated),
        ("atlas", facts.atlas_exported),
    ):
        if not complete:
            break
        completed.append(key)
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
    reachable_keys = completed | {first_incomplete_key}
    if preferred_current_key in reachable_keys:
        return preferred_current_key
    return first_incomplete_key


def _first_incomplete_key(completed_keys: set[str]) -> str:
    for key in _workflow_keys():
        if key not in completed_keys:
            return key
    return _workflow_keys()[-1]


def _workflow_keys() -> tuple[str, ...]:
    return tuple(section.key for section in WIZARD_WORKFLOW_STEPS)


def _has_output_path(state: DockRuntimeState) -> bool:
    return bool((state.output_path or "").strip())


def _has_sync_task(state: DockRuntimeState) -> bool:
    return state.fetch_task is not None or state.store_task is not None


def _stored_activity_count(state: DockRuntimeState) -> int | None:
    count = state.stored_activity_count
    if count is None:
        return None
    return max(int(count), 0)


def _loaded_dataset_layer_count(state: DockRuntimeState) -> int | None:
    count = sum(
        layer is not None
        for layer in (
            state.activities_layer,
            state.starts_layer,
            state.points_layer,
            state.atlas_layer,
        )
    )
    return count


def _output_name(output_path: str | None) -> str | None:
    stripped = (output_path or "").strip()
    if not stripped:
        return None
    if "\\" in stripped:
        return PureWindowsPath(stripped).name or stripped
    return Path(stripped).name or stripped


def _optional_text(value: str | None) -> str | None:
    stripped = (value or "").strip()
    return stripped or None


def _layer_name(layer) -> str | None:
    if layer is None:
        return None
    try:
        name_method = layer.name
    except Exception:
        # QGIS/Qt wrapper objects may raise different exception types once the
        # underlying C++ layer has been deleted. The layer name is optional
        # summary copy, so keep wizard refreshes resilient.
        return None
    if not callable(name_method):
        return None
    try:
        name = name_method()
    except Exception:
        return None
    if not isinstance(name, str):
        return None
    stripped = name.strip()
    return stripped or None


__all__ = [
    "WizardProgressFacts",
    "build_wizard_progress_facts_from_runtime_state",
    "build_wizard_progress_from_facts_and_settings",
    "build_wizard_progress_from_facts",
]
