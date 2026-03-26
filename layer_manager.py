import logging

logger = logging.getLogger(__name__)

from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsProject,
    QgsRectangle,
    QgsVectorLayerTemporalProperties,
)

from .activity_query import ActivityQuery, build_subset_string
from .background_map_service import BackgroundMapService
from .layer_style_service import LayerStyleService
from .mapbox_config import TILE_MODE_RASTER
from .project_layer_loader import ProjectLayerLoader
from .temporal_config import build_temporal_plan, describe_temporal_configuration, is_temporal_mode_enabled


class LayerManager:
    WORKING_CRS = "EPSG:3857"

    def __init__(self, iface):
        self.iface = iface
        self._style_service = LayerStyleService()
        self._background_service = BackgroundMapService()
        self._project_layer_loader = ProjectLayerLoader()

    def load_output_layers(self, gpkg_path):
        self._ensure_working_crs()
        activities_layer, starts_layer, points_layer, atlas_layer = (
            self._project_layer_loader.load_output_layers(gpkg_path)
        )
        self._move_background_layers_to_bottom()
        self._zoom_to_layers([activities_layer, starts_layer, points_layer, atlas_layer])
        return activities_layer, starts_layer, points_layer, atlas_layer

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
        if layer is None or not layer.isValid():
            return
        query = ActivityQuery(
            activity_type=activity_type,
            date_from=date_from,
            date_to=date_to,
            min_distance_km=min_distance_km,
            max_distance_km=max_distance_km,
            search_text=search_text,
            detailed_only=detailed_only,
        )
        layer.setSubsetString(build_subset_string(query))
        layer.triggerRepaint()

    def apply_style(self, activities_layer, starts_layer, points_layer, atlas_layer, preset, background_preset_name=None):
        self._style_service.apply_style(
            activities_layer, starts_layer, points_layer, atlas_layer, preset, background_preset_name
        )

    def apply_temporal_configuration(self, activities_layer, starts_layer, points_layer, atlas_layer, mode_label):
        layer_specs = [
            (activities_layer, "activity_tracks"),
            (starts_layer, "activity_starts"),
            (points_layer, "activity_points"),
            (atlas_layer, "activity_atlas_pages"),
        ]
        plans = []
        for layer, layer_key in layer_specs:
            if layer is None:
                continue
            plan = self._apply_temporal_plan(layer, layer_key, mode_label)
            if plan is not None:
                plans.append(plan)
        return describe_temporal_configuration(plans, mode_label)

    def _ensure_working_crs(self):
        project = QgsProject.instance()
        working_crs = QgsCoordinateReferenceSystem(self.WORKING_CRS)
        if not working_crs.isValid():
            return

        canvas = self.iface.mapCanvas() if self.iface is not None else None

        # Preserve the current canvas extent (in map units) before changing CRS
        # so that reprojection doesn't reset the view to the world extent.
        current_extent = canvas.extent() if canvas is not None else None
        current_crs = project.crs()

        project.setCrs(working_crs)
        if canvas is not None:
            canvas.setDestinationCrs(working_crs)
            # Re-apply the previous extent if the project already had a valid CRS
            # and it wasn't the default empty/world extent (i.e. user had panned/zoomed).
            if current_extent is not None and current_crs.isValid() and not current_extent.isEmpty():
                from qgis.core import QgsCoordinateTransform  # noqa: PLC0415
                transform = QgsCoordinateTransform(current_crs, working_crs, project)
                try:
                    transformed = transform.transformBoundingBox(current_extent)
                    if not transformed.isEmpty():
                        canvas.setExtent(transformed)
                        canvas.refresh()
                except RuntimeError:
                    logger.debug("Extent transform in CRS switch failed", exc_info=True)

    def _move_background_layers_to_bottom(self):
        self._background_service.move_background_layers_to_bottom()

    def _apply_temporal_plan(self, layer, layer_key, mode_label):
        props = layer.temporalProperties()
        if props is None:
            return None
        if not is_temporal_mode_enabled(mode_label):
            props.setIsActive(False)
            layer.triggerRepaint()
            return None

        available_fields = [field.name() for field in layer.fields()]
        plan = build_temporal_plan(layer_key, available_fields, mode_label)
        if plan is None:
            props.setIsActive(False)
            layer.triggerRepaint()
            return None

        props.setIsActive(True)
        props.setMode(QgsVectorLayerTemporalProperties.ModeFeatureDateTimeStartAndEndFromExpressions)
        props.setStartExpression(plan.expression)
        props.setEndExpression(plan.expression)
        layer.triggerRepaint()
        return plan

    def _zoom_to_layers(self, layers):
        extents = None
        for layer in layers:
            if layer is None or not layer.isValid():
                continue
            layer_extent = layer.extent()
            if layer_extent.isEmpty():
                continue
            if extents is None:
                extents = QgsRectangle(layer_extent)
            else:
                extents.combineExtentWith(layer_extent)

        if extents is None or extents.isEmpty():
            return

        canvas = self.iface.mapCanvas() if self.iface is not None else None
        if canvas is None:
            return

        extents = self._snap_extent_to_background_tile_zoom(extents, canvas)
        canvas.setExtent(extents)
        canvas.refresh()

    def _snap_extent_to_background_tile_zoom(self, extents, canvas):
        return self._background_service.snap_extent_to_background_tile_zoom(extents, canvas)
