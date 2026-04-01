import importlib
import sys
import unittest
from types import ModuleType
from unittest.mock import MagicMock, patch

from tests import _path  # noqa: F401
from qfit.visualization.application.layer_gateway import LayerGateway


class LayerGatewayBoundaryTests(unittest.TestCase):
    def test_load_workflow_service_accepts_gateway_protocol_instance(self):
        from qfit.load_workflow import LoadWorkflowService

        gateway = MagicMock(spec=LayerGateway)
        service = LoadWorkflowService(gateway)

        self.assertIs(service.layer_gateway, gateway)

    def test_visual_apply_service_accepts_gateway_protocol_instance(self):
        from qfit.visual_apply import VisualApplyService

        gateway = MagicMock(spec=LayerGateway)
        service = VisualApplyService(gateway)

        self.assertIs(service.layer_gateway, gateway)

    def test_qgis_gateway_adapter_and_legacy_import_share_same_class(self):
        modules = self._qgis_gateway_modules()

        with patch.dict(sys.modules, modules, clear=False):
            self._reset_qgis_gateway_imports()
            adapter_module = importlib.import_module(
                "qfit.visualization.infrastructure.qgis_layer_gateway"
            )
            layer_manager_module = importlib.import_module("qfit.layer_manager")

        self.assertIs(layer_manager_module.LayerManager, adapter_module.QgisLayerGateway)

    def test_qgis_gateway_satisfies_protocol_and_delegates_to_services(self):
        modules = self._qgis_gateway_modules()

        with patch.dict(sys.modules, modules, clear=False):
            self._reset_qgis_gateway_imports()
            adapter_module = importlib.import_module(
                "qfit.visualization.infrastructure.qgis_layer_gateway"
            )

            gateway = adapter_module.QgisLayerGateway(MagicMock(name="iface"))
            result = gateway.load_output_layers("/tmp/out.gpkg")

        self.assertIsInstance(gateway, LayerGateway)
        canvas = gateway._canvas_service
        loader = gateway._project_layer_loader
        background = gateway._background_service
        canvas.ensure_working_crs.assert_called_once_with(gateway.iface, preserve_extent=False)
        loader.load_output_layers.assert_called_once_with("/tmp/out.gpkg")
        canvas.zoom_to_layers.assert_called_once_with(
            gateway.iface,
            [result[0], result[1], result[2], result[3]],
        )
        background.move_background_layers_to_bottom.assert_called_once_with()

    def test_qgis_gateway_remove_layers_delegates_to_qgsproject(self):
        modules = self._qgis_gateway_modules()

        with patch.dict(sys.modules, modules, clear=False):
            self._reset_qgis_gateway_imports()
            adapter_module = importlib.import_module(
                "qfit.visualization.infrastructure.qgis_layer_gateway"
            )

            gateway = adapter_module.QgisLayerGateway(MagicMock(name="iface"))
            layer_a = MagicMock(name="layer_a")
            layer_b = MagicMock(name="layer_b")

            gateway.remove_layers([layer_a, None, layer_b])

        modules["qgis.core"].QgsProject.instance.return_value.removeMapLayer.assert_any_call(layer_a)
        modules["qgis.core"].QgsProject.instance.return_value.removeMapLayer.assert_any_call(layer_b)

    @staticmethod
    def _reset_qgis_gateway_imports():
        for name in [
            "qfit.layer_manager",
            "qfit.visualization.infrastructure.qgis_layer_gateway",
        ]:
            sys.modules.pop(name, None)

    @staticmethod
    def _qgis_gateway_modules():
        def class_module(name, class_name, instance):
            module = ModuleType(name)
            setattr(module, class_name, MagicMock(return_value=instance))
            return module

        style_service = MagicMock(name="style_service")
        background_service = MagicMock(name="background_service")
        filter_service = MagicMock(name="filter_service")
        project_layer_loader = MagicMock(name="project_layer_loader")
        temporal_service = MagicMock(name="temporal_service")
        map_canvas_service = MagicMock(name="map_canvas_service")

        project_layer_loader.load_output_layers.return_value = (
            MagicMock(name="activities"),
            MagicMock(name="starts"),
            MagicMock(name="points"),
            MagicMock(name="atlas"),
        )

        mapbox_config = ModuleType("qfit.mapbox_config")
        mapbox_config.TILE_MODE_RASTER = "raster"

        qgis_core = ModuleType("qgis.core")
        qgis_core.QgsProject = MagicMock(name="QgsProject")

        return {
            "qgis.core": qgis_core,
            "qfit.background_map_service": class_module(
                "qfit.background_map_service",
                "BackgroundMapService",
                background_service,
            ),
            "qfit.layer_filter_service": class_module(
                "qfit.layer_filter_service",
                "LayerFilterService",
                filter_service,
            ),
            "qfit.layer_style_service": class_module(
                "qfit.layer_style_service",
                "LayerStyleService",
                style_service,
            ),
            "qfit.map_canvas_service": class_module(
                "qfit.map_canvas_service",
                "MapCanvasService",
                map_canvas_service,
            ),
            "qfit.mapbox_config": mapbox_config,
            "qfit.project_layer_loader": class_module(
                "qfit.project_layer_loader",
                "ProjectLayerLoader",
                project_layer_loader,
            ),
            "qfit.temporal_service": class_module(
                "qfit.temporal_service",
                "TemporalService",
                temporal_service,
            ),
        }
