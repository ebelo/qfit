import unittest
from unittest.mock import MagicMock

from tests import _path  # noqa: F401

from qfit.atlas.export_controller import AtlasExportValidationError
from qfit.atlas.export_service import AtlasExportResult
from qfit.atlas.export_use_case import (
    AtlasExportUseCase,
    GenerateAtlasPdfCommand,
    PrepareAtlasPdfExportResult,
)


class AtlasExportUseCaseTests(unittest.TestCase):
    def setUp(self):
        self.controller = MagicMock(name="controller")
        self.service = MagicMock(name="service")
        self.use_case = AtlasExportUseCase(self.controller, self.service)

    def test_build_command_returns_dataclass(self):
        command = self.use_case.build_command(output_path="/tmp/atlas.pdf", background_enabled=True)

        self.assertIsInstance(command, GenerateAtlasPdfCommand)
        self.assertEqual(command.output_path, "/tmp/atlas.pdf")
        self.assertTrue(command.background_enabled)

    def test_prepare_export_returns_validation_error_when_layer_invalid(self):
        self.controller.validate_atlas_layer.side_effect = AtlasExportValidationError("missing layer")

        result = self.use_case.prepare_export(GenerateAtlasPdfCommand(atlas_layer=None))

        self.assertFalse(result.is_ready)
        self.assertEqual(result.error_title, "Atlas export error")
        self.assertEqual(result.error_message, "missing layer")
        self.service.check_pdf_export_prerequisites.assert_not_called()

    def test_prepare_export_returns_missing_output_path_error(self):
        self.controller.normalize_pdf_path.side_effect = AtlasExportValidationError("missing path")

        result = self.use_case.prepare_export(GenerateAtlasPdfCommand(atlas_layer=object(), output_path=""))

        self.assertFalse(result.is_ready)
        self.assertEqual(result.error_title, "Missing output path")
        self.assertEqual(result.error_message, "missing path")
        self.service.check_pdf_export_prerequisites.assert_not_called()

    def test_prepare_export_returns_prerequisite_error_with_statuses(self):
        self.controller.normalize_pdf_path.return_value = ("/tmp/atlas.pdf", True)
        self.service.check_pdf_export_prerequisites.return_value = "pypdf missing"

        result = self.use_case.prepare_export(
            GenerateAtlasPdfCommand(atlas_layer=object(), output_path="/tmp/atlas")
        )

        self.assertFalse(result.is_ready)
        self.assertEqual(result.output_path, "/tmp/atlas.pdf")
        self.assertTrue(result.path_changed)
        self.assertEqual(result.error_title, "Atlas PDF export unavailable")
        self.assertEqual(result.error_message, "pypdf missing")
        self.assertEqual(result.pdf_status, "Atlas PDF export unavailable.")
        self.assertEqual(result.main_status, "Atlas PDF export unavailable.")
        self.service.build_request.assert_not_called()

    def test_prepare_export_builds_request_on_success(self):
        request = object()
        self.controller.normalize_pdf_path.return_value = ("/tmp/atlas.pdf", True)
        self.service.check_pdf_export_prerequisites.return_value = None
        self.service.build_request.return_value = request

        command = GenerateAtlasPdfCommand(
            atlas_layer=object(),
            output_path="/tmp/atlas",
            on_finished=MagicMock(),
            pre_export_tile_mode="Raster",
            preset_name="Outdoor",
            access_token="tok",
            style_owner="mapbox",
            style_id="style",
            background_enabled=True,
            profile_plot_style="style-override",
        )
        result = self.use_case.prepare_export(command)

        self.assertTrue(result.is_ready)
        self.assertIs(result.request, request)
        self.assertEqual(result.output_path, "/tmp/atlas.pdf")
        self.assertTrue(result.path_changed)
        self.service.build_request.assert_called_once_with(
            atlas_layer=command.atlas_layer,
            output_path="/tmp/atlas.pdf",
            on_finished=command.on_finished,
            pre_export_tile_mode="Raster",
            preset_name="Outdoor",
            access_token="tok",
            style_owner="mapbox",
            style_id="style",
            background_enabled=True,
            profile_plot_style="style-override",
        )

    def test_start_export_prepares_basemap_and_builds_task(self):
        request = object()
        task = object()
        self.service.build_task.return_value = task
        prepared = PrepareAtlasPdfExportResult(request=request, output_path="/tmp/atlas.pdf")

        result = self.use_case.start_export(prepared)

        self.assertIs(result, task)
        self.service.prepare_basemap_for_export.assert_called_once_with(request)
        self.service.build_task.assert_called_once_with(request)

    def test_start_export_requires_prepared_request(self):
        with self.assertRaises(ValueError):
            self.use_case.start_export(PrepareAtlasPdfExportResult())

    def test_finish_export_delegates_to_service(self):
        final_result = AtlasExportResult(output_path="/tmp/atlas.pdf", page_count=2)
        self.service.build_result.return_value = final_result

        result = self.use_case.finish_export("/tmp/atlas.pdf", None, False, 2)

        self.assertIs(result, final_result)
        self.service.build_result.assert_called_once_with("/tmp/atlas.pdf", None, False, 2)


if __name__ == "__main__":
    unittest.main()
