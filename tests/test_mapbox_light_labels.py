"""Light duplicate-label adaptation is exact-style scoped and backwards safe."""
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from tests import _path  # noqa: F401
from qfit.visualization.infrastructure import mapbox_light_labels as labels


def source(**layout):
    return {"owner": "mapbox", "id": "light-v11", "layers": [{
        "id": "road-label-simple", "source-layer": "road",
        "layout": {"symbol-placement": "line", **layout},
    }]}


class LightRoadDuplicateTests(unittest.TestCase):
    def test_spacing_uses_source_default_and_rejects_unsupported_values(self):
        self.assertEqual(labels._road_symbol_spacing(source()), 250)
        self.assertEqual(labels._road_symbol_spacing(source(**{"symbol-spacing": 300})), 300)
        for value in (True, "250", [], ["get", "spacing"], -1, 0, float("nan"), float("inf")):
            with self.subTest(value=value):
                self.assertIsNone(labels._road_symbol_spacing(source(**{"symbol-spacing": value})))
        for style in ({}, {"owner": "custom", "id": "light-v11"},
                      {"owner": "mapbox", "id": "outdoors-v12"},
                      {"owner": "mapbox", "id": "light-v10"}):
            self.assertIsNone(labels._road_symbol_spacing(style))
        style = source()
        style["layers"] = [None, {"id": "unrelated"}]
        self.assertIsNone(labels._road_symbol_spacing(style))
        style = source()
        style["layers"][0]["source-layer"] = "place_label"
        self.assertIsNone(labels._road_symbol_spacing(style))
        self.assertIsNone(labels._road_symbol_spacing(source(**{"symbol-placement": "point"})))

    def test_unrelated_styles_and_old_qgis_remain_untouched(self):
        labeling = MagicMock()
        self.assertEqual(labels.apply_light_road_duplicate_spacing(labeling, {}), 0)
        with patch.dict(sys.modules, {"qgis.core": SimpleNamespace(Qgis=object, QgsLabelThinningSettings=object)}):
            self.assertEqual(labels.apply_light_road_duplicate_spacing(labeling, source()), 0)
        with patch.dict(sys.modules, {"qgis.core": SimpleNamespace(Qgis=object)}):
            self.assertEqual(labels.apply_light_road_duplicate_spacing(labeling, source()), 0)
        labeling.styles.assert_not_called()
        labeling.setStyles.assert_not_called()

    def test_changes_only_owned_rules_and_preserves_explicit_thinning(self):
        rules = []
        for name in ("road-label-simple", "road-label-simple-z12-to-z15", "road-label", "road-label-simple-custom", "poi-label"):
            label = MagicMock()
            label.styleName.return_value = name
            label.labelSettings().thinningSettings().allowDuplicateRemoval.return_value = False
            rules.append(label)
        explicit = MagicMock()
        explicit.styleName.return_value = "road-label-simple"
        explicit.labelSettings().thinningSettings().allowDuplicateRemoval.return_value = True
        rules.append(explicit)
        labeling = MagicMock()
        labeling.styles.return_value = rules
        qgis = SimpleNamespace(RenderUnit=SimpleNamespace(Millimeters=9))
        thinning_class = SimpleNamespace(setAllowDuplicateRemoval=lambda _: None)
        with patch.dict(sys.modules, {"qgis.core": SimpleNamespace(Qgis=qgis, QgsLabelThinningSettings=thinning_class)}):
            self.assertEqual(labels.apply_light_road_duplicate_spacing(labeling, source()), 2)
            for label in rules[:2]:
                settings = label.labelSettings()
                thinning = settings.thinningSettings()
                thinning.setAllowDuplicateRemoval.assert_called_once_with(True)
                thinning.setMinimumDistanceToDuplicate.assert_called_once_with(250 * 25.4 / 96)
                thinning.setMinimumDistanceToDuplicateUnit.assert_called_once_with(9)
                settings.setThinningSettings.assert_called_once_with(thinning)
                label.setLabelSettings.assert_called_once_with(settings)
            for label in rules[2:]:
                label.setLabelSettings.assert_not_called()
            labeling.setStyles.assert_called_once_with(rules)
            labeling.reset_mock()
            labeling.styles.return_value = rules[2:]
            self.assertEqual(labels.apply_light_road_duplicate_spacing(labeling, source()), 0)
            labeling.setStyles.assert_not_called()


