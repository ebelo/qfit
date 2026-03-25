import logging

logger = logging.getLogger(__name__)

from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsProject,
    QgsRasterLayer,
    QgsRectangle,
    QgsVectorLayer,
    QgsVectorLayerTemporalProperties,
    QgsVectorTileLayer,
)

from .activity_query import ActivityQuery, build_subset_string
from .layer_style_service import LayerStyleService
from .mapbox_config import (
    BACKGROUND_LAYER_PREFIX,
    TILE_MODE_RASTER,
    TILE_MODE_VECTOR,
    build_background_layer_name,
    build_vector_tile_layer_uri,
    build_xyz_layer_uri,
    extract_mapbox_vector_source_ids,
    fetch_mapbox_style_definition,
    simplify_mapbox_style_expressions,
    resolve_background_style,
    snap_web_mercator_bounds_to_native_zoom,
)
from .temporal_config import build_temporal_plan, describe_temporal_configuration, is_temporal_mode_enabled


class LayerManager:
    WORKING_CRS = "EPSG:3857"

    def __init__(self, iface):
        self.iface = iface
        self._style_service = LayerStyleService()

    def load_output_layers(self, gpkg_path):
        self._ensure_working_crs()
        activities_layer = self._load_first_available(
            gpkg_path,
            [("activity_tracks", "qfit activities"), ("activities", "qfit activities")],
        )
        starts_layer = self._load_optional_layer(gpkg_path, "activity_starts", "qfit activity starts")
        points_layer = self._load_optional_layer(gpkg_path, "activity_points", "qfit activity points")
        atlas_layer = self._load_optional_layer(gpkg_path, "activity_atlas_pages", "qfit atlas pages")
        self._move_background_layers_to_bottom()
        self._zoom_to_layers([activities_layer, starts_layer, points_layer, atlas_layer])
        return activities_layer, starts_layer, points_layer, atlas_layer

    def ensure_background_layer(self, enabled, preset_name, access_token, style_owner="", style_id="", tile_mode=TILE_MODE_RASTER):
        if not enabled:
            self._remove_background_layers()
            return None

        resolved_owner, resolved_style_id = resolve_background_style(preset_name, style_owner, style_id)
        display_name = build_background_layer_name(preset_name, resolved_owner, resolved_style_id)

        layer = None
        if tile_mode == TILE_MODE_VECTOR:
            try:
                style_definition = fetch_mapbox_style_definition(access_token, resolved_owner, resolved_style_id)
                simplified_style = simplify_mapbox_style_expressions(style_definition)
                tileset_ids = extract_mapbox_vector_source_ids(style_definition)
                # Build URI without styleUrl — we apply the pre-processed style manually
                uri = build_vector_tile_layer_uri(
                    access_token,
                    resolved_owner,
                    resolved_style_id,
                    tileset_ids=tileset_ids,
                    include_style_url=False,
                )
                layer = QgsVectorTileLayer(uri, display_name)
                if not layer.isValid():
                    layer = None
                else:
                    # Apply the simplified style JSON (expression colors already
                    # replaced with literal fallbacks so QGIS doesn't render black)
                    self._apply_mapbox_gl_style(layer, simplified_style)
            except (RuntimeError, KeyError, ValueError, OSError):
                logger.warning("Vector tile layer creation failed, falling back to raster", exc_info=True)
                layer = None

        if layer is None:
            uri = build_xyz_layer_uri(access_token, resolved_owner, resolved_style_id)
            layer = QgsRasterLayer(uri, display_name, "wms")
            if not layer.isValid():
                raise RuntimeError("Could not load the selected Mapbox background layer into QGIS.")

        self._remove_background_layers()
        project = QgsProject.instance()
        project.addMapLayer(layer, False)
        project.layerTreeRoot().addLayer(layer)
        self._move_background_layers_to_bottom()
        return layer

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

    def _load_first_available(self, gpkg_path, candidates):
        last_error = None
        for layer_name, display_name in candidates:
            try:
                return self._load_layer(gpkg_path, layer_name, display_name)
            except RuntimeError as exc:
                last_error = exc
        if last_error is not None:
            raise last_error
        return None

    def _load_optional_layer(self, gpkg_path, layer_name, display_name):
        try:
            return self._load_layer(gpkg_path, layer_name, display_name)
        except RuntimeError:
            return None

    def _load_layer(self, gpkg_path, layer_name, display_name):
        uri = f"{gpkg_path}|layername={layer_name}"
        layer = QgsVectorLayer(uri, display_name, "ogr")
        if not layer.isValid():
            raise RuntimeError(f"Could not load layer '{layer_name}' from {gpkg_path}")

        existing = QgsProject.instance().mapLayersByName(display_name)
        for old_layer in existing:
            QgsProject.instance().removeMapLayer(old_layer.id())
        QgsProject.instance().addMapLayer(layer)
        return layer

    def _apply_label_priority(self, labeling) -> None:
        """Boost label priority for major city/country layers so they win collision
        resolution over minor settlements and POIs in QGIS vector tile rendering.

        For settlement layers we also apply a data-defined priority override using
        ``sizerank`` so that Geneva (sizerank=1) beats Annemasse (sizerank=4)
        within the same label layer — otherwise QGIS resolves intra-layer collisions
        by arbitrary feature order.
        """
        from qgis.core import QgsProperty  # noqa: PLC0415

        # Layer-level base priorities (0–10, higher wins)
        _LAYER_PRIORITIES = {
            "continent-label":          10,
            "country-label":            10,
            "state-label":              9,
            "settlement-major-label":   8,
            "settlement-minor-label":   6,
            "settlement-subdivision-label": 3,
            "water-point-label":        7,
            "water-line-label":         6,
            "natural-line-label":       4,
            "natural-point-label":      2,
            "poi-label":                2,
            "road-label":               5,
            "airport-label":            5,
        }
        # For settlement layers use a data-defined expression to give larger cities
        # higher intra-layer priority. sizerank is inverted (lower = more important)
        # so we map: max(0, 10 - sizerank)  clamped to [1, 10].
        _SETTLEMENT_LAYERS = {"settlement-major-label", "settlement-minor-label"}

        try:
            for style in labeling.styles():
                layer_name = style.layerName()
                priority = _LAYER_PRIORITIES.get(layer_name)
                if priority is None:
                    continue
                settings = style.labelSettings()
                if settings is None:
                    continue
                settings.priority = priority
                if layer_name in _SETTLEMENT_LAYERS:
                    # Data-defined priority: convert sizerank (1=biggest) to 1–10 scale.
                    # The field is named 'sizerank' in Mapbox Streets v8 tiles.
                    # We invert: sizerank 1 → priority 10, sizerank 10 → priority 1.
                    # coalesce to 8 so unknown features get mid-range priority.
                    dd_props = settings.dataDefinedProperties()
                    dd_props.setProperty(
                        87,  # QgsPalLayerSettings.Priority
                        QgsProperty.fromExpression(
                            "greatest(1, least(10, 10 - coalesce(to_int(\"sizerank\"), 8) + 1))"
                        ),
                    )
                    settings.setDataDefinedProperties(dd_props)
                style.setLabelSettings(settings)
        except (RuntimeError, AttributeError):
            logger.debug("Mapbox GL style application skipped", exc_info=True)

    def _apply_mapbox_gl_style(self, layer: QgsVectorTileLayer, style_definition: dict) -> None:
        """Apply a pre-processed Mapbox GL style dict to a QgsVectorTileLayer.

        We pass the simplified style (with expression colors replaced by literal
        fallbacks) directly to QgsMapBoxGlStyleConverter so QGIS does not render
        unresolvable color expressions as black.
        """
        try:
            from qgis.core import (  # noqa: PLC0415
                QgsMapBoxGlStyleConverter,
                QgsMapBoxGlStyleConversionContext,
                Qgis,
            )
            ctx = QgsMapBoxGlStyleConversionContext()
            ctx.setTargetUnit(Qgis.RenderUnit.Millimeters)
            ctx.setPixelSizeConversionFactor(25.4 / 96.0)
            converter = QgsMapBoxGlStyleConverter()
            result = converter.convert(style_definition, ctx)
            if result == QgsMapBoxGlStyleConverter.Success:
                renderer = converter.renderer()
                labeling = converter.labeling()
                if renderer is not None:
                    layer.setRenderer(renderer)
                if labeling is not None:
                    self._apply_label_priority(labeling)
                    layer.setLabeling(labeling)
                    layer.setLabelsEnabled(True)
        except (RuntimeError, ImportError):
            logger.debug("Extent transformation failed, using default renderer", exc_info=True)

    def _remove_background_layers(self):
        project = QgsProject.instance()
        for layer in list(project.mapLayers().values()):
            if layer.name().startswith(BACKGROUND_LAYER_PREFIX):
                project.removeMapLayer(layer.id())

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
        root = QgsProject.instance().layerTreeRoot()
        background_nodes = []
        other_nodes = []
        for child in list(root.children()):
            layer = child.layer() if hasattr(child, "layer") else None
            if layer is not None and layer.name().startswith(BACKGROUND_LAYER_PREFIX):
                background_nodes.append(child)
            else:
                other_nodes.append(child)

        desired_order = other_nodes + background_nodes
        if desired_order and desired_order != list(root.children()):
            root.reorderChildren(desired_order)

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
        if extents is None or extents.isEmpty():
            return extents
        if QgsProject.instance().crs().authid() != self.WORKING_CRS:
            return extents
        if not self._has_raster_background_layer():
            return extents

        viewport_width_px = getattr(canvas, "width", lambda: 1024)()
        viewport_height_px = getattr(canvas, "height", lambda: 768)()
        snapped_bounds, _ = snap_web_mercator_bounds_to_native_zoom(
            (
                extents.xMinimum(),
                extents.yMinimum(),
                extents.xMaximum(),
                extents.yMaximum(),
            ),
            viewport_width_px,
            viewport_height_px,
        )
        return QgsRectangle(*snapped_bounds)

    def _has_raster_background_layer(self) -> bool:
        for layer in QgsProject.instance().mapLayers().values():
            if layer.name().startswith(BACKGROUND_LAYER_PREFIX) and isinstance(layer, QgsRasterLayer):
                return True
        return False
