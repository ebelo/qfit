import unittest
from unittest.mock import MagicMock, patch

from tests import _path  # noqa: F401

try:
    from qfit.visualization.infrastructure import LayerManager
    _LAYER_MANAGER_IMPORT_ERROR = None
except ImportError as exc:  # pragma: no cover - depends on QGIS bindings in CI
    LayerManager = None
    _LAYER_MANAGER_IMPORT_ERROR = exc


@unittest.skipIf(LayerManager is None, f"LayerManager unavailable: {_LAYER_MANAGER_IMPORT_ERROR}")
class LayerManagerTests(unittest.TestCase):
    def test_load_output_layers_preserves_user_project_crs(self):
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

        project = MagicMock()
        project_crs = MagicMock()
        project_crs.isValid.return_value = True
        project.crs.return_value = project_crs
        canvas = iface.mapCanvas.return_value

        with patch("qfit.visualization.infrastructure.qgis_layer_gateway.QgsProject") as qgs_project:
            qgs_project.instance.return_value = project
            result = manager.load_output_layers("/tmp/test.gpkg")

        manager._canvas_service.ensure_working_crs.assert_not_called()
        manager._project_layer_loader.load_output_layers.assert_called_once_with(
            "/tmp/test.gpkg"
        )
        project.setCrs.assert_called_once_with(project_crs)
        canvas.setDestinationCrs.assert_called_once_with(project_crs)
        manager._canvas_service.zoom_to_layers.assert_called_once_with(
            iface, [activities, starts, points, atlas]
        )
        self.assertEqual(result, (activities, starts, points, atlas))

    def test_load_route_layers_preserves_user_project_crs(self):
        iface = MagicMock()
        manager = LayerManager(iface)

        routes = MagicMock()
        points = MagicMock()
        samples = MagicMock()
        manager._project_layer_loader.load_output_layers = MagicMock()
        manager._project_layer_loader.load_route_layers = MagicMock(
            return_value=(routes, points, samples)
        )
        manager._style_service.apply_style = MagicMock()
        manager._style_service.apply_route_style = MagicMock()
        manager._canvas_service.ensure_working_crs = MagicMock()
        manager._canvas_service.zoom_to_layers = MagicMock()
        manager._move_background_layers_to_bottom = MagicMock()

        project = MagicMock()
        project_crs = MagicMock()
        project_crs.isValid.return_value = True
        project.crs.return_value = project_crs
        canvas = iface.mapCanvas.return_value

        with patch("qfit.visualization.infrastructure.qgis_layer_gateway.QgsProject") as qgs_project:
            qgs_project.instance.return_value = project
            result = manager.load_route_layers("/tmp/test.gpkg")

        manager._canvas_service.ensure_working_crs.assert_not_called()
        manager._project_layer_loader.load_route_layers.assert_called_once_with(
            "/tmp/test.gpkg"
        )
        project.setCrs.assert_called_once_with(project_crs)
        canvas.setDestinationCrs.assert_called_once_with(project_crs)
        manager._style_service.apply_route_style.assert_called_once_with(
            routes, points, samples
        )
        manager._canvas_service.zoom_to_layers.assert_called_once_with(
            iface, (routes, points, samples)
        )
        self.assertEqual(result, (routes, points, samples))


if __name__ == "__main__":
    unittest.main()
