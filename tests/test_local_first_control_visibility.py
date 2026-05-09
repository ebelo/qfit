import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from tests import _path  # noqa: F401

from qfit.ui.application.local_first_control_visibility import (
    ADVANCED_FETCH_VISIBILITY_WIDGETS,
    DETAILED_FETCH_VISIBILITY_WIDGETS,
    MAPBOX_CUSTOM_STYLE_VISIBILITY_WIDGETS,
    POINT_SAMPLING_VISIBILITY_WIDGETS,
    bind_local_first_conditional_visibility_controls,
    build_advanced_fetch_visibility_update,
    build_detailed_fetch_visibility_update,
    build_local_first_conditional_visibility_updates,
    build_mapbox_custom_style_visibility_update,
    build_point_sampling_visibility_update,
    refresh_local_first_conditional_control_visibility,
    set_named_widgets_visible,
    update_local_first_advanced_fetch_visibility,
    update_local_first_detailed_fetch_visibility,
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
    def test_advanced_fetch_visibility_targets_only_details_panel(self):
        update = build_advanced_fetch_visibility_update(True)

        self.assertEqual(update.key, "advanced_fetch")
        self.assertEqual(update.widget_attrs, ADVANCED_FETCH_VISIBILITY_WIDGETS)
        self.assertEqual(update.widget_attrs, ("advancedFetchSettingsWidget",))
        self.assertTrue(update.visible)

    def test_detailed_fetch_visibility_keeps_backfill_and_strategy_controls_together(self):
        update = build_detailed_fetch_visibility_update(False)

        self.assertEqual(update.key, "detailed_fetch")
        self.assertEqual(update.widget_attrs, DETAILED_FETCH_VISIBILITY_WIDGETS)
        self.assertIn("backfillMissingDetailedRoutesButton", update.widget_attrs)
        self.assertIn("detailedRouteStrategyComboBox", update.widget_attrs)
        self.assertFalse(update.visible)

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
            advancedFetchGroupBox=SimpleNamespace(isChecked=lambda: True),
            detailedStreamsCheckBox=SimpleNamespace(isChecked=lambda: False),
            backgroundPresetComboBox=SimpleNamespace(currentText=lambda: "Custom"),
            writeActivityPointsCheckBox=SimpleNamespace(isChecked=lambda: True),
        )

        updates = build_local_first_conditional_visibility_updates(dock)

        self.assertEqual(
            [(update.key, update.visible) for update in updates],
            [
                ("advanced_fetch", True),
                ("detailed_fetch", False),
                ("mapbox_custom_style", True),
                ("point_sampling", True),
            ],
        )

    def test_build_conditional_visibility_updates_ignores_destroyed_qt_widgets(self):
        def raise_runtime_error():
            raise RuntimeError("wrapped C/C++ object has been deleted")

        dock = SimpleNamespace(
            advancedFetchGroupBox=SimpleNamespace(isChecked=raise_runtime_error),
            backgroundPresetComboBox=SimpleNamespace(currentText=raise_runtime_error),
        )

        updates = build_local_first_conditional_visibility_updates(dock)

        self.assertEqual(
            [(update.key, update.visible) for update in updates],
            [
                ("advanced_fetch", False),
                ("detailed_fetch", False),
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
            advancedFetchGroupBox=SimpleNamespace(isChecked=lambda: True),
            detailedStreamsCheckBox=SimpleNamespace(isChecked=lambda: False),
            backgroundPresetComboBox=SimpleNamespace(currentText=lambda: "Custom"),
            writeActivityPointsCheckBox=SimpleNamespace(isChecked=lambda: False),
            advancedFetchSettingsWidget=MagicMock(),
            backfillMissingDetailedRoutesButton=MagicMock(),
            mapboxStyleOwnerLabel=MagicMock(),
            pointSamplingStrideLabel=MagicMock(),
        )

        refresh_local_first_conditional_control_visibility(dock)

        dock.advancedFetchSettingsWidget.setVisible.assert_called_once_with(True)
        dock.backfillMissingDetailedRoutesButton.setVisible.assert_called_once_with(False)
        dock.mapboxStyleOwnerLabel.setVisible.assert_called_once_with(True)
        dock.pointSamplingStrideLabel.setVisible.assert_called_once_with(False)

    def test_update_helpers_apply_named_visibility_groups(self):
        dock = SimpleNamespace(
            advancedFetchSettingsWidget=MagicMock(),
            backfillMissingDetailedRoutesButton=MagicMock(),
            pointSamplingStrideLabel=MagicMock(),
            mapboxStyleOwnerLabel=MagicMock(),
        )

        update_local_first_advanced_fetch_visibility(dock, True)
        update_local_first_detailed_fetch_visibility(dock, False)
        update_local_first_point_sampling_visibility(dock, True)
        update_local_first_mapbox_custom_style_visibility(dock, "Custom")

        dock.advancedFetchSettingsWidget.setVisible.assert_called_once_with(True)
        dock.backfillMissingDetailedRoutesButton.setVisible.assert_called_once_with(False)
        dock.pointSamplingStrideLabel.setVisible.assert_called_once_with(True)
        dock.mapboxStyleOwnerLabel.setVisible.assert_called_once_with(True)

    def test_bind_conditional_visibility_controls_routes_signals_to_application_rules(self):
        detailed_signal = _FakeSignal()
        point_signal = _FakeSignal()
        advanced_signal = _FakeSignal()
        dock = SimpleNamespace(
            detailedStreamsCheckBox=SimpleNamespace(toggled=detailed_signal),
            writeActivityPointsCheckBox=SimpleNamespace(toggled=point_signal),
            advancedFetchGroupBox=SimpleNamespace(toggled=advanced_signal),
            backfillMissingDetailedRoutesButton=MagicMock(),
            pointSamplingStrideLabel=MagicMock(),
            advancedFetchSettingsWidget=MagicMock(),
        )

        bind_local_first_conditional_visibility_controls(dock)
        detailed_signal.emit(False)
        point_signal.emit(True)
        advanced_signal.emit(True)

        dock.backfillMissingDetailedRoutesButton.setVisible.assert_called_once_with(False)
        dock.pointSamplingStrideLabel.setVisible.assert_called_once_with(True)
        dock.advancedFetchSettingsWidget.setVisible.assert_called_once_with(True)


if __name__ == "__main__":
    unittest.main()
