from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PureWindowsPath

from .dock_runtime_state import DockRuntimeState


@dataclass(frozen=True)
class WorkflowProgressFacts:
    """Render-neutral facts for deriving workflow progress and summaries.

    These facts deliberately model completed work, not enabled controls. They are
    shared by the dock-first local-first shell and the compatibility wizard
    progress adapter so local-first navigation can avoid depending on a
    wizard-named progress model.
    """

    connection_configured: bool = False
    activities_fetched: bool = False
    activities_stored: bool = False
    activity_layers_loaded: bool = False
    analysis_generated: bool = False
    atlas_exported: bool = False
    sync_in_progress: bool = False
    route_sync_in_progress: bool = False
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


def build_workflow_progress_facts_from_runtime_state(
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
) -> WorkflowProgressFacts:
    """Derive render-neutral workflow progress facts from the dock runtime snapshot."""

    output_name = _output_name(state.output_path)
    analysis_output_name = _layer_name(state.analysis_layer)
    atlas_output_name = _output_name(atlas_output_path)
    return WorkflowProgressFacts(
        connection_configured=connection_configured,
        activities_fetched=bool(state.activities),
        activities_stored=_has_stored_activities(state),
        activity_layers_loaded=state.activities_layer is not None,
        analysis_generated=state.analysis_layer is not None,
        atlas_exported=atlas_exported,
        sync_in_progress=_has_sync_task(state),
        route_sync_in_progress=state.route_sync_task is not None,
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


def _has_stored_activities(state: DockRuntimeState) -> bool:
    if state.stored_activity_count is not None:
        return True
    if _loaded_dataset_layer_count(state) > 0:
        return True
    output_path = (state.output_path or "").strip()
    if not output_path:
        return False
    try:
        return Path(output_path).exists()
    except OSError:
        return False


def _has_sync_task(state: DockRuntimeState) -> bool:
    return (
        state.fetch_task is not None
        or state.store_task is not None
        or state.route_sync_task is not None
    )


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
        # summary copy, so keep workflow refreshes resilient.
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
    "WorkflowProgressFacts",
    "build_workflow_progress_facts_from_runtime_state",
]
