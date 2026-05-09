import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from tests import _path  # noqa: F401

from qfit.ui.application.local_first_basemap_controls import (
    bind_local_first_basemap_preset_controls,
    configure_local_first_basemap_options,
    sync_local_first_basemap_style_fields,
    update_local_first_basemap_preset,
)


class FakeCombo:
    def __init__(self):
        self.items = ["stale"]

    def clear(self):
        self.items.clear()

    def addItem(self, value):
        self.items.append(value)


class FakeSignal:
    def __init__(self):
        self.connected = []

    def connect(self, callback):
        self.connected.append(callback)


class FakeLineEdit:
    def __init__(self, value=""):
        self.value = value

    def text(self):
        return self.value

    def setText(self, value):
        self.value = value


class LocalFirstBasemapControlsTests(unittest.TestCase):
    def test_configure_options_populates_preset_and_tile_combos(self):
        dock = SimpleNamespace(
            backgroundPresetComboBox=FakeCombo(),
            tileModeComboBox=FakeCombo(),
        )

        with (
            patch(
                "qfit.ui.application.local_first_basemap_controls."
                "background_preset_names",
                return_value=("Outdoor", "Custom"),
            ),
            patch(
                "qfit.ui.application.local_first_basemap_controls.TILE_MODES",
                ("raster", "vector"),
            ),
        ):
            configure_local_first_basemap_options(dock)

        self.assertEqual(dock.backgroundPresetComboBox.items, ["Outdoor", "Custom"])
        self.assertEqual(dock.tileModeComboBox.items, ["raster", "vector"])

    def test_sync_style_fields_uses_controller_defaults(self):
        controller = MagicMock()
        controller.resolve_style_defaults.return_value = ("mapbox", "outdoors-v12")
        dock = SimpleNamespace(
            background_controller=controller,
            mapboxStyleOwnerLineEdit=FakeLineEdit(" existing-owner "),
            mapboxStyleIdLineEdit=FakeLineEdit(" existing-style "),
        )

        sync_local_first_basemap_style_fields(dock, "Outdoor", force=False)

        controller.resolve_style_defaults.assert_called_once_with(
            "Outdoor",
            current_owner="existing-owner",
            current_style_id="existing-style",
            force=False,
        )
        self.assertEqual(dock.mapboxStyleOwnerLineEdit.value, "mapbox")
        self.assertEqual(dock.mapboxStyleIdLineEdit.value, "outdoors-v12")

    def test_update_preset_syncs_fields_and_visibility(self):
        dock = SimpleNamespace(
            background_controller=MagicMock(),
            mapboxStyleOwnerLineEdit=FakeLineEdit(),
            mapboxStyleIdLineEdit=FakeLineEdit(),
        )
        dock.background_controller.resolve_style_defaults.return_value = (
            "owner",
            "style",
        )

        with patch(
            "qfit.ui.application.local_first_basemap_controls."
            "update_local_first_mapbox_custom_style_visibility"
        ) as update_visibility:
            update_local_first_basemap_preset(dock, "Custom")

        dock.background_controller.resolve_style_defaults.assert_called_once_with(
            "Custom",
            current_owner="",
            current_style_id="",
            force=True,
        )
        update_visibility.assert_called_once_with(dock, "Custom")

    def test_bind_preset_controls_routes_signal_to_policy(self):
        signal = FakeSignal()
        dock = SimpleNamespace(
            backgroundPresetComboBox=SimpleNamespace(currentTextChanged=signal),
        )

        with patch(
            "qfit.ui.application.local_first_basemap_controls."
            "update_local_first_basemap_preset"
        ) as update_preset:
            bind_local_first_basemap_preset_controls(dock)
            signal.connected[0]("Satellite")

        update_preset.assert_called_once_with(dock, "Satellite")


if __name__ == "__main__":
    unittest.main()
