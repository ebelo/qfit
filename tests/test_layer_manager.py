import unittest
from unittest.mock import MagicMock

from tests import _path  # noqa: F401
from qfit.layer_manager import LayerManager


class LayerManagerTests(unittest.TestCase):
    def test_load_output_layers_switches_crs_without_preserving_old_extent(self):
        iface = MagicMock()
        manager = LayerManager(iface)

        activities = MagicMock()
        starts = MagicMock()
        points = MagicMock()
        atlas = MagicMock()
        manager._project_layer_loader.load_output_layers = MagicMock(
            return_value=(activities, starts, points, atlas)
        )
        manager._canvas_service.ensure_working_crs = MagicMock()
        manager._canvas_service.zoom_to_layers = MagicMock()
        manager._move_background_layers_to_bottom = MagicMock()

        result = manager.load_output_layers("/tmp/test.gpkg")

        manager._canvas_service.ensure_working_crs.assert_called_once_with(
            iface, preserve_extent=False
        )
        manager._project_layer_loader.load_output_layers.assert_called_once_with(
            "/tmp/test.gpkg"
        )
        manager._canvas_service.zoom_to_layers.assert_called_once_with(
            iface, [activities, starts, points, atlas]
        )
        self.assertEqual(result, (activities, starts, points, atlas))


if __name__ == "__main__":
    unittest.main()
