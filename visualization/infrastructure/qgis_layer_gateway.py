import logging
from types import SimpleNamespace

from qgis.core import QgsProject

logger = logging.getLogger(__name__)

from ...mapbox_config import TILE_MODE_RASTER


def _build_background_service():
    from .background_map_service import BackgroundMapService

    return BackgroundMapService()


def _build_map_canvas_service(background_service):
    from .map_canvas_service import MapCanvasService

    return MapCanvasService(background_service)


def _build_project_layer_loader():
    from .project_layer_loader import ProjectLayerLoader

    return ProjectLayerLoader()


def _build_temporal_service():
    from .temporal_service import TemporalService

    return TemporalService()


def _build_layer_filter_service():
    from .layer_filter_service import LayerFilterService

    return LayerFilterService()


def _build_layer_style_service():
    from .layer_style_service import LayerStyleService

    return LayerStyleService()


class QgisLayerGateway:
    """QGIS-backed adapter for loading, filtering, styling, and map wiring."""

    WORKING_CRS = "EPSG:3857"

    def __init__(self, iface):
        self.iface = iface
        self._style_service = SimpleNamespace()
        self._background_service = SimpleNamespace()
        self._filter_service = SimpleNamespace()
        self._project_layer_loader = SimpleNamespace()
        self._temporal_service = SimpleNamespace()
        self._canvas_service = SimpleNamespace()

    def _get_background_service(self):
        if not hasattr(self._background_service, "ensure_background_layer"):
            self._background_service = _build_background_service()
        return self._background_service

    def _get_canvas_service(self):
        if not hasattr(self._canvas_service, "ensure_working_crs"):
            self._canvas_service = _build_map_canvas_service(self._get_background_service())
        return self._canvas_service

    def _get_filter_service(self):
        if not hasattr(self._filter_service, "apply_filters"):
            self._filter_service = _build_layer_filter_service()
        return self._filter_service

    def _get_project_layer_loader(self):
        if not hasattr(self._project_layer_loader, "load_output_layers"):
            self._project_layer_loader = _build_project_layer_loader()
        return self._project_layer_loader

    def _get_style_service(self):
        if not hasattr(self._style_service, "apply_style"):
            self._style_service = _build_layer_style_service()
        return self._style_service

    def _get_temporal_service(self):
        if not hasattr(self._temporal_service, "apply_temporal_configuration"):
            self._temporal_service = _build_temporal_service()
        return self._temporal_service

    def load_output_layers(self, gpkg_path):
        canvas_service = self._get_canvas_service()
        project_layer_loader = self._get_project_layer_loader()
        canvas_service.ensure_working_crs(self.iface, preserve_extent=False)
        activities_layer, starts_layer, points_layer, atlas_layer = (
            project_layer_loader.load_output_layers(gpkg_path)
        )
        self._move_background_layers_to_bottom()
        canvas_service.zoom_to_layers(
            self.iface, [activities_layer, starts_layer, points_layer, atlas_layer]
        )
        return activities_layer, starts_layer, points_layer, atlas_layer

    def remove_layers(self, layers):
        for layer in layers or []:
            if layer is None:
                continue
            try:
                QgsProject.instance().removeMapLayer(layer)
            except RuntimeError:
                logger.debug("Failed to remove layer from project", exc_info=True)

    def has_features(self, layer):
        if layer is None:
            return False
        try:
            return layer.featureCount() > 0
        except (AttributeError, RuntimeError, TypeError):
            return False

    def ensure_background_layer(self, enabled, preset_name, access_token, style_owner="", style_id="", tile_mode=TILE_MODE_RASTER):
        return self._get_background_service().ensure_background_layer(
            enabled=enabled,
            preset_name=preset_name,
            access_token=access_token,
            style_owner=style_owner,
            style_id=style_id,
            tile_mode=tile_mode,
        )

    def apply_filters(self, layer, activity_type=None, date_from=None, date_to=None, min_distance_km=None, max_distance_km=None, search_text=None, detailed_only=False, detailed_route_filter=None):
        self._get_filter_service().apply_filters(
            layer,
            activity_type=activity_type,
            date_from=date_from,
            date_to=date_to,
            min_distance_km=min_distance_km,
            max_distance_km=max_distance_km,
            search_text=search_text,
            detailed_only=detailed_only,
            detailed_route_filter=detailed_route_filter,
        )

    def apply_style(
        self,
        activities_layer,
        starts_layer,
        points_layer,
        atlas_layer,
        preset=None,
        background_preset_name=None,
        render_plan=None,
    ):
        self._get_style_service().apply_style(
            activities_layer,
            starts_layer,
            points_layer,
            atlas_layer,
            preset,
            background_preset_name,
            render_plan=render_plan,
        )

    def apply_temporal_configuration(self, activities_layer, starts_layer, points_layer, atlas_layer, mode_label):
        return self._get_temporal_service().apply_temporal_configuration(
            activities_layer, starts_layer, points_layer, atlas_layer, mode_label
        )

    def _move_background_layers_to_bottom(self):
        self._get_background_service().move_background_layers_to_bottom()
