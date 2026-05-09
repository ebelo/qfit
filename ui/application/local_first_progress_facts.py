from __future__ import annotations

import logging

from ...visualization.application import DEFAULT_TEMPORAL_MODE_LABEL

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
    "current_local_first_background_facts",
    "current_local_first_visual_temporal_mode",
]
