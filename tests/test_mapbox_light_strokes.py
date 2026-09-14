"""Audited Light widths remain isolated from other styles and native overrides."""
import copy
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from tests import _path  # noqa: F401
from qfit.visualization.infrastructure import mapbox_light_strokes as strokes


def source():
    return json.loads((Path(__file__).parent / "fixtures/mapbox/light-road-width-source.json").read_text())


class LightRoadWidthTests(unittest.TestCase):
    def test_source_selection_keeps_original_classes_zoom_and_values(self):
        style = source()
        original = copy.deepcopy(style)
        self.assertEqual(strokes._source_widths(style), {
            layer["id"]: layer["paint"]["line-width"] for layer in style["layers"]
        })
        self.assertEqual(style, original)

    def test_guards_reject_other_styles_owners_and_expression_contracts(self):
        style = source()
        for owner, identity in (("custom", "light-v11"), ("mapbox", "outdoors-v12"), ("mapbox", "light-v10")):
            self.assertEqual(strokes._source_widths({**style, "owner": owner, "id": identity}), {})
        for key, value in (("id", "road-simple-custom"), ("type", "fill"), ("source-layer", "other")):
            candidate = {**style, "layers": [{**style["layers"][1], key: value}]}
            self.assertEqual(strokes._source_widths(candidate), {})
        self.assertEqual(strokes._source_widths({**style, "layers": [None, {}]}), {})
        road = next(x for x in style["layers"] if x["id"] == "road-simple")
        width = road["paint"]["line-width"]
        alternatives = [None, 2.4, [], width[:-1],
                        ["interpolate", ["linear"], *width[2:]],
                        [*width[:3], 4, *width[4:]],
                        [*width[:4], ["get", "width"], *width[5:]]]
        for invalid in alternatives:
            candidate = {**style, "layers": [{**road, "paint": {"line-width": invalid}}]}
            self.assertEqual(strokes._source_widths(candidate), {})

    def test_match_guard_rejects_unsupported_or_unsafe_widths(self):
        valid = ["match", ["get", "class"], ["street"], 1, 0]
        self.assertTrue(strokes._is_class_width_match(valid))
        for invalid in (None, [], valid[:-1], ["match", ["get", "type"], ["street"], 1, 0],
                        ["match", ["get", "class"], [], 1, 0],
                        ["match", ["get", "class"], [1], 1, 0],
                        ["match", ["get", "class"], "street", 1, 0]):
            self.assertFalse(strokes._is_class_width_match(invalid))
        for invalid in (True, -1, 301, float("inf"), float("nan"), "2", ["get", "width"]):
            self.assertFalse(strokes._is_class_width_match([*valid[:3], invalid, 0]))

    def test_adapter_changes_only_fixed_simple_owned_millimetre_strokes(self):
        class Stroke(MagicMock):
            pass

        def rule(name="road-simple", layer="road"):
            item = MagicMock()
            item.styleName.return_value = name
            item.layerName.return_value = layer
            item.symbol().symbolLayerCount.return_value = 1
            stroke = Stroke()
            stroke.widthUnit.return_value = 9
            stroke.dataDefinedProperties().property().isActive.return_value = False
            item.symbol().symbolLayer.return_value = stroke
            return item

        rules = [rule(), rule("bridge-simple"), rule("other"), rule(layer="other"), rule(), rule(), rule(), rule(), rule()]
        rules[4].symbol.return_value = None
        rules[5].symbol().symbolLayerCount.return_value = 2
        rules[6].symbol().symbolLayer.return_value = object()
        rules[7].symbol().symbolLayer().widthUnit.return_value = 3
        rules[8].symbol().symbolLayer().dataDefinedProperties().property().isActive.return_value = True
        renderer = MagicMock()
        renderer.styles.return_value = rules
        native = SimpleNamespace(
            Qgis=SimpleNamespace(RenderUnit=SimpleNamespace(Millimeters=9)),
            QgsSimpleLineSymbolLayer=Stroke,
            QgsSymbolLayer=SimpleNamespace(PropertyStrokeWidth=44),
            QgsProperty=SimpleNamespace(fromExpression=lambda expression: expression),
            QgsExpression=SimpleNamespace(quotedValue=lambda value: repr(value)),
        )
        self.assertEqual(strokes.apply_light_road_widths(renderer, {}), 0)
        renderer.styles.assert_not_called()
        with patch.dict(sys.modules, {"qgis.core": native}):
            self.assertEqual(strokes.apply_light_road_widths(renderer, source()), 2)
            renderer.setStyles.assert_called_once_with(rules)
            for item in rules[:2]:
                item.symbol().symbolLayer().setDataDefinedProperty.assert_called_once()
                expression = item.symbol().symbolLayer().setDataDefinedProperty.call_args.args[1]
                self.assertIn('"class"', expression)
                self.assertIn("1.5^", expression)
                self.assertTrue(expression.endswith("* 25.4 / 96"))
            for item in (rules[2], rules[3], rules[7], rules[8]):
                item.symbol().symbolLayer().setDataDefinedProperty.assert_not_called()
            renderer.reset_mock()
            renderer.styles.return_value = rules[2:]
            self.assertEqual(strokes.apply_light_road_widths(renderer, source()), 0)
            renderer.setStyles.assert_not_called()
