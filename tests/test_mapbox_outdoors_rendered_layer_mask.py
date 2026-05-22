import datetime as dt
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests import _path  # noqa: F401

from qfit.validation.mapbox_outdoors_rendered_layer_mask import (
    RenderedLayerMaskConfig,
    RenderedLayerMaskVariant,
    apply_transparent_layer_mask,
    build_qgis_render_child_script,
    build_rendered_layer_mask_report,
    image_changed_bbox,
    image_delta_metrics,
    parse_crop_box,
    parse_variant_spec,
    render_markdown_summary,
    render_qgis_vector_in_subprocess,
)
from qfit.validation.mapbox_outdoors_comparison import MapboxComparisonCamera


STYLE = {
    "version": 8,
    "sources": {
        "composite": {
            "type": "vector",
            "url": "mapbox://mapbox.mapbox-streets-v8",
        }
    },
    "layers": [
        {"id": "background", "type": "background", "paint": {"background-color": "#ffffff"}},
        {"id": "landuse-cemetery", "type": "fill", "paint": {"fill-color": "#c8dca8"}},
        {"id": "road-path", "type": "line", "paint": {"line-color": "#ff9900"}},
        {"id": "poi-label", "type": "symbol", "paint": {"text-color": "#333333"}},
    ],
}


