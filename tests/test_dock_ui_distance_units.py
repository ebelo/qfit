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

    def test_max_pages_all_hint_lives_on_spinbox(self):
        self.assertEqual(_property_text(_widget(self.root, "maxPagesLabel"), "text"), "Max pages")
        self.assertEqual(
            _property_text(_widget(self.root, "maxPagesSpinBox"), "specialValueText"),
            "All",
        )

    def test_advanced_fetch_group_signals_optional_defaults(self):
        group_box = _widget(self.root, "advancedFetchGroupBox")
        self.assertEqual(
            _property_text(group_box, "title"),
            "Advanced fetch settings (optional)",
        )
        self.assertIn("recommended full-sync defaults", _property_text(group_box, "toolTip"))

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

    def test_atlas_pdf_labels_use_sentence_case(self):
        self.assertEqual(_property_text(_widget(self.root, "atlasPdfGroupBox"), "title"), "Generate atlas PDF")
        self.assertEqual(
            _property_text(_widget(self.root, "generateAtlasPdfButton"), "text"),
            "Generate atlas PDF",
        )


if __name__ == "__main__":
    unittest.main()
