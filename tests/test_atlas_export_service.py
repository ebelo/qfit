"""Tests for AtlasExportService and AtlasExportResult."""
import unittest
from unittest.mock import MagicMock

from tests import _path  # noqa: F401

from qfit.atlas.export_service import (
    AtlasExportPlan,
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
    def test_delegates_prerequisite_check_to_runtime(self):
        runtime = MagicMock()
        runtime.check_pdf_export_prerequisites.return_value = "missing pypdf"
        service = AtlasExportService(MagicMock(), runtime=runtime)

        error = service.check_pdf_export_prerequisites()

        self.assertEqual(error, "missing pypdf")
        runtime.check_pdf_export_prerequisites.assert_called_once_with()


# ---------------------------------------------------------------------------
# AtlasExportService.build_task
# ---------------------------------------------------------------------------


class BuildTaskTests(unittest.TestCase):
    def setUp(self):
        self.layer_manager = MagicMock()
        self.runtime = MagicMock()
        self.service = AtlasExportService(self.layer_manager, runtime=self.runtime)

    def test_build_task_delegates_request_and_gateway_to_runtime(self):
        request = GenerateAtlasPdfRequest(
            atlas_layer=MagicMock(),
            output_path="/out.pdf",
            atlas_title="Atlas",
            atlas_subtitle="Spring rides",
            on_finished=MagicMock(),
            pre_export_tile_mode="Raster",
            preset_name="Dark",
            access_token="tok",
            style_owner="mapbox",
            style_id="dark-v11",
            background_enabled=True,
        )

        self.service.build_task(request)

        self.runtime.build_task.assert_called_once_with(request, layer_gateway=self.layer_manager)

    def test_build_task_constructs_request_from_legacy_kwargs_before_delegating(self):
        self.service.build_task(
            atlas_layer=MagicMock(),
            output_path="/out.pdf",
            atlas_title="Atlas",
            atlas_subtitle="Subset",
            on_finished=MagicMock(),
            pre_export_tile_mode="Vector",
            preset_name="Light",
            access_token="",
            style_owner="",
            style_id="",
            background_enabled=False,
        )

        request = self.runtime.build_task.call_args.args[0]
        self.assertIsInstance(request, GenerateAtlasPdfRequest)
        self.assertEqual(request.atlas_title, "Atlas")
        self.assertEqual(request.atlas_subtitle, "Subset")
        self.assertFalse(request.background_enabled)
        self.assertEqual(request.pre_export_tile_mode, "Vector")

    def test_build_task_preserves_profile_plot_style_in_delegated_request(self):
        style = object()

        self.service.build_task(
            atlas_layer=MagicMock(),
            output_path="/out.pdf",
            atlas_title="Atlas",
            atlas_subtitle="Subset",
            on_finished=MagicMock(),
            pre_export_tile_mode="Vector",
            preset_name="Light",
            access_token="",
            style_owner="",
            style_id="",
            background_enabled=False,
            profile_plot_style=style,
        )

        request = self.runtime.build_task.call_args.args[0]
        self.assertIs(request.profile_plot_style, style)


class AtlasExportRequestContractTests(unittest.TestCase):
    def test_build_plan_returns_dataclass(self):
        plan = AtlasExportService.build_plan(
            output_path="/tmp/atlas.pdf",
            atlas_title="Atlas",
            atlas_subtitle="Spring",
            pre_export_tile_mode="Raster",
            preset_name="Dark",
            access_token="tok",
            style_owner="mapbox",
            style_id="dark-v11",
            background_enabled=True,
        )

        self.assertIsInstance(plan, AtlasExportPlan)
        self.assertEqual(plan.output_path, "/tmp/atlas.pdf")
        self.assertEqual(plan.atlas_title, "Atlas")
        self.assertEqual(plan.atlas_subtitle, "Spring")
        self.assertTrue(plan.background_enabled)

    def test_build_request_returns_dataclass(self):
        request = AtlasExportService.build_request(
            atlas_layer=MagicMock(),
            output_path="/tmp/atlas.pdf",
            atlas_title="Atlas",
            atlas_subtitle="Spring",
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
        self.assertEqual(request.atlas_title, "Atlas")
        self.assertEqual(request.atlas_subtitle, "Spring")
        self.assertTrue(request.background_enabled)

    def test_build_request_preserves_profile_plot_style(self):
        style = object()

        request = AtlasExportService.build_request(
            atlas_layer=MagicMock(),
            output_path="/tmp/atlas.pdf",
            atlas_title="Atlas",
            atlas_subtitle="Spring",
            on_finished=MagicMock(),
            pre_export_tile_mode="Raster",
            preset_name="Dark",
            access_token="tok",
            style_owner="mapbox",
            style_id="dark-v11",
            background_enabled=True,
            profile_plot_style=style,
        )

        self.assertIs(request.profile_plot_style, style)

    def test_build_request_from_plan_returns_dataclass(self):
        plan = AtlasExportService.build_plan(
            output_path="/tmp/atlas.pdf",
            atlas_title="Atlas",
            atlas_subtitle="Spring",
            pre_export_tile_mode="Raster",
            preset_name="Dark",
            access_token="tok",
            style_owner="mapbox",
            style_id="dark-v11",
            background_enabled=True,
        )

        request = AtlasExportService.build_request_from_plan(
            plan=plan,
            atlas_layer=MagicMock(),
            on_finished=MagicMock(),
        )

        self.assertIsInstance(request, GenerateAtlasPdfRequest)
        self.assertEqual(request.output_path, "/tmp/atlas.pdf")
        self.assertEqual(request.atlas_title, "Atlas")
        self.assertEqual(request.atlas_subtitle, "Spring")
        self.assertTrue(request.background_enabled)
