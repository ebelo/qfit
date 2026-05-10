import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from tests import _path  # noqa: F401


UI_PATH = Path(__file__).resolve().parents[1] / "qfit_dockwidget_base.ui"


def _widget(root: ET.Element, name: str) -> ET.Element:
    for widget in root.iter("widget"):
        if widget.get("name") == name:
            return widget
    raise AssertionError(f"widget {name!r} not found")


def _property_text(widget: ET.Element, property_name: str) -> str:
    for prop in widget.findall("property"):
        if prop.get("name") == property_name:
            string = prop.find("string")
            return string.text if string is not None and string.text is not None else ""
    raise AssertionError(f"property {property_name!r} not found on {widget.get('name')!r}")


class DockUiFieldGrammarTests(unittest.TestCase):
    def setUp(self):
        self.root = ET.parse(UI_PATH).getroot()

    def test_top_level_sections_use_task_labels_without_step_numbers(self):
        self.assertEqual(
            _property_text(_widget(self.root, "workflowLabel"), "text"),
            "Sections: Fetch & store · Visualize · Analyze · Publish",
        )

        expected_titles = {
            "credentialsGroupBox": "Strava connection",
            "activitiesGroupBox": "Fetch activities",
            "outputGroupBox": "Store data",
            "styleGroupBox": "Visualize",
            "analysisWorkflowGroupBox": "Analyze",
            "publishGroupBox": "Publish / atlas",
        }
        for widget_name, title in expected_titles.items():
            with self.subTest(widget_name=widget_name):
                self.assertEqual(_property_text(_widget(self.root, widget_name), "title"), title)

    def test_distance_labels_keep_units_in_spinbox_suffixes(self):
        self.assertEqual(_property_text(_widget(self.root, "distanceLabel"), "text"), "Min distance")
        self.assertEqual(
            _property_text(_widget(self.root, "maxDistanceLabel"), "text"),
            "Max distance",
        )
        self.assertEqual(
            _property_text(_widget(self.root, "minDistanceSpinBox"), "suffix"),
            " km",
        )
        self.assertEqual(
            _property_text(_widget(self.root, "maxDistanceSpinBox"), "suffix"),
            " km",
        )

    def test_atlas_labels_use_sentence_case(self):
        self.assertEqual(_property_text(_widget(self.root, "atlasTitleLabel"), "text"), "Atlas title")
        self.assertEqual(
            _property_text(_widget(self.root, "atlasSubtitleLabel"), "text"),
            "Atlas subtitle",
        )

    def test_activity_points_checkbox_uses_human_readable_label(self):
        self.assertEqual(
            _property_text(_widget(self.root, "writeActivityPointsCheckBox"), "text"),
            "Generate sampled activity points for analysis",
        )

    def test_point_sampling_label_describes_user_visible_effect(self):
        self.assertEqual(
            _property_text(_widget(self.root, "pointSamplingStrideLabel"), "text"),
            "Keep every Nth point",
        )

    def test_apply_filters_button_uses_short_primary_action_label(self):
        self.assertEqual(_property_text(_widget(self.root, "applyFiltersButton"), "text"), "Apply filters")

    def test_basemap_checkbox_uses_short_action_label(self):
        self.assertEqual(_property_text(_widget(self.root, "backgroundMapCheckBox"), "text"), "Enable Mapbox basemap")

    def test_detailed_route_actions_use_short_labels(self):
        self.assertEqual(_property_text(_widget(self.root, "backfillMissingDetailedRoutesButton"), "text"), "Backfill routes")

    def test_atlas_pdf_labels_use_sentence_case(self):
        self.assertEqual(_property_text(_widget(self.root, "atlasPdfGroupBox"), "title"), "Generate atlas PDF")
        self.assertEqual(
            _property_text(_widget(self.root, "generateAtlasPdfButton"), "text"),
            "Generate atlas PDF",
        )

    def test_atlas_help_uses_plain_language_layer_name(self):
        publish_help = _property_text(_widget(self.root, "publishHelpLabel"), "text")
        atlas_help = _property_text(_widget(self.root, "atlasPdfHelpLabel"), "text")
        self.assertNotIn("activity_atlas_pages", publish_help)
        self.assertNotIn("activity_atlas_pages", atlas_help)
        self.assertIn("atlas pages layer", atlas_help)


if __name__ == "__main__":
    unittest.main()
