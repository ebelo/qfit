from __future__ import annotations

import logging
from dataclasses import replace

from ...activities.application import build_activity_preview_selection_state
from .local_first_activity_controls import build_current_activity_preview_request
from ...visualization.application import DEFAULT_TEMPORAL_MODE_LABEL
from .wizard_filter_summary import build_wizard_filter_description
from .wizard_progress import build_wizard_progress_facts_from_runtime_state

logger = logging.getLogger(__name__)


def build_current_local_first_progress_facts(dock):
    """Return render-neutral local-first progress facts from the live dock state."""

    runtime_state = runtime_state_with_local_first_output_path(
        dock.runtime_state,
        dock._widget_text("outputPathLineEdit"),
    )
    atlas_exported = bool(getattr(dock, "_atlas_export_completed", False))
    atlas_export_output_path = current_local_first_atlas_output_path(
        runtime_state=runtime_state,
        atlas_pdf_path=dock._widget_text("atlasPdfPathLineEdit"),
        atlas_exported=atlas_exported,
        completed_output_path=getattr(dock, "_atlas_export_output_path", None),
        task_output_path=getattr(dock, "_atlas_export_task_output_path", None),
    )
    (
        background_enabled,
        background_layer_loaded,
        background_name,
    ) = current_local_first_background_facts(dock, runtime_state)
    (
        filters_active,
        filtered_activity_count,
        filter_description,
    ) = current_local_first_filter_facts(dock, runtime_state)
    return build_wizard_progress_facts_from_runtime_state(
        runtime_state,
        connection_configured=current_local_first_connection_configured(dock),
        atlas_exported=atlas_exported,
        atlas_output_path=atlas_export_output_path,
        background_enabled=background_enabled,
        background_layer_loaded=background_layer_loaded,
        background_name=background_name,
        filters_active=filters_active,
        filtered_activity_count=filtered_activity_count,
        filter_description=filter_description,
        activity_style_preset=current_local_first_activity_style_preset(dock),
        last_sync_date=current_local_first_last_sync_date(
            getattr(dock, "settings", None)
        ),
    )


def current_local_first_connection_configured(dock) -> bool:
    """Return whether local-first progress can treat Strava as configured."""

    return all(
        _safe_local_first_widget_text(dock, name)
        for name in (
            "clientIdLineEdit",
            "clientSecretLineEdit",
            "refreshTokenLineEdit",
        )
    )


def current_local_first_activity_style_preset(dock) -> str | None:
    """Return current activity style copy for local-first progress summaries."""

    preset_combo = getattr(dock, "stylePresetComboBox", None)
    if preset_combo is None or not hasattr(preset_combo, "currentText"):
        return None
    try:
        preset_name = preset_combo.currentText()
    except RuntimeError:
        logger.debug("Failed to read local-first activity style preset", exc_info=True)
        return None
    if not isinstance(preset_name, str):
        return None
    stripped = preset_name.strip()
    return stripped or None


def current_local_first_visual_temporal_mode(dock) -> str:
    """Return the visible temporal playback setting for visual workflow actions."""

    combo = getattr(dock, "temporalModeComboBox", None)
    if combo is None or not hasattr(combo, "currentText"):
        return DEFAULT_TEMPORAL_MODE_LABEL
    try:
        mode_label = combo.currentText()
    except RuntimeError:
        logger.debug("Failed to read local-first temporal playback mode", exc_info=True)
        return DEFAULT_TEMPORAL_MODE_LABEL
    if not isinstance(mode_label, str):
        return DEFAULT_TEMPORAL_MODE_LABEL
    return mode_label.strip() or DEFAULT_TEMPORAL_MODE_LABEL


def current_local_first_background_facts(dock, runtime_state) -> tuple[bool, bool, str | None]:
    """Return current basemap facts for local-first progress summaries."""

    background_layer_loaded = runtime_state.background_layer is not None
    if background_layer_loaded:
        return True, True, _current_local_first_layer_name(
            runtime_state.background_layer,
            log_message="Failed to read local-first background layer name",
        )

    checkbox = getattr(dock, "backgroundMapCheckBox", None)
    background_enabled = bool(
        checkbox is not None
        and hasattr(checkbox, "isChecked")
        and checkbox.isChecked()
    )
    if not background_enabled:
        return False, False, None
    return True, False, _current_local_first_background_name(dock)


