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


class LightNationalBoundaryTests(unittest.TestCase):
    def source(self):
        return json.loads((Path(__file__).parent / "fixtures/mapbox/light-boundary-source.json").read_text())

    def test_source_contract_is_exact_light_ordinary_national_boundary(self):
        source_style = self.source()
        original = copy.deepcopy(source_style)
        self.assertTrue(strokes._has_solid_national_boundary(source_style))
        self.assertEqual(source_style, original)
        for owner, identity in (("custom", "light-v11"), ("mapbox", "outdoors-v12"), ("mapbox", "light-v10")):
            self.assertFalse(strokes._has_solid_national_boundary({**source_style, "owner": owner, "id": identity}))
        layer = next(item for item in source_style["layers"] if item["id"] == "admin-0-boundary")
        for key, value in (("id", "admin-0-boundary-disputed"), ("type", "fill"), ("source-layer", "road"), ("paint", None)):
            self.assertFalse(strokes._has_solid_national_boundary({**source_style, "layers": [{**layer, key: value}]}))
        for key, value in (("line-width", 2.6), ("line-width", ["interpolate", ["linear"], ["zoom"], 3, 1, 12, 3]),
                           ("line-dasharray", [10, 1]), ("line-dasharray", ["literal", [10, 0]])):
            altered = {**layer, "paint": {**layer["paint"], key: value}}
            self.assertFalse(strokes._has_solid_national_boundary({**source_style, "layers": [altered]}))
        self.assertFalse(strokes._has_solid_national_boundary({**source_style, "layers": [None, {}]}))

    def test_adapter_preserves_native_overrides_other_rules_and_source(self):
        class Stroke(MagicMock):
            pass

        def rule():
            item = MagicMock()
            item.styleName.return_value = "admin-0-boundary"
            item.layerName.return_value = "admin"
            item.symbol().symbolLayerCount.return_value = 1
            stroke = Stroke()
            stroke.widthUnit.return_value = 9
            stroke.customDashPatternUnit.return_value = 9
            stroke.useCustomDashPattern.return_value = True
            stroke.penStyle.return_value = 1
            stroke.width.return_value = 0.2
            stroke.customDashVector.return_value = [2, 0]
            stroke.dataDefinedProperties().hasActiveProperties.return_value = False
            item.symbol().symbolLayer.return_value = stroke
            return item

        rules = [rule() for _ in range(14)]
        rules[1].styleName.return_value = "admin-0-boundary-disputed"
        rules[2].layerName.return_value = "other"
        rules[3].symbol.return_value = None
        rules[4].symbol().symbolLayerCount.return_value = 2
        rules[5].symbol().symbolLayer.return_value = object()
        for index, method, value in ((6, "widthUnit", 3), (7, "customDashPatternUnit", 3),
                                     (8, "useCustomDashPattern", False), (9, "penStyle", 2),
                                     (11, "customDashVector", [2, 0, 3, 0]),
                                     (12, "customDashVector", [2, 1]), (13, "customDashVector", [3, 0])):
            getattr(rules[index].symbol().symbolLayer(), method).return_value = value
        rules[10].symbol().symbolLayer().dataDefinedProperties().hasActiveProperties.return_value = True
        renderer = MagicMock()
        renderer.styles.return_value = rules
        native = SimpleNamespace(
            Qgis=SimpleNamespace(RenderUnit=SimpleNamespace(Millimeters=9)),
            QgsSimpleLineSymbolLayer=Stroke, QgsSymbolLayer=SimpleNamespace(PropertyStrokeWidth=44),
            QgsProperty=SimpleNamespace(fromExpression=lambda expression: expression),
        )
        qt = SimpleNamespace(Qt=SimpleNamespace(PenStyle=SimpleNamespace(SolidLine=1)))
        self.assertEqual(strokes.apply_light_national_boundary_stroke(renderer, {}), 0)
        renderer.styles.assert_not_called()
        source_style = self.source()
        original = copy.deepcopy(source_style)
        with patch.dict(sys.modules, {"qgis.core": native, "qgis.PyQt.QtCore": qt}):
            self.assertEqual(strokes.apply_light_national_boundary_stroke(renderer, source_style), 1)
            renderer.setStyles.assert_called_once_with(rules)
            stroke = rules[0].symbol().symbolLayer()
            stroke.setUseCustomDashPattern.assert_called_once_with(False)
            stroke.setDataDefinedProperty.assert_called_once_with(44, strokes._NATIONAL_BOUNDARY_EXPRESSION)
            for item in rules[6:]:
                item.symbol().symbolLayer().setUseCustomDashPattern.assert_not_called()
                item.symbol().symbolLayer().setDataDefinedProperty.assert_not_called()
            renderer.reset_mock()
            renderer.styles.return_value = rules[1:]
            self.assertEqual(strokes.apply_light_national_boundary_stroke(renderer, source_style), 0)
            renderer.setStyles.assert_not_called()
        self.assertEqual(source_style, original)


