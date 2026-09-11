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