def current_local_first_atlas_output_path(
    *,
    runtime_state,
    atlas_pdf_path: str,
    atlas_exported: bool,
    completed_output_path: str | None = None,
    task_output_path: str | None = None,
) -> str:
    """Return the atlas output path local-first progress should describe."""

    if runtime_state.atlas_export_task is not None:
        return task_output_path or atlas_pdf_path
    if atlas_exported and completed_output_path:
        return completed_output_path
    return atlas_pdf_path


def current_local_first_last_sync_date(settings) -> str | None:
    """Return the persisted last sync date for local-first progress summaries."""

    get_value = getattr(settings, "get", None)
    if not callable(get_value):
        return None
    value = get_value("last_sync_date", None)
    if not isinstance(value, str):
        return None
    return value.strip() or None


def runtime_state_with_local_first_output_path(runtime_state, selected_output_path: str):
    """Return runtime facts that reflect the visible local-first GeoPackage path."""

    selected_output_path = (selected_output_path or "").strip()
    if not selected_output_path or selected_output_path == runtime_state.output_path:
        return runtime_state
    return replace(runtime_state, output_path=selected_output_path)


def current_local_first_filter_facts(dock, runtime_state) -> tuple[bool, int | None, str | None]:
    """Return current map-filter facts for local-first progress summaries."""

    layer_filter_facts = _current_local_first_layer_filter_facts(runtime_state)
    if layer_filter_facts is not None:
        filters_active, filtered_activity_count = layer_filter_facts
        filter_description = "layer subset" if filters_active else None
        return filters_active, filtered_activity_count, filter_description

    activities = tuple(runtime_state.activities)
    if not activities:
        return False, None, None
    preview_request = build_current_activity_preview_request(dock)
    selection_state = build_activity_preview_selection_state(preview_request)
    filters_active = selection_state.filtered_count != len(activities)
    if not filters_active:
        return False, None, None
    return (
        True,
        selection_state.filtered_count,
        build_wizard_filter_description(preview_request),
    )


def _safe_local_first_widget_text(dock, widget_name: str) -> str:
    widget_text = getattr(dock, "_widget_text", None)
    if callable(widget_text):
        try:
            value = widget_text(widget_name)
        except RuntimeError:
            logger.debug("Failed to read local-first widget text", exc_info=True)
            return ""
        return value.strip() if isinstance(value, str) else ""

    widget = getattr(dock, widget_name, None)
    text = getattr(widget, "text", None)
    if not callable(text):
        return ""
    try:
        value = text()
    except RuntimeError:
        logger.debug("Failed to read local-first widget text", exc_info=True)
        return ""
    return value.strip() if isinstance(value, str) else ""


def _current_local_first_layer_filter_facts(runtime_state) -> tuple[bool, int | None] | None:
    layer = runtime_state.activities_layer
    if layer is None or not hasattr(layer, "subsetString"):
        return None
    try:
        subset = (layer.subsetString() or "").strip()
    except RuntimeError:
        logger.debug("Failed to read activity layer subset", exc_info=True)
        return None
    if not subset:
        return False, None
    return True, _current_local_first_layer_feature_count(layer)


def _current_local_first_layer_feature_count(layer) -> int | None:
    if not hasattr(layer, "featureCount"):
        return None
    try:
        count = layer.featureCount()
    except RuntimeError:
        logger.debug("Failed to read activity layer feature count", exc_info=True)
        return None
    if not isinstance(count, int):
        return None
    return max(count, 0)


def _current_local_first_layer_name(layer, *, log_message: str) -> str | None:
    if layer is None:
        return None
    name_method = getattr(layer, "name", None)
    if not callable(name_method):
        return None
    try:
        layer_name = name_method()
    except RuntimeError:
        logger.debug(log_message, exc_info=True)
        return None
    if not isinstance(layer_name, str):
        return None
    stripped = layer_name.strip()
    return stripped or None


def _current_local_first_background_name(dock) -> str | None:
    preset_combo = getattr(dock, "backgroundPresetComboBox", None)
    if preset_combo is None or not hasattr(preset_combo, "currentText"):
        return None
    try:
        preset_name = preset_combo.currentText()
    except RuntimeError:
        logger.debug("Failed to read local-first background preset", exc_info=True)
        return None
    if not isinstance(preset_name, str):
        return None
    stripped = preset_name.strip()
    return stripped or None


__all__ = [
    "build_current_local_first_progress_facts",
    "current_local_first_activity_style_preset",
    "current_local_first_atlas_output_path",
    "current_local_first_background_facts",
    "current_local_first_connection_configured",
    "current_local_first_filter_facts",
    "current_local_first_last_sync_date",
    "current_local_first_visual_temporal_mode",
    "runtime_state_with_local_first_output_path",
]
