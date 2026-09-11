"""Open font selection retains source roles without guessing installed faces."""
import hashlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from tests import _path  # noqa: F401
from qfit.visualization.infrastructure import mapbox_open_fonts as fonts


def source(layers):
    return {"owner": "mapbox", "id": "outdoors-v12", "layers": layers}


def layer(name, stack):
    return {"id": name, "layout": {"text-font": stack}}


class OpenFontTests(unittest.TestCase):
    def test_source_roles_and_unknown_expression_stacks(self):
        style = source([
            layer("road", ["DIN Pro Regular", "Arial Unicode MS Regular"]),
            layer("city", ["DIN Pro Medium"]),
            layer("water", ["DIN Pro Italic"]),
            layer("shield", ["DIN Pro Bold"]),
            layer("unknown", ["Other Font"]),
            layer("expression", ["case", ["has", "name"], ["DIN Pro Bold"]]),
            layer("nested", [["DIN Pro Bold"]]),
            layer("empty", []), layer("text", "DIN Pro Medium"),
            layer("", ["DIN Pro Bold"]), None,
        ])
        self.assertEqual(fonts.source_font_styles(style), {
            "road": "Regular", "city": "Medium", "water": "Italic", "shield": "Bold",
        })
        for owner, identity in [("custom", "outdoors-v12"), ("mapbox", "light-v10"), ("custom", "light-v11")]:
            with self.subTest(owner=owner, identity=identity):
                style.update(owner=owner, id=identity)
                self.assertEqual(fonts.source_font_styles(style), {})

    def test_only_exact_resolved_faces_are_available(self):
        def resolved(font):
            face = font.setStyleName.call_args.args[0]
            return SimpleNamespace(
                family=lambda: "DejaVu Sans" if face == "Bold" else fonts.OPEN_FONT_FAMILY,
                styleName=lambda: "Regular" if face == "Medium" else face,
            )
        qt = SimpleNamespace(QFont=MagicMock(side_effect=lambda *_: MagicMock()), QFontInfo=resolved)
        with patch.dict(sys.modules, {"qgis.PyQt.QtGui": qt}):
            self.assertEqual(fonts._available_styles(["Regular", "Medium", "Bold"]), {"Regular"})

    def test_preserves_unknown_owners_and_missing_faces(self):
        style = source([
            layer("road", ["DIN Pro Regular"]),
            layer("road-other", ["Unknown"]),
            layer("city", ["DIN Pro Medium"]),
        ])
        labels = []
        for name in ["road-z10", "road-other-z10", "city", "unrelated", "roadside"]:
            label = MagicMock()
            label.styleName.return_value = name
            labels.append(label)
        labeling = MagicMock()
        labeling.styles.return_value = labels
        with patch.object(fonts, "_available_styles", return_value={"Regular"}):
            self.assertEqual(fonts.apply_available_outdoors_fonts(labeling, style), 1)
        fmt = labels[0].labelSettings().format()
        fmt.font().setFamily.assert_called_once_with(fonts.OPEN_FONT_FAMILY)
        fmt.font().setStyleName.assert_called_once_with("Regular")
        labels[0].setLabelSettings.assert_called_once()
        for label in labels[1:]:
            label.setLabelSettings.assert_not_called()
        labeling.setStyles.assert_called_once_with(labels)

    def test_absent_fonts_and_other_presets_leave_labeling_untouched(self):
        labeling = MagicMock()
        labeling.styles.return_value = []
        with patch.object(fonts, "_available_styles", return_value=set()):
            self.assertEqual(fonts.apply_available_outdoors_fonts(labeling, source([layer("city", ["DIN Pro Medium"])])), 0)
            self.assertEqual(fonts.apply_available_outdoors_fonts(labeling, {"layers": []}), 0)
        labeling.setStyles.assert_not_called()

    def test_light_inventory_and_compatibility_entry_point(self):
        style = {"owner": "mapbox", "id": "light-v11", "layers": [
            layer("poi-label", ["DIN Pro Italic"]),
            layer("country-label", ["DIN Pro Medium"]),
        ]}
        self.assertEqual(fonts.source_font_styles(style), {
            "poi-label": "Italic", "country-label": "Medium",
        })
        labeling = MagicMock()
        self.assertEqual(fonts.apply_available_outdoors_fonts(labeling, style), 0)
        labeling.styles.assert_not_called()

    def test_light_zoom_splits_preserve_baseline_and_supported_roles(self):
        import copy

        class Label:
            def __init__(self, name, minimum, maximum):
                self.name, self.minimum, self.maximum = name, minimum, maximum
            def styleName(self):
                return self.name
            def minZoomLevel(self):
                return self.minimum
            def maxZoomLevel(self):
                return self.maximum
            def setStyleName(self, name):
                self.name = name
            def setMinZoomLevel(self, value):
                self.minimum = value
            def setMaxZoomLevel(self, value):
                self.maximum = value

        style = {"owner": "mapbox", "id": "light-v11", "layers": [
            layer("settlement-major-label", ["DIN Pro Medium"]),
            layer("road-label-simple", ["DIN Pro Regular"]),
            layer("water-line-label", ["DIN Pro Italic"]),
            layer("country-label", ["DIN Pro Medium"]),
            layer("poi-label", ["DIN Pro Italic"]),
            layer("road-label-simple-unknown", ["Unknown"]),
        ]}
        labels = [Label(*args) for args in [
            ("settlement-major-label", 2, 14),
            ("road-label-simple-z12-to-z15", 12, 14),
            ("road-label-simple", 15, -1),
            ("water-line-label-ocean", 1, -1),
            ("country-label", 1, 9),
            ("poi-label-below-z16", 6, 15),
            ("poi-label-z16-to-z17", 16, 16),
            ("road-label-simple-unknown", 15, -1),
        ]]
        labeling = MagicMock()
        labeling.styles.return_value = labels
        core = SimpleNamespace(QgsVectorTileBasicLabelingStyle=copy.deepcopy)
        with patch.dict(sys.modules, {"qgis.core": core}), \
             patch.object(fonts, "_available_styles", return_value=set(fonts.DIN_STYLES.values())), \
             patch.object(fonts, "_set_open_font") as apply:
            self.assertEqual(fonts.apply_available_mapbox_fonts(labeling, style), 4)
        result = labeling.setStyles.call_args.args[0]
        self.assertEqual([(x.minimum, x.maximum) for x in result[:2]], [(2, 7), (8, 14)])
        self.assertIs(result[0], labels[0])
        self.assertIsNot(result[1], labels[0])
        self.assertEqual([c.args[1] for c in apply.call_args_list], ["Medium", "Regular", "Italic", "Italic"])
        self.assertEqual([c.args[0] for c in apply.call_args_list], [result[1], labels[2], labels[3], labels[6]])

    def test_missing_light_face_does_not_split_or_mutate_rules(self):
        labeling = MagicMock()
        label = MagicMock()
        label.styleName.return_value = "settlement-major-label"
        labeling.styles.return_value = [label]
        style = {"owner": "mapbox", "id": "light-v11", "layers": [
            layer("settlement-major-label", ["DIN Pro Medium"]),
        ]}
        with patch.object(fonts, "_available_styles", return_value=set()):
            self.assertEqual(fonts.apply_available_mapbox_fonts(labeling, style), 0)
        labeling.setStyles.assert_not_called()
        label.setMaxZoomLevel.assert_not_called()

    def test_vendored_font_bytes_match_pinned_provenance_and_include_license(self):
        directory = Path(__file__).resolve().parents[1] / "scripts/docker/fonts/barlow"
        manifest = json.loads((directory / "provenance.json").read_text())
        for name, digest in manifest["files"].items():
            with self.subTest(name=name):
                self.assertEqual(hashlib.sha256((directory / name).read_bytes()).hexdigest(), digest)
        self.assertIn("SIL OPEN FONT LICENSE Version 1.1", (directory / "OFL.txt").read_text())
        self.assertEqual(set(directory.glob("*.ttf")), {
            directory / f"Barlow-{face}.ttf" for face in fonts.DIN_STYLES.values()
        })
