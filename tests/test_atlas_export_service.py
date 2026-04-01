"""Tests for AtlasExportService and AtlasExportResult.

atlas_export_service.build_task uses a lazy import of atlas.export_task (which
requires QGIS bindings), so build_task tests patch qfit.atlas.export_task via
patch.dict to avoid polluting sys.modules for the full test run.
"""
import sys
import unittest
from unittest.mock import MagicMock, patch

from tests import _path  # noqa: F401

from qfit.atlas.export_service import (
    AtlasExportResult,
    AtlasExportService,
    GenerateAtlasPdfRequest,
)


# ---------------------------------------------------------------------------
# AtlasExportResult – status property tests
# ---------------------------------------------------------------------------


class AtlasExportResultCancelledTests(unittest.TestCase):
    def setUp(self):
        self.result = AtlasExportResult(cancelled=True)

    def test_pdf_status_says_cancelled(self):
        self.assertEqual(self.result.pdf_status, "Atlas PDF export cancelled.")

    def test_main_status_says_cancelled(self):
        self.assertEqual(self.result.main_status, "Atlas PDF export cancelled.")


class AtlasExportResultErrorTests(unittest.TestCase):
    def setUp(self):
        self.result = AtlasExportResult(error="disk full")

    def test_pdf_status_contains_error(self):
        self.assertIn("disk full", self.result.pdf_status)
        self.assertIn("failed", self.result.pdf_status.lower())

    def test_main_status_says_failed(self):
        self.assertIn("failed", self.result.main_status.lower())
        self.assertNotIn("disk full", self.result.main_status)


class AtlasExportResultSuccessTests(unittest.TestCase):
    def setUp(self):
        self.result = AtlasExportResult(
            output_path="/tmp/atlas.pdf",
            page_count=12,
        )

    def test_pdf_status_contains_page_count_and_path(self):
        self.assertIn("12", self.result.pdf_status)
        self.assertIn("/tmp/atlas.pdf", self.result.pdf_status)

    def test_main_status_matches_pdf_status_on_success(self):
        self.assertEqual(self.result.main_status, self.result.pdf_status)


class AtlasExportResultDefaultsTests(unittest.TestCase):
    def test_default_values(self):
        result = AtlasExportResult()
        self.assertIsNone(result.output_path)
        self.assertEqual(result.page_count, 0)
        self.assertIsNone(result.error)
        self.assertFalse(result.cancelled)


# ---------------------------------------------------------------------------
# AtlasExportService.build_result
# ---------------------------------------------------------------------------


class BuildResultTests(unittest.TestCase):
    def test_wraps_cancelled(self):
        result = AtlasExportService.build_result(None, None, True, 0)
        self.assertTrue(result.cancelled)

    def test_wraps_error(self):
        result = AtlasExportService.build_result(None, "timeout", False, 0)
        self.assertEqual(result.error, "timeout")

    def test_wraps_success(self):
        result = AtlasExportService.build_result("/out.pdf", None, False, 5)
        self.assertEqual(result.output_path, "/out.pdf")
        self.assertEqual(result.page_count, 5)
        self.assertIsNone(result.error)
        self.assertFalse(result.cancelled)


# ---------------------------------------------------------------------------
# AtlasExportService.prepare_basemap_for_export
# ---------------------------------------------------------------------------


class PrepareBasemapTests(unittest.TestCase):
    def setUp(self):
        self.layer_manager = MagicMock()
        self.service = AtlasExportService(self.layer_manager)

    def _call(self, pre_export_tile_mode="Raster", background_enabled=True):
        self.service.prepare_basemap_for_export(
            pre_export_tile_mode=pre_export_tile_mode,
            background_enabled=background_enabled,
            preset_name="Dark",
            access_token="tok",
            style_owner="mapbox",
            style_id="dark-v11",
        )

    def test_switches_to_vector_when_raster_and_background_enabled(self):
        self._call(pre_export_tile_mode="Raster", background_enabled=True)

        self.layer_manager.ensure_background_layer.assert_called_once()
        kwargs = self.layer_manager.ensure_background_layer.call_args.kwargs
        self.assertEqual(kwargs["tile_mode"], "Vector")
        self.assertTrue(kwargs["enabled"])

    def test_no_op_when_tile_mode_is_already_vector(self):
        self._call(pre_export_tile_mode="Vector", background_enabled=True)

        self.layer_manager.ensure_background_layer.assert_not_called()

    def test_no_op_when_background_disabled(self):
        self._call(pre_export_tile_mode="Raster", background_enabled=False)

        self.layer_manager.ensure_background_layer.assert_not_called()

    def test_passes_correct_params_to_ensure_background_layer(self):
        self.service.prepare_basemap_for_export(
            pre_export_tile_mode="Raster",
            background_enabled=True,
            preset_name="Satellite",
            access_token="mytoken",
            style_owner="acme",
            style_id="streets-v12",
        )

        self.layer_manager.ensure_background_layer.assert_called_once_with(
            enabled=True,
            preset_name="Satellite",
            access_token="mytoken",
            style_owner="acme",
            style_id="streets-v12",
            tile_mode="Vector",
        )

    def test_silently_continues_when_ensure_background_layer_raises(self):
        self.layer_manager.ensure_background_layer.side_effect = RuntimeError("tiles unavailable")

        # Should not propagate the error
        self._call(pre_export_tile_mode="Raster", background_enabled=True)


