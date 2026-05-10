import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests import _path  # noqa: F401

from qfit.validation.mapbox_outdoors_comparison import (
    CAMERAS,
    ComparisonConfig,
    DEFAULT_OUTPUT_ROOT,
    MapboxComparisonCamera,
    build_comparison_paths,
    build_mapbox_gl_html,
    build_parser,
    build_run_directory,
    camera_center_web_mercator,
    camera_extent_web_mercator,
    list_cameras,
    resolve_mapbox_token,
    run_comparison,
)


PNG_PLACEHOLDER = b"not-a-real-png-for-unit-tests"


class MapboxOutdoorsComparisonTests(unittest.TestCase):
    def test_default_camera_targets_mapbox_outdoors(self):
        camera = CAMERAS["valais-geneva-outdoors"]

        self.assertEqual(camera.style_owner, "mapbox")
        self.assertEqual(camera.style_id, "outdoors-v12")
        self.assertEqual(camera.style_url, "mapbox://styles/mapbox/outdoors-v12")
        self.assertGreater(camera.width, 0)
        self.assertGreater(camera.height, 0)

    def test_list_cameras_mentions_valais_geneva_camera(self):
        text = list_cameras()

        self.assertIn("valais-geneva-outdoors", text)
        self.assertIn("mapbox/outdoors-v12", text)

    def test_build_run_directory_uses_timestamped_debug_layout(self):
        run_dir = build_run_directory(
            output_root=Path("/tmp/qfit-mapbox"),
            camera_name="valais-geneva-outdoors",
            now=dt.datetime(2026, 5, 10, 19, 45, tzinfo=dt.timezone.utc),
        )

        self.assertEqual(run_dir, Path("/tmp/qfit-mapbox/valais-geneva-outdoors/20260510T194500Z"))

    def test_build_comparison_paths_are_predictable_png_outputs(self):
        paths = build_comparison_paths(run_dir=Path("/tmp/run"))

        self.assertEqual(paths.browser_png, Path("/tmp/run/mapbox-gl-reference.png"))
        self.assertEqual(paths.qgis_png, Path("/tmp/run/qgis-vector-render.png"))
        self.assertEqual(paths.diff_png, Path("/tmp/run/mapbox-gl-vs-qgis-diff.png"))
        self.assertEqual(paths.manifest_json, Path("/tmp/run/manifest.json"))

    def test_resolve_token_prefers_argument_then_environment(self):
        self.assertEqual(
            resolve_mapbox_token(provided_token="arg-token", environ={"MAPBOX_ACCESS_TOKEN": "env-token"}),
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
        with self.assertRaises(ValueError):
            resolve_mapbox_token(provided_token=None, environ={})

    def test_camera_extent_is_web_mercator_bounds_around_center(self):
        camera = MapboxComparisonCamera(
            name="small",
            description="Small test camera",
            longitude=7.0,
            latitude=46.0,
            zoom=8.0,
            width=512,
            height=512,
        )

        center_x, center_y = camera_center_web_mercator(camera)
        xmin, ymin, xmax, ymax = camera_extent_web_mercator(camera)

        self.assertAlmostEqual((xmin + xmax) / 2, center_x)
        self.assertAlmostEqual((ymin + ymax) / 2, center_y)
        self.assertGreater(xmax - xmin, 0)
        self.assertGreater(ymax - ymin, 0)

    def test_build_mapbox_html_uses_camera_style_without_logging_token(self):
        camera = CAMERAS["valais-geneva-outdoors"]
        html = build_mapbox_gl_html(camera=camera, token="pk.test-token")

        self.assertIn("mapbox://styles/mapbox/outdoors-v12", html)
        self.assertIn("qfitMapboxReady", html)
        self.assertIn("pk.test-token", html)

    def test_run_comparison_writes_manifest_without_token(self):
        def fake_browser_renderer(*, output_path, **_kwargs):
            output_path.write_bytes(PNG_PLACEHOLDER)

        def fake_qgis_renderer(*, output_path, **_kwargs):
            output_path.write_bytes(PNG_PLACEHOLDER)

        def fake_diff_builder(*, output_path, **_kwargs):
            output_path.write_bytes(PNG_PLACEHOLDER)

        with tempfile.TemporaryDirectory() as tmpdir:
            result = run_comparison(
                ComparisonConfig(
                    camera=CAMERAS["valais-geneva-outdoors"],
                    token="pk.secret-token",
                    output_root=Path(tmpdir),
                    now=dt.datetime(2026, 5, 10, 19, 45, tzinfo=dt.timezone.utc),
                ),
                browser_renderer=fake_browser_renderer,
                qgis_renderer=fake_qgis_renderer,
                diff_builder=fake_diff_builder,
            )

            manifest_text = result.paths.manifest_json.read_text(encoding="utf-8")
            manifest = json.loads(manifest_text)

        self.assertTrue(result.browser_captured)
        self.assertTrue(result.qgis_captured)
        self.assertTrue(result.diff_captured)
        self.assertNotIn("pk.secret-token", manifest_text)
        self.assertEqual(manifest["camera"]["name"], "valais-geneva-outdoors")
        self.assertEqual(manifest["style_url"], "mapbox://styles/mapbox/outdoors-v12")
        self.assertTrue(manifest["captured"]["browser_reference"])
        self.assertTrue(manifest["captured"]["qgis_vector_render"])
        self.assertTrue(manifest["captured"]["diff"])

    def test_run_comparison_skips_diff_when_one_capture_is_disabled(self):
        def fake_qgis_renderer(*, output_path, **_kwargs):
            output_path.write_bytes(PNG_PLACEHOLDER)

        diff_called = False

        def fake_diff_builder(**_kwargs):
            nonlocal diff_called
            diff_called = True

        with tempfile.TemporaryDirectory() as tmpdir:
            result = run_comparison(
                ComparisonConfig(
                    camera=CAMERAS["valais-geneva-outdoors"],
                    token="pk.secret-token",
                    output_root=Path(tmpdir),
                    browser=False,
                    qgis=True,
                    now=dt.datetime(2026, 5, 10, 19, 45, tzinfo=dt.timezone.utc),
                ),
                qgis_renderer=fake_qgis_renderer,
                diff_builder=fake_diff_builder,
            )

        self.assertFalse(result.browser_captured)
        self.assertTrue(result.qgis_captured)
        self.assertFalse(result.diff_captured)
        self.assertFalse(diff_called)

    def test_parser_accepts_manual_capture_controls(self):
        parser = build_parser()
        args = parser.parse_args([
            "valais-geneva-outdoors",
            "--mapbox-token",
            "pk.test",
            "--output-root",
            "/tmp/qfit-mapbox",
            "--skip-qgis",
            "--browser-timeout-ms",
            "5000",
        ])

        self.assertEqual(args.camera.name, "valais-geneva-outdoors")
        self.assertEqual(args.mapbox_token, "pk.test")
        self.assertEqual(args.output_root, "/tmp/qfit-mapbox")
        self.assertTrue(args.skip_qgis)
        self.assertEqual(args.browser_timeout_ms, 5000)

    def test_main_lists_cameras_without_requiring_token(self):
        with patch("builtins.print") as print_mock:
            from qfit.validation import mapbox_outdoors_comparison

            result = mapbox_outdoors_comparison.main(["--list-cameras"])

        self.assertEqual(result, 0)
        printed = "\n".join(str(call.args[0]) for call in print_mock.call_args_list)
        self.assertIn("valais-geneva-outdoors", printed)

    def test_default_output_root_stays_under_ignored_debug_directory(self):
        self.assertEqual(DEFAULT_OUTPUT_ROOT, Path(__file__).resolve().parents[1] / "debug" / "mapbox-outdoors-comparison")


if __name__ == "__main__":
    unittest.main()