class LightNationalBackgroundTests(unittest.TestCase):
    def source(self):
        return json.loads((Path(__file__).parent / "fixtures/mapbox/light-boundary-source.json").read_text())

    def test_exact_source_contract_and_duplicate_owners(self):
        source_style = self.source()
        original = copy.deepcopy(source_style)
        self.assertTrue(strokes._has_national_background(source_style))
        owner = next(x for x in source_style["layers"] if x["id"] == "admin-0-boundary-bg")
        for identity in ({"owner": "custom"}, {"id": "outdoors-v12"}, {"id": "light-v10"}):
            self.assertFalse(strokes._has_national_background({**source_style, **identity}))
        for key, value in (("id", "admin-1-boundary-bg"), ("type", "fill"),
                           ("source-layer", "road"), ("paint", None)):
            self.assertFalse(strokes._has_national_background({**source_style, "layers": [{**owner, key: value}]}))
        for key in owner["paint"]:
            altered = {**owner, "paint": {**owner["paint"], key: 1}}
            self.assertFalse(strokes._has_national_background({**source_style, "layers": [altered]}))
        for layers in ([None, {}], [owner, owner], []):
            self.assertFalse(strokes._has_national_background({**source_style, "layers": layers}))
        self.assertEqual(source_style, original)

    def test_native_override_and_symbol_guards(self):
        class Stroke(MagicMock):
            pass

        def rule():
            item = MagicMock()
            item.styleName.return_value = "admin-0-boundary-bg"
            item.layerName.return_value = "admin"
            item.symbol().symbolLayerCount.return_value = 1
            item.symbol().dataDefinedProperties().hasActiveProperties.return_value = False
            stroke = Stroke()
            stroke.widthUnit.return_value = 9
            stroke.useCustomDashPattern.return_value = False
            stroke.penStyle.return_value = 1
            stroke.dataDefinedProperties().hasActiveProperties.return_value = False
            item.symbol().symbolLayer.return_value = stroke
            return item

        rules = [rule() for _ in range(10)]
        rules[1].styleName.return_value = "admin-0-boundary-disputed"
        rules[2].layerName.return_value = "road"
        rules[3].symbol.return_value = None
        rules[4].symbol().symbolLayerCount.return_value = 2
        rules[5].symbol().dataDefinedProperties().hasActiveProperties.return_value = True
        rules[6].symbol().symbolLayer.return_value = object()
        rules[7].symbol().symbolLayer().widthUnit.return_value = 3
        rules[8].symbol().symbolLayer().useCustomDashPattern.return_value = True
        rules[9].symbol().symbolLayer().dataDefinedProperties().hasActiveProperties.return_value = True
        other_pen = rule()
        other_pen.symbol().symbolLayer().penStyle.return_value = 2
        rules.append(other_pen)
        renderer = MagicMock()
        renderer.styles.return_value = rules
        native = SimpleNamespace(
            Qgis=SimpleNamespace(RenderUnit=SimpleNamespace(Millimeters=9)),
            QgsSimpleLineSymbolLayer=Stroke,
            QgsSymbol=SimpleNamespace(PropertyOpacity=0),
            QgsSymbolLayer=SimpleNamespace(PropertyStrokeWidth=44),
            QgsProperty=SimpleNamespace(fromExpression=lambda value: value),
        )
        qt = SimpleNamespace(Qt=SimpleNamespace(PenStyle=SimpleNamespace(SolidLine=1)))
        self.assertEqual(strokes.apply_light_national_background(renderer, {}), 0)
        renderer.styles.assert_not_called()
        source_style = self.source()
        original = copy.deepcopy(source_style)
        with patch.dict(sys.modules, {"qgis.core": native, "qgis.PyQt.QtCore": qt}):
            self.assertEqual(strokes.apply_light_national_background(renderer, source_style), 1)
            renderer.setStyles.assert_called_once_with(rules)
            rules[0].symbol().symbolLayer().setDataDefinedProperty.assert_called_once_with(44, strokes._NATIONAL_BACKGROUND_WIDTH)
            rules[0].symbol().setDataDefinedProperty.assert_called_once_with(0, strokes._NATIONAL_BACKGROUND_OPACITY)
            for item in rules[1:]:
                if item.symbol() is not None:
                    item.symbol().setDataDefinedProperty.assert_not_called()
            renderer.reset_mock()
            renderer.styles.return_value = rules[1:]
            self.assertEqual(strokes.apply_light_national_background(renderer, source_style), 0)
            renderer.setStyles.assert_not_called()
        self.assertEqual(source_style, original)