# ---------------------------------------------------------------------------
# AtlasExportService.check_pdf_export_prerequisites
# ---------------------------------------------------------------------------


class CheckPdfExportPrerequisitesTests(unittest.TestCase):
    def test_returns_none_when_pdf_writer_is_available(self):
        stub_module, _mock_task = _make_atlas_task_stub()
        stub_module._load_pdf_writer = MagicMock(return_value=object())

        with patch.dict(sys.modules, {"qfit.atlas.export_task": stub_module}):
            self.assertIsNone(AtlasExportService.check_pdf_export_prerequisites())

    def test_returns_user_facing_error_when_pdf_writer_is_missing(self):
        stub_module, _mock_task = _make_atlas_task_stub()
        stub_module._load_pdf_writer = MagicMock(side_effect=ImportError("missing pypdf"))

        with patch.dict(sys.modules, {"qfit.atlas.export_task": stub_module}):
            error = AtlasExportService.check_pdf_export_prerequisites()

        self.assertIsNotNone(error)
        self.assertIn("pypdf", error)
        self.assertIn("Reinstall/update the plugin", error)


# ---------------------------------------------------------------------------
# AtlasExportService.build_task
# ---------------------------------------------------------------------------


def _make_atlas_task_stub():
    """Return a (stub_module, MockTask) pair for patching qfit.atlas.export_task."""
    stub_module = MagicMock()
    MockTask = MagicMock()
    stub_module.AtlasExportTask = MockTask
    return stub_module, MockTask


class BuildTaskTests(unittest.TestCase):
    def setUp(self):
        self.layer_manager = MagicMock()
        self.service = AtlasExportService(self.layer_manager)

    def test_constructs_atlas_export_task_with_correct_params(self):
        stub_module, MockTask = _make_atlas_task_stub()
        on_finished = MagicMock()
        atlas_layer = MagicMock()

        with patch.dict(sys.modules, {"qfit.atlas.export_task": stub_module}):
            self.service.build_task(
                atlas_layer=atlas_layer,
                output_path="/out.pdf",
                on_finished=on_finished,
                pre_export_tile_mode="Raster",
                preset_name="Dark",
                access_token="tok",
                style_owner="mapbox",
                style_id="dark-v11",
                background_enabled=True,
            )

        MockTask.assert_called_once_with(
            atlas_layer=atlas_layer,
            output_path="/out.pdf",
            on_finished=on_finished,
            restore_tile_mode="Raster",
            layer_manager=self.layer_manager,
            preset_name="Dark",
            access_token="tok",
            style_owner="mapbox",
            style_id="dark-v11",
            background_enabled=True,
        )

    def test_passes_background_enabled_false(self):
        stub_module, MockTask = _make_atlas_task_stub()

        with patch.dict(sys.modules, {"qfit.atlas.export_task": stub_module}):
            self.service.build_task(
                atlas_layer=MagicMock(),
                output_path="/out.pdf",
                on_finished=MagicMock(),
                pre_export_tile_mode="Vector",
                preset_name="Light",
                access_token="",
                style_owner="",
                style_id="",
                background_enabled=False,
            )

        kwargs = MockTask.call_args.kwargs
        self.assertFalse(kwargs["background_enabled"])
        self.assertEqual(kwargs["restore_tile_mode"], "Vector")


class AtlasExportRequestContractTests(unittest.TestCase):
    def test_build_request_returns_dataclass(self):
        request = AtlasExportService.build_request(
            atlas_layer=MagicMock(),
            output_path="/tmp/atlas.pdf",
            on_finished=MagicMock(),
            pre_export_tile_mode="Raster",
            preset_name="Dark",
            access_token="tok",
            style_owner="mapbox",
            style_id="dark-v11",
            background_enabled=True,
        )

        self.assertIsInstance(request, GenerateAtlasPdfRequest)
        self.assertEqual(request.output_path, "/tmp/atlas.pdf")
        self.assertTrue(request.background_enabled)