class MapboxOutdoorsRenderedLayerMaskTests(unittest.TestCase):
    def test_parse_variant_spec_requires_named_layer_ids(self):
        variant = parse_variant_spec("cemetery=landuse-cemetery,landuse-z10-cemetery")

        self.assertEqual(variant.name, "cemetery")
        self.assertEqual(variant.layer_ids, ("landuse-cemetery", "landuse-z10-cemetery"))
        with self.assertRaises(Exception):
            parse_variant_spec("cemetery")
        with self.assertRaises(Exception):
            parse_variant_spec("cemetery=")

    def test_parse_crop_box_validates_non_empty_regions(self):
        self.assertEqual(parse_crop_box("1,2,5,8"), (1, 2, 5, 8))

        with self.assertRaises(Exception):
            parse_crop_box("1,2,1,8")
        with self.assertRaises(Exception):
            parse_crop_box("-1,2,5,8")

    def test_apply_transparent_layer_mask_sets_type_specific_opacity(self):
        masked, matched, missing = apply_transparent_layer_mask(
            STYLE,
            layer_ids=("landuse-cemetery", "road-path", "poi-label", "missing"),
        )

        self.assertEqual(matched, ["landuse-cemetery", "road-path", "poi-label"])
        self.assertEqual(missing, ["missing"])
        layers = {layer["id"]: layer for layer in masked["layers"]}
        self.assertEqual(layers["landuse-cemetery"]["paint"]["fill-opacity"], 0.0)
        self.assertEqual(layers["road-path"]["paint"]["line-opacity"], 0.0)
        self.assertEqual(layers["poi-label"]["paint"]["text-opacity"], 0.0)
        self.assertEqual(layers["poi-label"]["paint"]["icon-opacity"], 0.0)
        self.assertNotIn("fill-opacity", STYLE["layers"][1]["paint"])

    def test_image_delta_metrics_reports_signed_and_absolute_crop_movement(self):
        try:
            from PIL import Image
        except ImportError:  # pragma: no cover - local dependency guard
            self.skipTest("Pillow is not available")

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            reference_path = root / "reference.png"
            candidate_path = root / "candidate.png"
            Image.new("RGB", (2, 1), (10, 20, 30)).save(reference_path)
            Image.new("RGB", (2, 1), (10, 20, 30)).save(candidate_path)
            with Image.open(candidate_path) as candidate:
                candidate.putpixel((1, 0), (20, 10, 30))
                candidate.save(candidate_path)

            metrics = image_delta_metrics(
                reference_path=reference_path,
                candidate_path=candidate_path,
                crop_box=(1, 0, 2, 1),
            )

            self.assertEqual(metrics["pixel_count"], 1)
            self.assertEqual(metrics["changed_pixel_count"], 1)
            self.assertEqual(metrics["mean_delta_rgb"], [10.0, -10.0, 0.0])
            self.assertAlmostEqual(metrics["mean_absolute_channel_delta"], 20.0 / 3.0)
            self.assertAlmostEqual(metrics["mean_luminance_delta"], -5.026)
            self.assertEqual(
                image_changed_bbox(reference_path=reference_path, candidate_path=candidate_path),
                [1, 0, 2, 1],
            )

    def test_build_report_uses_existing_manifest_and_masks_variants(self):
        try:
            from PIL import Image
        except ImportError:  # pragma: no cover - local dependency guard
            self.skipTest("Pillow is not available")

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            baseline_dir = root / "baseline"
            baseline_dir.mkdir()
            browser_path = baseline_dir / "mapbox-gl-reference.png"
            qgis_path = baseline_dir / "qgis-vector-render.png"
            style_path = baseline_dir / "qgis-preprocessed-style.json"
            manifest_path = baseline_dir / "manifest.json"
            Image.new("RGB", (3, 1), (10, 20, 30)).save(browser_path)
            Image.new("RGB", (3, 1), (10, 20, 30)).save(qgis_path)
            style_path.write_text(json.dumps(STYLE), encoding="utf-8")
            manifest_path.write_text(
                json.dumps({
                    "camera": {
                        "name": "unit-camera",
                        "description": "Unit camera",
                        "longitude": 7.0,
                        "latitude": 46.0,
                        "zoom": 14.0,
                        "width": 3,
                        "height": 1,
                        "style_owner": "mapbox",
                        "style_id": "outdoors-v12",
                    },
                    "outputs": {
                        "browser_reference": str(browser_path),
                        "qgis_vector_render": str(qgis_path),
                        "qgis_preprocessed_style": str(style_path),
                    },
                    "metrics": {
                        "normalized_mean_absolute_channel_delta": 0.0,
                        "normalized_rms_channel_delta": 0.0,
                        "changed_pixel_ratio": 0.0,
                    },
                }),
                encoding="utf-8",
            )

            def fake_renderer(**kwargs):
                output_path = kwargs["output_path"]
                style_definition = kwargs["style_definition"]
                Image.new("RGB", (3, 1), (10, 20, 30)).save(output_path)
                layers = {layer["id"]: layer for layer in style_definition["layers"]}
                if layers["landuse-cemetery"]["paint"].get("fill-opacity") == 0.0:
                    with Image.open(output_path) as rendered:
                        rendered.putpixel((2, 0), (20, 20, 30))
                        rendered.save(output_path)

            def fake_diff_builder(*, reference_path, candidate_path, output_path):
                Image.new("RGB", (3, 1), (0, 0, 0)).save(output_path)
                return image_delta_metrics(reference_path=reference_path, candidate_path=candidate_path)

            report = build_rendered_layer_mask_report(
                RenderedLayerMaskConfig(
                    baseline_manifest=manifest_path,
                    output_root=root / "mask-output",
                    variants=(RenderedLayerMaskVariant("cemetery", ("landuse-cemetery",)),),
                    crop_boxes=((2, 0, 3, 1),),
                    token="test-token",
                    now=dt.datetime(2026, 5, 22, 7, 30, tzinfo=dt.timezone.utc),
                ),
                qgis_renderer=fake_renderer,
                diff_builder=fake_diff_builder,
            )

            control = report["variants"][0]
            variant = report["variants"][1]
            self.assertTrue(control["is_rerender_control"])
            self.assertEqual(control["name"], "qgis-rerender-control")
            self.assertTrue(variant["render_changed"])
            self.assertEqual(variant["matched_layer_ids"], ["landuse-cemetery"])
            self.assertEqual(variant["diff_bbox_vs_baseline_qgis"], [2, 0, 3, 1])
            self.assertEqual(variant["diff_bbox_vs_rerender_control_qgis"], [2, 0, 3, 1])
            self.assertEqual(
                variant["qgis_movement_vs_rerender_control_metrics"]["mean_absolute_channel_delta"],
                10.0 / 9.0,
            )
            self.assertEqual(
                variant["crop_delta_vs_baseline"][0]["mean_absolute_channel_delta"],
                10.0 / 3.0,
            )
            self.assertEqual(
                variant["crop_delta_vs_rerender_control"][0]["mean_absolute_channel_delta"],
                10.0 / 3.0,
            )
            summary_path = (
                root
                / "mask-output"
                / "comparison-camera"
                / "20260522T073000Z"
                / "summary.md"
            )
            self.assertTrue(summary_path.exists())
            self.assertIn("rendered-layer mask probe", summary_path.read_text(encoding="utf-8"))

    def test_markdown_summary_lists_render_moving_variants(self):
        markdown = render_markdown_summary({
            "generated": "2026-05-22T07:30:00+00:00",
            "camera": {"name": "unit-camera"},
            "inputs": {"baseline_manifest": "debug/manifest.json"},
            "baseline": {"metrics": {"normalized_mean_absolute_channel_delta": 0.1}},
            "crop_boxes": [[0, 0, 1, 1]],
            "variants": [
                {
                    "name": "moving",
                    "target_layer_ids": ["layer"],
                    "render_changed": True,
                    "metrics": {"normalized_mean_absolute_channel_delta": 0.2},
                    "metric_delta_vs_baseline": {
                        "normalized_mean_absolute_channel_delta": 0.1,
                    },
                    "crop_delta_vs_baseline": [{
                        "mean_absolute_channel_delta": 1.0,
                        "rms_channel_delta": 2.0,
                        "mean_luminance_delta": 3.0,
                    }],
                }
            ],
        })

        self.assertIn("`moving`", markdown)
        self.assertIn("Control-adjusted render-moving variants: `moving`.", markdown)

    def test_qgis_child_script_keeps_token_out_of_source(self):
        script = build_qgis_render_child_script()

        self.assertIn("render_qgis_vector", script)
        self.assertIn("MAPBOX_ACCESS_TOKEN", script)
        self.assertNotIn("test-token", script)

    def test_subprocess_renderer_passes_token_only_through_environment(self):
        captured = {}

        def fake_run(command, **kwargs):
            captured["command"] = command
            captured["env"] = kwargs["env"]
            captured["cwd"] = kwargs["cwd"]
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("qfit.validation.mapbox_outdoors_rendered_layer_mask.subprocess.run", fake_run):
                render_qgis_vector_in_subprocess(
                    camera=MapboxComparisonCamera(
                        name="unit-camera",
                        description="Unit camera",
                        longitude=7.0,
                        latitude=46.0,
                        zoom=14.0,
                        width=3,
                        height=1,
                    ),
                    token="test-token",
                    output_path=Path(tmpdir) / "render.png",
                    style_definition=STYLE,
                )
        self.assertEqual(captured["env"]["MAPBOX_ACCESS_TOKEN"], "test-token")
        self.assertNotIn("test-token", " ".join(str(part) for part in captured["command"]))
        self.assertTrue(str(captured["cwd"]).endswith("qfit"))


if __name__ == "__main__":
    unittest.main()
