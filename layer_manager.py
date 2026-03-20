from qgis.PyQt.QtGui import QColor
from qgis.core import (
    QgsCategorizedSymbolRenderer,
    QgsGradientColorRamp,
    QgsHeatmapRenderer,
    QgsLineSymbol,
    QgsMarkerSymbol,
    QgsProject,
    QgsRectangle,
    QgsRendererCategory,
    QgsSingleSymbolRenderer,
    QgsStyle,
    QgsVectorLayer,
)


class LayerManager:
    def __init__(self, iface):
        self.iface = iface

    def load_output_layers(self, gpkg_path):
        activities_layer = self._load_first_available(
            gpkg_path,
            [("activity_tracks", "QFIT Activities"), ("activities", "QFIT Activities")],
        )
        starts_layer = self._load_optional_layer(gpkg_path, "activity_starts", "QFIT Activity Starts")
        points_layer = self._load_optional_layer(gpkg_path, "activity_points", "QFIT Activity Points")
        self._zoom_to_layers([activities_layer, starts_layer, points_layer])
        return activities_layer, starts_layer, points_layer

    def apply_filters(self, layer, activity_type=None, date_from=None, date_to=None, min_distance_km=None):
        if layer is None:
            return
        clauses = []
        if activity_type and activity_type != "All":
            clauses.append(f'"activity_type" = \'{activity_type.replace("'", "''")}\'')
        if date_from:
            clauses.append(f'"start_date" >= \'{date_from}T00:00:00\'')
        if date_to:
            clauses.append(f'"start_date" <= \'{date_to}T23:59:59\'')
        if min_distance_km and min_distance_km > 0:
            clauses.append(f'"distance_m" >= {float(min_distance_km) * 1000.0}')
        layer.setSubsetString(" AND ".join(clauses))
        layer.triggerRepaint()

    def apply_style(self, activities_layer, starts_layer, points_layer, preset):
        preset = preset or "Simple lines"
        if activities_layer is not None:
            if preset == "By activity type":
                self._apply_categorized_line_style(activities_layer)
            else:
                self._apply_simple_line_style(activities_layer)

        if points_layer is not None:
            if preset == "Heatmap":
                self._apply_heatmap_style(points_layer)
            elif preset == "Track points":
                self._apply_track_point_style(points_layer, subtle=False)
            else:
                self._apply_track_point_style(points_layer, subtle=True)

        if starts_layer is not None:
            if preset == "Clustered starts":
                self._apply_clusterish_style(starts_layer)
            elif preset == "Start points":
                self._apply_start_point_style(starts_layer, subtle=False)
            elif preset == "Heatmap" and points_layer is None:
                self._apply_heatmap_style(starts_layer)
            else:
                self._apply_start_point_style(starts_layer, subtle=points_layer is not None)

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

        canvas.setExtent(extents)
        canvas.refresh()

    def _apply_simple_line_style(self, layer):
        symbol = QgsLineSymbol.createSimple({"line_color": "39,174,96,255", "line_width": "0.8"})
        layer.setRenderer(QgsSingleSymbolRenderer(symbol))
        layer.setOpacity(1.0)
        layer.triggerRepaint()

    def _apply_categorized_line_style(self, layer):
        palette = [
            QColor("#27ae60"),
            QColor("#2980b9"),
            QColor("#8e44ad"),
            QColor("#d35400"),
            QColor("#c0392b"),
        ]
        field_index = layer.fields().indexOf("activity_type")
        values = sorted(value for value in layer.uniqueValues(field_index) if value not in (None, ""))
        categories = []
        for index, value in enumerate(values):
            symbol = QgsLineSymbol.createSimple(
                {"line_color": palette[index % len(palette)].name(), "line_width": "0.9"}
            )
            categories.append(QgsRendererCategory(value, symbol, value or "Unknown"))
        layer.setRenderer(QgsCategorizedSymbolRenderer("activity_type", categories))
        layer.setOpacity(1.0)
        layer.triggerRepaint()

    def _apply_start_point_style(self, layer, subtle=False):
        symbol = QgsMarkerSymbol.createSimple(
            {
                "name": "circle",
                "color": "243,156,18,200" if not subtle else "149,165,166,170",
                "size": "2.6" if not subtle else "1.8",
            }
        )
        layer.setRenderer(QgsSingleSymbolRenderer(symbol))
        layer.setOpacity(0.9 if not subtle else 0.6)
        layer.triggerRepaint()

    def _apply_track_point_style(self, layer, subtle=False):
        symbol = QgsMarkerSymbol.createSimple(
            {
                "name": "circle",
                "color": "52,152,219,200" if not subtle else "52,152,219,120",
                "size": "1.4" if not subtle else "0.8",
                "outline_style": "no",
            }
        )
        layer.setRenderer(QgsSingleSymbolRenderer(symbol))
        layer.setOpacity(0.8 if not subtle else 0.35)
        layer.triggerRepaint()

    def _apply_heatmap_style(self, layer):
        renderer = QgsHeatmapRenderer()
        renderer.setRadius(12)
        renderer.setColorRamp(
            QgsStyle.defaultStyle().colorRamp("Turbo")
            or QgsGradientColorRamp(QColor("#2c3e50"), QColor("#e74c3c"))
        )
        layer.setRenderer(renderer)
        layer.setOpacity(1.0)
        layer.triggerRepaint()

    def _apply_clusterish_style(self, layer):
        symbol = QgsMarkerSymbol.createSimple(
            {
                "name": "circle",
                "color": "52,152,219,200",
                "size": "4.2",
                "outline_color": "255,255,255,255",
                "outline_width": "0.4",
            }
        )
        layer.setRenderer(QgsSingleSymbolRenderer(symbol))
        layer.setOpacity(0.75)
        layer.triggerRepaint()
