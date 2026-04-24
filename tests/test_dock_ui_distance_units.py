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


if __name__ == "__main__":
    unittest.main()