class LightNameFallbackTests(unittest.TestCase):
    @staticmethod
    def source_style():
        import json
        from pathlib import Path
        return json.loads((Path(__file__).parent / "fixtures/mapbox/light-place-name-source.json").read_text())

    @staticmethod
    def rule(name="country-label", layer="place_label", field='"name"'):
        rule = MagicMock()
        rule.styleName.return_value = name
        rule.layerName.return_value = layer
        rule.labelSettings().fieldName = field
        rule.labelSettings().isExpression = True
        return rule

    def test_restores_only_exact_source_owned_unsplit_rules(self):
        import copy
        source_style = self.source_style()
        before = copy.deepcopy(source_style)
        owned = [self.rule(), self.rule("settlement-major-label")]
        literal_field = self.rule()
        literal_field.labelSettings().isExpression = False
        untouched = [literal_field, self.rule("country-label-name-en"), self.rule("country-label-custom"),
                     self.rule("poi-label"), self.rule(layer="road"),
                     self.rule(field='"custom_name"')]
        labeling = MagicMock()
        labeling.styles.return_value = owned + untouched
        self.assertEqual(labels.apply_light_name_fallback(labeling, source_style), 2)
        for rule in owned:
            settings = rule.labelSettings()
            self.assertEqual(settings.fieldName,
                             'coalesce("name_en", "name")' )
            self.assertTrue(settings.isExpression)
            rule.setLabelSettings.assert_called_once_with(settings)
        for rule in untouched:
            rule.setLabelSettings.assert_not_called()
        self.assertEqual(source_style, before)
        labeling.setStyles.assert_called_once_with(owned + untouched)

    def test_other_presets_and_changed_source_contract_remain_untouched(self):
        import copy
        source_style = self.source_style()
        variants = [{}, {**source_style, "owner": "custom"},
                    {**source_style, "id": "outdoors-v12"}, {**source_style, "id": "light-v10"},
                    {**source_style, "layers": [None, {"id": "unrelated"}]}]
        for field, value in (("type", "line"), ("source-layer", "road"), ("layout", {})):
            changed = copy.deepcopy(source_style)
            for layer in changed["layers"]:
                layer[field] = value
            variants.append(changed)
        changed = copy.deepcopy(source_style)
        for layer in changed["layers"]:
            layer["layout"]["text-field"] = ["coalesce", ["get", "name_fr"], ["get", "name"]]
        variants.append(changed)
        for style in variants:
            with self.subTest(style=style):
                labeling = MagicMock()
                self.assertEqual(labels.apply_light_name_fallback(labeling, style), 0)
                labeling.setStyles.assert_not_called()

    def test_no_owned_converted_rule_is_a_noop(self):
        labeling = MagicMock()
        labeling.styles.return_value = [self.rule("country-label-name-en")]
        self.assertEqual(labels.apply_light_name_fallback(labeling, self.source_style()), 0)
        labeling.setStyles.assert_not_called()


class LightMajorRankTests(unittest.TestCase):
    def test_only_recorded_source_contract_applies(self):
        import copy
        style = LightNameFallbackTests.source_style()
        self.assertTrue(labels._has_light_major_rank_contract(style))
        variants = [{}, {**style, "owner": "custom"}, {**style, "id": "outdoors-v12"},
                    {**style, "layers": [None, {"id": "other"}]}]
        for key, value in (("type", "line"), ("source-layer", "road"),
                           ("minzoom", 3), ("maxzoom", 16), ("filter", ["has", "name"])):
            changed = copy.deepcopy(style)
            next(x for x in changed["layers"] if x["id"] == "settlement-major-label")[key] = value
            variants.append(changed)
        for variant in variants:
            with self.subTest(variant=variant):
                labeling = MagicMock()
                self.assertEqual(labels.apply_light_major_rank_filter(labeling, variant), 0)
                labeling.styles.assert_not_called()

    def test_native_filter_preserves_settings_and_declines_changed_rules(self):
        from dataclasses import dataclass, field

        @dataclass
        class Rule:
            name: str = "settlement-major-label"
            layer: str = "place_label"
            minimum: int = 2
            maximum: int = 14
            expression: str = labels._MAJOR_NATIVE_FILTER
            settings: dict = field(default_factory=lambda: {"field": 'coalesce("name_en", "name")', "priority": 8})

            def styleName(self): return self.name
            def layerName(self): return self.layer
            def minZoomLevel(self): return self.minimum
            def maxZoomLevel(self): return self.maximum
            def filterExpression(self): return self.expression
            def setFilterExpression(self, value): self.expression = value

        original = Rule()
        untouched = [Rule(name="other"), Rule(layer="road"), Rule(minimum=3),
                     Rule(maximum=13), Rule(expression='"rank" < 15')]
        labeling = MagicMock()
        labeling.styles.return_value = [original, *untouched]
        self.assertEqual(labels.apply_light_major_rank_filter(labeling, LightNameFallbackTests.source_style()), 1)
        labeling.setStyles.assert_called_once_with([original, *untouched])
        self.assertEqual((original.minimum, original.maximum), (2, 14))
        self.assertEqual(original.settings, Rule().settings)
        self.assertIn('@vector_tile_zoom >= 13 THEN "symbolrank" >= 11', original.expression)
        self.assertIn('@vector_tile_zoom >= 14 THEN "symbolrank" >= 15', original.expression)
        self.assertEqual(original.expression.replace(labels._MAJOR_DYNAMIC_RANK, labels._MAJOR_NATIVE_RANK),
                         labels._MAJOR_NATIVE_FILTER)
        labeling.reset_mock()
        self.assertEqual(labels.apply_light_major_rank_filter(labeling, LightNameFallbackTests.source_style()), 0)
        labeling.setStyles.assert_not_called()
