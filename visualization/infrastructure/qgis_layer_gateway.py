import logging

from qgis.core import QgsProject

logger = logging.getLogger(__name__)

from ...layer_filter_service import LayerFilterService
from ...layer_style_service import LayerStyleService
from ...map_canvas_service import MapCanvasService
from ...mapbox_config import TILE_MODE_RASTER
from ...project_layer_loader import ProjectLayerLoader
from .background_map_service import BackgroundMapService
from .temporal_service import TemporalService


class QgisLayerGateway:
    """QGIS-backed adapter for loading, filtering, styling, and map wiring."""

    WORKING_CRS = "EPSG:3857"

    def __init__(self, iface):
        self.iface = iface
        self._style_service = LayerStyleService()
        self._background_service = BackgroundMapService()
        self._filter_service = LayerFilterService()
        self._project_layer_loader = ProjectLayerLoader()
        self._temporal_service = TemporalService()
        self._canvas_service = MapCanvasService(self._background_service)

    def load_output_layers(self, gpkg_path):
        self._canvas_service.ensure_working_crs(self.iface, preserve_extent=False)
        activities_layer, starts_layer, points_layer, atlas_layer = (
            self._project_layer_loader.load_output_layers(gpkg_path)
        )
        self._move_background_layers_to_bottom()
        self._canvas_service.zoom_to_layers(
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

    def ensure_background_layer(self, enabled, preset_name, access_token, style_owner="", style_id="", tile_mode=TILE_MODE_RASTER):
        return self._background_service.ensure_background_layer(
            enabled=enabled,
            preset_name=preset_name,
            access_token=access_token,
            style_owner=style_owner,
            style_id=style_id,
            tile_mode=tile_mode,
        )

    def apply_filters(self, layer, activity_type=None, date_from=None, date_to=None, min_distance_km=None, max_distance_km=None, search_text=None, detailed_only=False):
        self._filter_service.apply_filters(
            layer,
            activity_type=activity_type,
            date_from=date_from,
            date_to=date_to,
            min_distance_km=min_distance_km,
            max_distance_km=max_distance_km,
            search_text=search_text,
            detailed_only=detailed_only,
        )

    def apply_style(self, activities_layer, starts_layer, points_layer, atlas_layer, preset, background_preset_name=None):
        self._style_service.apply_style(
            activities_layer, starts_layer, points_layer, atlas_layer, preset, background_preset_name
        )

    def apply_temporal_configuration(self, activities_layer, starts_layer, points_layer, atlas_layer, mode_label):
        return self._temporal_service.apply_temporal_configuration(
            activities_layer, starts_layer, points_layer, atlas_layer, mode_label
        )

    def _move_background_layers_to_bottom(self):
        self._background_service.move_background_layers_to_bottom()
