import unittest

from qfit.contextual_help import ContextualHelpBinder, build_dock_help_entries


class ContextualHelpTests(unittest.TestCase):
    def test_dock_help_entries_cover_high_value_confusing_controls(self):
        entries = {entry.anchor_name: entry for entry in build_dock_help_entries()}

        for anchor_name in [
            "maxDetailedActivitiesSpinBox",
            "writeActivityPointsCheckBox",
            "pointSamplingStrideSpinBox",
            "temporalModeComboBox",
            "backgroundPresetComboBox",
            "mapboxAccessTokenLineEdit",
            "atlasTargetAspectRatioSpinBox",
            "loadButton",
            "applyFiltersButton",
            "buttonLayout",
        ]:
            self.assertIn(anchor_name, entries)

        self.assertEqual(entries["maxDetailedActivitiesSpinBox"].label_text, "Detailed track fetch limit")
        self.assertTrue(entries["maxDetailedActivitiesSpinBox"].help_button)
        self.assertIn("only enriches up to 25", entries["maxDetailedActivitiesSpinBox"].helper_text)
        self.assertEqual(entries["pointSamplingStrideSpinBox"].label_text, "Keep every Nth point")
        self.assertEqual(entries["temporalModeComboBox"].label_text, "Temporal timestamps")
        self.assertEqual(entries["backgroundPresetComboBox"].label_text, "Basemap preset")
        self.assertEqual(entries["atlasTargetAspectRatioSpinBox"].label_text, "Target page aspect ratio")
        self.assertIn("Write + load layers", entries["buttonLayout"].helper_text)

    def test_contextual_help_binder_is_importable_without_instantiating_qgis_widgets(self):
        binder = ContextualHelpBinder(root=object())
        self.assertIsNotNone(binder)


if __name__ == "__main__":
    unittest.main()
