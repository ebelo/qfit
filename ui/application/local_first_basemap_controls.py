from __future__ import annotations

from ...mapbox_config import TILE_MODES, background_preset_names
from .local_first_control_visibility import update_local_first_mapbox_custom_style_visibility


def configure_local_first_basemap_options(dock) -> None:
    """Populate basemap backing controls used by the local-first Settings page."""

    preset_combo = getattr(dock, "backgroundPresetComboBox", None)
    if preset_combo is not None:
        _replace_combo_items(preset_combo, background_preset_names())

    tile_mode_combo = getattr(dock, "tileModeComboBox", None)
    if tile_mode_combo is not None:
        _replace_combo_items(tile_mode_combo, TILE_MODES)


def bind_local_first_basemap_preset_controls(dock) -> None:
    """Bind local-first basemap preset changes to backing field policy."""

    preset_combo = getattr(dock, "backgroundPresetComboBox", None)
    signal = getattr(preset_combo, "currentTextChanged", None)
    connect = getattr(signal, "connect", None)
    if callable(connect):
        connect(
            lambda preset_name: update_local_first_basemap_preset(dock, preset_name)
        )


def update_local_first_basemap_preset(dock, preset_name: str) -> None:
    """Apply a user-selected basemap preset to local-first backing controls."""

    sync_local_first_basemap_style_fields(dock, preset_name, force=True)
    update_local_first_mapbox_custom_style_visibility(dock, preset_name)


def sync_local_first_basemap_style_fields(
    dock,
    preset_name: str | None,
    *,
    force: bool = False,
) -> None:
    """Sync Mapbox owner/style fields from the selected basemap preset."""

    controller = getattr(dock, "background_controller", None)
    resolve_style_defaults = getattr(controller, "resolve_style_defaults", None)
    if not callable(resolve_style_defaults):
        return

    result = resolve_style_defaults(
        preset_name,
        current_owner=_line_edit_text(getattr(dock, "mapboxStyleOwnerLineEdit", None)),
        current_style_id=_line_edit_text(getattr(dock, "mapboxStyleIdLineEdit", None)),
        force=force,
    )
    if result is None:
        return

    style_owner, style_id = result
    _set_line_edit_text(getattr(dock, "mapboxStyleOwnerLineEdit", None), style_owner)
    _set_line_edit_text(getattr(dock, "mapboxStyleIdLineEdit", None), style_id)


def _replace_combo_items(combo, values) -> None:
    clear = getattr(combo, "clear", None)
    if callable(clear):
        clear()
    add_item = getattr(combo, "addItem", None)
    if callable(add_item):
        for value in values:
            add_item(value)


def _line_edit_text(line_edit) -> str:
    text = getattr(line_edit, "text", None)
    if not callable(text):
        return ""
    return str(text()).strip()


def _set_line_edit_text(line_edit, text: str) -> None:
    set_text = getattr(line_edit, "setText", None)
    if callable(set_text):
        set_text(text)


__all__ = [
    "bind_local_first_basemap_preset_controls",
    "configure_local_first_basemap_options",
    "sync_local_first_basemap_style_fields",
    "update_local_first_basemap_preset",
]
