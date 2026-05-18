import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from tests import _path  # noqa: F401

from qfit.validation.mapbox_outdoors_label_settings import (
    build_label_settings_paths,
    build_run_directory,
    build_summary_markdown,
    label_settings_record,
    load_style_definition,
    resolve_mapbox_token,
    write_report,
)


class FakeProperties:
    def __init__(self, keys):
        self._keys = keys

    def propertyKeys(self):
        return self._keys


class FakeStyle:
    def __init__(self, *, style_name, layer_name):
        self._style_name = style_name
        self._layer_name = layer_name

    def styleName(self):
        return self._style_name

    def layerName(self):
        return self._layer_name


class FakeSettings:
    fieldName = '"name"'
    isExpression = True
    priority = 7
    placement = SimpleNamespace(name="Line")
    repeatDistance = 66.1458333333
    repeatDistanceUnit = SimpleNamespace(name="Millimeters")
    displayAll = False
    obstacle = True

    def dataDefinedProperties(self):
        return FakeProperties([87, 50])


class MapboxOutdoorsLabelSettingsTests(unittest.TestCase):
    def test_resolve_mapbox_token_prefers_argument_then_environment(self):
        self.assertEqual(
            resolve_mapbox_token(
                provided_token="arg-token",
                environ={"MAPBOX_ACCESS_TOKEN": "env-token", "QFIT_MAPBOX_ACCESS_TOKEN": "qfit-token"},
            ),
            "arg-token",
        )
        self.assertEqual(
            resolve_mapbox_token(provided_token=None, environ={"MAPBOX_ACCESS_TOKEN": "env-token"}),
            "env-token",
        )
        self.assertEqual(
            resolve_mapbox_token(provided_token=None, environ={"QFIT_MAPBOX_ACCESS_TOKEN": "qfit-token"}),
            "qfit-token",
        )
        self.assertIsNone(resolve_mapbox_token(provided_token=None, environ={}))

    def test_build_run_directory_uses_style_slug_and_timestamp(self):
        run_dir = build_run_directory(
            output_root=Path("/tmp/qfit-labels"),
            style_owner="mapbox",
            style_id="outdoors-v12",
            now=dt.datetime(2026, 5, 18, 8, 22, tzinfo=dt.timezone.utc),
        )

        self.assertEqual(run_dir, Path("/tmp/qfit-labels/mapbox-outdoors-v12/20260518T082200Z"))

    def test_build_label_settings_paths_are_predictable(self):
        paths = build_label_settings_paths(Path("/tmp/run"))

        self.assertEqual(paths.json_path, Path("/tmp/run/label-settings.json"))
        self.assertEqual(paths.summary_path, Path("/tmp/run/summary.md"))

    def test_load_style_definition_requires_json_object(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            good_path = Path(tmpdir) / "style.json"
            good_path.write_text(json.dumps({"version": 8, "layers": []}), encoding="utf-8")
            self.assertEqual(load_style_definition(good_path), {"version": 8, "layers": []})

            bad_path = Path(tmpdir) / "bad.json"
            bad_path.write_text("[]", encoding="utf-8")
            with self.assertRaises(ValueError):
                load_style_definition(bad_path)

    def test_label_settings_record_captures_qgis_fields_and_base_layer(self):
        record = label_settings_record(
            FakeStyle(style_name="road-label-z15-plus", layer_name="road"),
            FakeSettings(),
        )

        self.assertEqual(record["style_name"], "road-label-z15-plus")
        self.assertEqual(record["base_style_layer_id"], "road-label")
        self.assertEqual(record["source_layer"], "road")
        self.assertEqual(record["field_name"], '"name"')
        self.assertTrue(record["is_expression"])
        self.assertEqual(record["priority"], 7)
        self.assertEqual(record["placement"], "Line")
        self.assertAlmostEqual(record["repeat_distance"], 66.1458333333)
        self.assertEqual(record["repeat_distance_unit"], "Millimeters")
        self.assertEqual(record["data_defined_property_keys"], [50, 87])

    def test_summary_markdown_lists_label_settings(self):
        report = {
            "style_owner": "mapbox",
            "style_id": "outdoors-v12",
            "generated": "2026-05-18T08:22:00+00:00",
            "sprite_context_loaded": True,
            "sprite_definition_count": 440,
            "label_count": 1,
            "labels": [
                {
                    "base_style_layer_id": "contour-label",
                    "style_name": "contour-label",
                    "source_layer": "contour",
                    "field_name": "concat(\"ele\", ' m')",
                    "is_expression": True,
                    "priority": 3,
                    "placement": "Line",
                    "repeat_distance": 0.0,
                    "repeat_distance_unit": "Millimeters",
                    "display_all": False,
                    "obstacle": True,
                    "data_defined_property_keys": [],
                }
            ],
        }

        markdown = build_summary_markdown(report)

        self.assertIn("# Mapbox Outdoors QGIS label settings — mapbox/outdoors-v12", markdown)
        self.assertIn("Converted label styles: 1", markdown)
        self.assertIn("Sprite context loaded: yes", markdown)
        self.assertIn("contour-label", markdown)
        self.assertIn("concat", markdown)
        self.assertIn("Millimeters", markdown)

    def test_write_report_writes_json_and_summary(self):
        report = {
            "style_owner": "mapbox",
            "style_id": "outdoors-v12",
            "generated": "2026-05-18T08:22:00+00:00",
            "label_count": 0,
            "labels": [],
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = build_label_settings_paths(Path(tmpdir) / "run")

            write_report(report, paths)

            self.assertEqual(json.loads(paths.json_path.read_text(encoding="utf-8"))["label_count"], 0)
            self.assertIn("Converted label styles: 0", paths.summary_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
