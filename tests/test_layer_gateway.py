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
            gateway._canvas_service = MagicMock(name="canvas_service")
            gateway._project_layer_loader = MagicMock(name="project_layer_loader")
            gateway._project_layer_loader.load_output_layers.return_value = (
                MagicMock(name="activities"),
                MagicMock(name="starts"),
                MagicMock(name="points"),
                MagicMock(name="atlas"),
            )
            gateway._move_background_layers_to_bottom = MagicMock(name="move_background_layers_to_bottom")
            result = gateway.load_output_layers("/tmp/out.gpkg")

        self.assertIsInstance(gateway, LayerGateway)
        canvas = gateway._canvas_service
        loader = gateway._project_layer_loader
        canvas.ensure_working_crs.assert_called_once_with(gateway.iface, preserve_extent=False)
        loader.load_output_layers.assert_called_once_with("/tmp/out.gpkg")
        canvas.zoom_to_layers.assert_called_once_with(
            gateway.iface,
            [result[0], result[1], result[2], result[3]],
        )
        gateway._move_background_layers_to_bottom.assert_called_once_with()

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

    def test_qgis_gateway_lazy_services_delegate_cleanly(self):
        modules = self._qgis_gateway_modules()

        with patch.dict(sys.modules, modules, clear=False):
            self._reset_qgis_gateway_imports()
            adapter_module = importlib.import_module(
                "qfit.visualization.infrastructure.qgis_layer_gateway"
            )

            background_service = MagicMock(name="background_service")
            filter_service = MagicMock(name="filter_service")
            style_service = MagicMock(name="style_service")
            temporal_service = MagicMock(name="temporal_service")
            with patch.object(adapter_module, "_build_background_service", return_value=background_service), patch.object(
                adapter_module,
                "_build_layer_filter_service",
                return_value=filter_service,
            ), patch.object(
                adapter_module,
                "_build_layer_style_service",
                return_value=style_service,
            ), patch.object(
                adapter_module,
                "_build_temporal_service",
                return_value=temporal_service,
            ):
                gateway = adapter_module.QgisLayerGateway(MagicMock(name="iface"))
                background_result = gateway.ensure_background_layer(True, "Outdoor", "tok")
                gateway.apply_filters(
                    MagicMock(name="layer"),
                    activity_type="Ride",
                    date_from="2026-01-01",
                    date_to="2026-01-31",
                    min_distance_km=10,
                    max_distance_km=20,
                    search_text="alps",
                    detailed_only=True,
                    detailed_route_filter="missing",
                )
                gateway.apply_style("activities", "starts", "points", "atlas", "Simple lines", "Outdoor")
                temporal_result = gateway.apply_temporal_configuration(
                    "activities", "starts", "points", "atlas", "By month"
                )

        self.assertIs(background_result, background_service.ensure_background_layer.return_value)
        self.assertIs(temporal_result, temporal_service.apply_temporal_configuration.return_value)
        background_service.ensure_background_layer.assert_called_once_with(
            enabled=True,
            preset_name="Outdoor",
            access_token="tok",
            style_owner="",
            style_id="",
            tile_mode="raster",
        )
        filter_service.apply_filters.assert_called_once_with(
            unittest.mock.ANY,
            activity_type="Ride",
            date_from="2026-01-01",
            date_to="2026-01-31",
            min_distance_km=10,
            max_distance_km=20,
            search_text="alps",
            detailed_only=True,
            detailed_route_filter="missing",
        )
        style_service.apply_style.assert_called_once_with(
            "activities",
            "starts",
            "points",
            "atlas",
            "Simple lines",
            "Outdoor",
            render_plan=None,
        )
        temporal_service.apply_temporal_configuration.assert_called_once_with(
            "activities", "starts", "points", "atlas", "By month"
        )

    def test_qgis_gateway_reuses_injected_service_overrides(self):
        modules = self._qgis_gateway_modules()

        with patch.dict(sys.modules, modules, clear=False):
            self._reset_qgis_gateway_imports()
            adapter_module = importlib.import_module(
                "qfit.visualization.infrastructure.qgis_layer_gateway"
            )

            gateway = adapter_module.QgisLayerGateway(MagicMock(name="iface"))
            gateway._background_service = MagicMock(name="background_service")
            gateway._canvas_service = MagicMock(name="canvas_service")
            gateway._project_layer_loader = MagicMock(name="project_layer_loader")
            gateway._project_layer_loader.load_output_layers.return_value = (
                MagicMock(name="activities"),
                MagicMock(name="starts"),
                MagicMock(name="points"),
                MagicMock(name="atlas"),
            )

            gateway.load_output_layers("/tmp/override.gpkg")
            gateway.ensure_background_layer(False, "Winter", "")

        modules["qfit.visualization.infrastructure.background_map_service"].BackgroundMapService.assert_not_called()
        modules["qfit.visualization.infrastructure.map_canvas_service"].MapCanvasService.assert_not_called()
        modules["qfit.visualization.infrastructure.project_layer_loader"].ProjectLayerLoader.assert_not_called()
        gateway._canvas_service.ensure_working_crs.assert_called_once_with(gateway.iface, preserve_extent=False)
        gateway._project_layer_loader.load_output_layers.assert_called_once_with("/tmp/override.gpkg")
        gateway._background_service.ensure_background_layer.assert_called_once()

    @staticmethod
    def _reset_qgis_gateway_imports():
        for name in [
            "qfit.layer_manager",
            "qfit.project_layer_loader",
            "qfit.visualization.infrastructure",
            "qfit.visualization.infrastructure.background_map_service",
            "qfit.visualization.infrastructure.layer_filter_service",
            "qfit.visualization.infrastructure.layer_style_service",
            "qfit.visualization.infrastructure.map_canvas_service",
            "qfit.visualization.infrastructure.project_layer_loader",
            "qfit.visualization.infrastructure.qgis_layer_gateway",
            "qfit.visualization.infrastructure.temporal_service",
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
        mapbox_config.BACKGROUND_LAYER_PREFIX = "qfit background"
        mapbox_config.TILE_MODE_RASTER = "raster"
        mapbox_config.TILE_MODE_VECTOR = "vector"
        mapbox_config.build_background_layer_name = MagicMock(name="build_background_layer_name")
        mapbox_config.build_vector_tile_layer_uri = MagicMock(name="build_vector_tile_layer_uri")
        mapbox_config.build_xyz_layer_uri = MagicMock(name="build_xyz_layer_uri")
        mapbox_config.extract_mapbox_vector_source_ids = MagicMock(name="extract_mapbox_vector_source_ids")
        mapbox_config.fetch_mapbox_style_definition = MagicMock(name="fetch_mapbox_style_definition")
        mapbox_config.resolve_background_style = MagicMock(name="resolve_background_style")
        mapbox_config.simplify_mapbox_style_expressions = MagicMock(name="simplify_mapbox_style_expressions")
        mapbox_config.snap_web_mercator_bounds_to_native_zoom = MagicMock(
            name="snap_web_mercator_bounds_to_native_zoom"
        )

        qgis_core = ModuleType("qgis.core")
        qgis_core.QgsProject = MagicMock(name="QgsProject")
        qgis_core.QgsCoordinateReferenceSystem = MagicMock(name="QgsCoordinateReferenceSystem")
        qgis_core.QgsCoordinateTransform = MagicMock(name="QgsCoordinateTransform")
        qgis_core.QgsCategorizedSymbolRenderer = MagicMock(name="QgsCategorizedSymbolRenderer")
        qgis_core.QgsFillSymbol = MagicMock(name="QgsFillSymbol")
        qgis_core.QgsGradientColorRamp = MagicMock(name="QgsGradientColorRamp")
        qgis_core.QgsGradientStop = MagicMock(name="QgsGradientStop")
        qgis_core.QgsHeatmapRenderer = MagicMock(name="QgsHeatmapRenderer")
        qgis_core.QgsLineSymbol = MagicMock(name="QgsLineSymbol")
        qgis_core.QgsMarkerSymbol = MagicMock(name="QgsMarkerSymbol")
        qgis_core.QgsRasterLayer = MagicMock(name="QgsRasterLayer")
        qgis_core.QgsRectangle = MagicMock(name="QgsRectangle")
        qgis_core.QgsRendererCategory = MagicMock(name="QgsRendererCategory")
        qgis_core.QgsSimpleLineSymbolLayer = MagicMock(name="QgsSimpleLineSymbolLayer")
        qgis_core.QgsSingleSymbolRenderer = MagicMock(name="QgsSingleSymbolRenderer")
        qgis_core.QgsUnitTypes = MagicMock(name="QgsUnitTypes")
        qgis_core.QgsVectorTileLayer = MagicMock(name="QgsVectorTileLayer")
        temporal_props = MagicMock(name="QgsVectorLayerTemporalProperties")
        temporal_props.ModeFeatureDateTimeStartAndEndFromExpressions = 1
        qgis_core.QgsVectorLayer = MagicMock(name="QgsVectorLayer")
        qgis_core.QgsVectorLayerTemporalProperties = temporal_props

        qgis_mod = ModuleType("qgis")
        qgis_mod.core = qgis_core
        qgis_pyqt = ModuleType("qgis.PyQt")
        qgis_qtcore = ModuleType("qgis.PyQt.QtCore")
        qt = MagicMock(name="Qt")
        qt.RoundCap = 1
        qt.RoundJoin = 1
        qgis_qtcore.Qt = qt
        qgis_qtgui = ModuleType("qgis.PyQt.QtGui")
        qgis_qtgui.QColor = MagicMock(name="QColor")

        return {
            "qgis": qgis_mod,
            "qgis.core": qgis_core,
            "qgis.PyQt": qgis_pyqt,
            "qgis.PyQt.QtCore": qgis_qtcore,
            "qgis.PyQt.QtGui": qgis_qtgui,
            "qfit.visualization.infrastructure.background_map_service": class_module(
                "qfit.visualization.infrastructure.background_map_service",
                "BackgroundMapService",
                background_service,
            ),
            "qfit.visualization.infrastructure.layer_filter_service": class_module(
                "qfit.visualization.infrastructure.layer_filter_service",
                "LayerFilterService",
                filter_service,
            ),
            "qfit.visualization.infrastructure.layer_style_service": class_module(
                "qfit.visualization.infrastructure.layer_style_service",
                "LayerStyleService",
                style_service,
            ),
            "qfit.visualization.infrastructure.map_canvas_service": class_module(
                "qfit.visualization.infrastructure.map_canvas_service",
                "MapCanvasService",
                map_canvas_service,
            ),
            "qfit.mapbox_config": mapbox_config,
            "qfit.visualization.infrastructure.project_layer_loader": class_module(
                "qfit.visualization.infrastructure.project_layer_loader",
                "ProjectLayerLoader",
                project_layer_loader,
            ),
            "qfit.visualization.infrastructure.temporal_service": class_module(
                "qfit.visualization.infrastructure.temporal_service",
                "TemporalService",
                temporal_service,
            ),
        }
