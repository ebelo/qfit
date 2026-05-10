import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from tests import _path  # noqa: F401

from qfit.ui.application.local_first_control_visibility import (
    MAPBOX_CUSTOM_STYLE_VISIBILITY_WIDGETS,
    POINT_SAMPLING_VISIBILITY_WIDGETS,
    bind_local_first_conditional_visibility_controls,
    build_local_first_conditional_visibility_updates,
    build_mapbox_custom_style_visibility_update,
    build_point_sampling_visibility_update,
    refresh_local_first_conditional_control_visibility,
    set_named_widgets_visible,
    update_local_first_mapbox_custom_style_visibility,
    update_local_first_point_sampling_visibility,
)


class _FakeSignal:
    def __init__(self):
        self.connected = []

    def connect(self, callback):
        self.connected.append(callback)

    def emit(self, value):
        for callback in list(self.connected):
            callback(value)


class LocalFirstControlVisibilityTests(unittest.TestCase):
    def test_point_sampling_visibility_targets_stride_controls(self):
        update = build_point_sampling_visibility_update(True)

        self.assertEqual(update.key, "point_sampling")
        self.assertEqual(update.widget_attrs, POINT_SAMPLING_VISIBILITY_WIDGETS)
        self.assertIn("pointSamplingStrideSpinBox", update.widget_attrs)
        self.assertTrue(update.visible)

    def test_mapbox_visibility_uses_custom_preset_policy(self):
        builtin_update = build_mapbox_custom_style_visibility_update("Outdoor")
        custom_update = build_mapbox_custom_style_visibility_update("Custom")

        self.assertEqual(builtin_update.key, "mapbox_custom_style")
        self.assertEqual(
            builtin_update.widget_attrs,
            MAPBOX_CUSTOM_STYLE_VISIBILITY_WIDGETS,
        )
        self.assertIn("mapboxStyleOwnerLineEdit", builtin_update.widget_attrs)
        self.assertFalse(builtin_update.visible)
        self.assertTrue(custom_update.visible)

    def test_build_conditional_visibility_updates_reads_live_control_state(self):
        dock = SimpleNamespace(
            backgroundPresetComboBox=SimpleNamespace(currentText=lambda: "Custom"),
            writeActivityPointsCheckBox=SimpleNamespace(isChecked=lambda: True),
        )

        updates = build_local_first_conditional_visibility_updates(dock)

        self.assertEqual(
            [(update.key, update.visible) for update in updates],
            [
                ("mapbox_custom_style", True),
                ("point_sampling", True),
            ],
        )

    def test_build_conditional_visibility_updates_ignores_destroyed_qt_widgets(self):
        def raise_runtime_error():
            raise RuntimeError("wrapped C/C++ object has been deleted")

        dock = SimpleNamespace(
            backgroundPresetComboBox=SimpleNamespace(currentText=raise_runtime_error),
        )

        updates = build_local_first_conditional_visibility_updates(dock)

        self.assertEqual(
            [(update.key, update.visible) for update in updates],
            [
                ("mapbox_custom_style", False),
                ("point_sampling", False),
            ],
        )

    def test_set_named_widgets_visible_skips_missing_and_non_widget_attrs(self):
        visible_widget = MagicMock()
        dock = SimpleNamespace(
            visibleWidget=visible_widget,
            plainObject=object(),
        )

        set_named_widgets_visible(
            dock,
            ("visibleWidget", "plainObject", "missingWidget"),
            False,
        )

        visible_widget.setVisible.assert_called_once_with(False)

    def test_refresh_conditional_visibility_applies_all_updates(self):
        dock = SimpleNamespace(
            backgroundPresetComboBox=SimpleNamespace(currentText=lambda: "Custom"),
            writeActivityPointsCheckBox=SimpleNamespace(isChecked=lambda: False),
            mapboxStyleOwnerLabel=MagicMock(),
            pointSamplingStrideLabel=MagicMock(),
        )

        refresh_local_first_conditional_control_visibility(dock)

        dock.mapboxStyleOwnerLabel.setVisible.assert_called_once_with(True)
        dock.pointSamplingStrideLabel.setVisible.assert_called_once_with(False)

    def test_update_helpers_apply_named_visibility_groups(self):
        dock = SimpleNamespace(
            pointSamplingStrideLabel=MagicMock(),
            mapboxStyleOwnerLabel=MagicMock(),
        )

        update_local_first_point_sampling_visibility(dock, True)
        update_local_first_mapbox_custom_style_visibility(dock, "Custom")

        dock.pointSamplingStrideLabel.setVisible.assert_called_once_with(True)
        dock.mapboxStyleOwnerLabel.setVisible.assert_called_once_with(True)

    def test_bind_conditional_visibility_controls_routes_signals_to_application_rules(self):
        point_signal = _FakeSignal()
        dock = SimpleNamespace(
            writeActivityPointsCheckBox=SimpleNamespace(toggled=point_signal),
            pointSamplingStrideLabel=MagicMock(),
        )

        bind_local_first_conditional_visibility_controls(dock)
        point_signal.emit(True)

        dock.pointSamplingStrideLabel.setVisible.assert_called_once_with(True)


if __name__ == "__main__":
    unittest.main()
