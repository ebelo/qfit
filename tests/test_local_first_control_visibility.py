import unittest

from tests import _path  # noqa: F401

from qfit.ui.application.local_first_control_visibility import (
    ADVANCED_FETCH_VISIBILITY_WIDGETS,
    DETAILED_FETCH_VISIBILITY_WIDGETS,
    MAPBOX_CUSTOM_STYLE_VISIBILITY_WIDGETS,
    POINT_SAMPLING_VISIBILITY_WIDGETS,
    build_advanced_fetch_visibility_update,
    build_detailed_fetch_visibility_update,
    build_mapbox_custom_style_visibility_update,
    build_point_sampling_visibility_update,
)


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


if __name__ == "__main__":
    unittest.main()
