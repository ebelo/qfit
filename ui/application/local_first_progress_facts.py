from __future__ import annotations

import logging

from ...activities.application import build_activity_preview_selection_state
from ...visualization.application import DEFAULT_TEMPORAL_MODE_LABEL
from .wizard_filter_summary import build_wizard_filter_description

logger = logging.getLogger(__name__)


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
    preview_request = dock._current_activity_preview_request()
    selection_state = build_activity_preview_selection_state(preview_request)
    filters_active = selection_state.filtered_count != len(activities)
    if not filters_active:
        return False, None, None
    return (
        True,
        selection_state.filtered_count,
        build_wizard_filter_description(preview_request),
    )


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
    "current_local_first_activity_style_preset",
    "current_local_first_atlas_output_path",
    "current_local_first_background_facts",
    "current_local_first_filter_facts",
    "current_local_first_visual_temporal_mode",
]
