import sys
import unittest
from unittest.mock import MagicMock, patch

from tests import _path  # noqa: F401

from qfit.atlas.export_service import GenerateAtlasPdfRequest
from qfit.atlas.qgis_export_runtime import QgisAtlasExportRuntime


def _make_atlas_task_stub():
    stub_module = MagicMock()
    mock_task = MagicMock()
    stub_module.AtlasExportTask = mock_task
    return stub_module, mock_task


class QgisAtlasExportRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.runtime = QgisAtlasExportRuntime()

    def test_returns_none_when_pdf_writer_is_available(self):
        stub_module, _mock_task = _make_atlas_task_stub()
        stub_module._load_pdf_writer = MagicMock(return_value=object())

        with patch.dict(sys.modules, {"qfit.atlas.export_task": stub_module}):
            self.assertIsNone(self.runtime.check_pdf_export_prerequisites())

    def test_returns_user_facing_error_when_pdf_writer_is_missing(self):
        stub_module, _mock_task = _make_atlas_task_stub()
        stub_module._load_pdf_writer = MagicMock(side_effect=ImportError("missing pypdf"))

        with patch.dict(sys.modules, {"qfit.atlas.export_task": stub_module}):
            error = self.runtime.check_pdf_export_prerequisites()

        self.assertIsNotNone(error)
        self.assertIn("pypdf", error)
        self.assertIn("Reinstall/update the plugin", error)

    def test_build_task_constructs_atlas_export_task_with_correct_params(self):
        stub_module, mock_task = _make_atlas_task_stub()
        on_finished = MagicMock()
        atlas_layer = MagicMock()
        layer_gateway = MagicMock()
        request = GenerateAtlasPdfRequest(
            atlas_layer=atlas_layer,
            output_path="/out.pdf",
            on_finished=on_finished,
            pre_export_tile_mode="Raster",
            preset_name="Dark",
            access_token="tok",
            style_owner="mapbox",
            style_id="dark-v11",
            background_enabled=True,
            profile_plot_style="style-override",
        )

        with patch.dict(sys.modules, {"qfit.atlas.export_task": stub_module}):
            self.runtime.build_task(request, layer_gateway=layer_gateway)

        mock_task.assert_called_once_with(
            atlas_layer=atlas_layer,
            output_path="/out.pdf",
            on_finished=on_finished,
            restore_tile_mode="Raster",
            layer_manager=layer_gateway,
            preset_name="Dark",
            access_token="tok",
            style_owner="mapbox",
            style_id="dark-v11",
            background_enabled=True,
            profile_plot_style="style-override",
        )


if __name__ == "__main__":
    unittest.main()
