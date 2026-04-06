import logging

logger = logging.getLogger(__name__)

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QColor
from qgis.core import (
    QgsCategorizedSymbolRenderer,
    QgsFillSymbol,
    QgsGradientColorRamp,
    QgsGradientStop,
    QgsHeatmapRenderer,
    QgsLineSymbol,
    QgsMarkerSymbol,
    QgsProject,
    QgsRendererCategory,
    QgsSimpleLineSymbolLayer,
    QgsSingleSymbolRenderer,
    QgsUnitTypes,
)

from ..map_style import (
    DEFAULT_SIMPLE_LINE_HEX,
    pick_activity_style_field,
    resolve_activity_color,
    resolve_basemap_line_style,
)
from ...mapbox_config import BACKGROUND_LAYER_PREFIX

BY_ACTIVITY_TYPE_PRESET = "By activity type"
OTHER_ACTIVITY_LABEL = "Other"


def build_qfit_heatmap_renderer():
    renderer = QgsHeatmapRenderer()
    renderer.setRadius(12)
    renderer.setRadiusUnit(QgsUnitTypes.RenderMillimeters)
    renderer.setRenderQuality(2)
    heat_ramp = QgsGradientColorRamp(
        QColor("#00000000"),
        QColor(239, 108, 0, 215),
        False,
        [
            QgsGradientStop(0.18, QColor("#00000000")),
            QgsGradientStop(0.38, QColor(79, 195, 247, 70)),
            QgsGradientStop(0.62, QColor(255, 183, 77, 135)),
            QgsGradientStop(0.82, QColor(255, 138, 101, 185)),
        ],
    )
    renderer.setColorRamp(heat_ramp)
    return renderer


class LayerStyleService:
    """Applies visual styles (renderers, opacity) to qfit output layers.

    Extracted from ``LayerManager`` so that styling logic can be tested and
    evolved independently of layer-loading and canvas management.
    """

    def apply_style(self, activities_layer, starts_layer, points_layer, atlas_layer, preset, background_preset_name=None):
        preset = preset or "Simple lines"
        basemap_preset_name = background_preset_name or self._infer_background_preset_name()

        self._apply_activities_layer_style(activities_layer, preset, basemap_preset_name)
        self._apply_points_layer_style(points_layer, preset, basemap_preset_name)
        self._apply_starts_layer_style(starts_layer, points_layer, preset, basemap_preset_name)

        if atlas_layer is not None:
            self._apply_atlas_page_style(atlas_layer)

    def _apply_activities_layer_style(self, activities_layer, preset, basemap_preset_name):
        if activities_layer is None:
            return
        if preset == BY_ACTIVITY_TYPE_PRESET:
            self._apply_categorized_line_style(activities_layer, basemap_preset_name)
            return
        if preset == "Heatmap":
            self._apply_simple_line_style(activities_layer, basemap_preset_name, subtle=True)
            activities_layer.setOpacity(0.0)
            return
        if preset == "Track points":
            self._apply_simple_line_style(activities_layer, basemap_preset_name, subtle=True)
            return
        self._apply_simple_line_style(activities_layer, basemap_preset_name)

    def _apply_points_layer_style(self, points_layer, preset, basemap_preset_name):
        if points_layer is None:
            return
        if preset == "Heatmap":
            self._apply_heatmap_style(points_layer)
            return
        if preset == "Track points":
            self._apply_track_point_style(points_layer, subtle=False)
            return
        if preset == BY_ACTIVITY_TYPE_PRESET:
            self._apply_categorized_point_style(points_layer, basemap_preset_name)
            return
        self._apply_track_point_style(points_layer, subtle=True)

    def _apply_starts_layer_style(self, starts_layer, points_layer, preset, basemap_preset_name):
        if starts_layer is None:
            return
        if preset == "Clustered starts":
            self._apply_clusterish_style(starts_layer)
            return
        if preset == "Start points":
            self._apply_start_point_style(starts_layer, subtle=False)
            return
        if preset == "Heatmap":
            if points_layer is None:
                self._apply_heatmap_style(starts_layer)
            else:
                self._apply_start_point_style(starts_layer, subtle=True)
                starts_layer.setOpacity(0.0)
            return
        if preset == BY_ACTIVITY_TYPE_PRESET:
            self._apply_categorized_point_style(starts_layer, basemap_preset_name, size="3.0")
            return
        self._apply_start_point_style(starts_layer, subtle=points_layer is not None)

    def _infer_background_preset_name(self):
        for layer in QgsProject.instance().mapLayers().values():
            name = layer.name()
            if not name.startswith(BACKGROUND_LAYER_PREFIX):
                continue
            if " — " not in name:
                return None
            return name.split(" — ", 1)[1].strip() or None
        return None

    def _apply_simple_line_style(self, layer, basemap_preset_name=None, subtle=False):
        line_style = resolve_basemap_line_style(basemap_preset_name)
        symbol = self._build_line_symbol(DEFAULT_SIMPLE_LINE_HEX, line_style)
        layer.setRenderer(QgsSingleSymbolRenderer(symbol))
        layer.setOpacity(line_style.opacity * 0.35 if subtle else line_style.opacity)
        layer.triggerRepaint()

    def _apply_categorized_line_style(self, layer, basemap_preset_name=None):
        line_style = resolve_basemap_line_style(basemap_preset_name)
        field_name = pick_activity_style_field(field.name() for field in layer.fields())
        if field_name is None:
            self._apply_simple_line_style(layer, basemap_preset_name)
            return

        field_index = layer.fields().indexOf(field_name)
        values = sorted(value for value in layer.uniqueValues(field_index) if value not in (None, ""))
        categories = []
        for value in values:
            symbol = self._build_line_symbol(resolve_activity_color(value, basemap_preset_name), line_style)
            categories.append(QgsRendererCategory(value, symbol, value or "Unknown"))

        renderer = QgsCategorizedSymbolRenderer(field_name, categories)
        renderer.setSourceSymbol(self._build_line_symbol(resolve_activity_color(OTHER_ACTIVITY_LABEL, basemap_preset_name), line_style))
        layer.setRenderer(renderer)
        layer.setOpacity(line_style.opacity)
        layer.triggerRepaint()

    def _apply_categorized_point_style(self, layer, basemap_preset_name=None, size="1.8"):
        field_name = pick_activity_style_field(field.name() for field in layer.fields())
        if field_name is None:
            self._apply_track_point_style(layer, subtle=True)
            return

        field_index = layer.fields().indexOf(field_name)
        values = sorted(value for value in layer.uniqueValues(field_index) if value not in (None, ""))
        categories = []
        for value in values:
            color_hex = resolve_activity_color(value, basemap_preset_name)
            symbol = self._build_categorized_point_symbol(color_hex, size)
            categories.append(QgsRendererCategory(value, symbol, value or "Unknown"))

        renderer = QgsCategorizedSymbolRenderer(field_name, categories)
        fallback_hex = resolve_activity_color(OTHER_ACTIVITY_LABEL, basemap_preset_name)
        renderer.setSourceSymbol(self._build_categorized_point_symbol(fallback_hex, size))
        layer.setRenderer(renderer)
        layer.setOpacity(0.75)
        layer.triggerRepaint()

    def _build_categorized_point_symbol(self, color_hex, size):
        return QgsMarkerSymbol.createSimple(
            {
                "name": "circle",
                "color": color_hex,
                "size": size,
                "outline_style": "no",
            }
        )

    def _build_line_symbol(self, color_hex, line_style):
        symbol = QgsLineSymbol()
        symbol.deleteSymbolLayer(0)

        if line_style.outline_color and line_style.outline_width > 0:
            outline_layer = QgsSimpleLineSymbolLayer()
            outline_layer.setColor(QColor(line_style.outline_color))
            outline_layer.setWidth(line_style.line_width + (line_style.outline_width * 2.0))
            outline_layer.setPenCapStyle(Qt.RoundCap)
            outline_layer.setPenJoinStyle(Qt.RoundJoin)
            symbol.appendSymbolLayer(outline_layer)

        line_layer = QgsSimpleLineSymbolLayer()
        line_layer.setColor(QColor(color_hex))
        line_layer.setWidth(line_style.line_width)
        line_layer.setPenCapStyle(Qt.RoundCap)
        line_layer.setPenJoinStyle(Qt.RoundJoin)
        symbol.appendSymbolLayer(line_layer)
        return symbol

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
        layer.setRenderer(build_qfit_heatmap_renderer())
        layer.setOpacity(0.75)
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

    def _apply_atlas_page_style(self, layer):
        symbol = QgsFillSymbol.createSimple(
            {
                "color": "255,255,255,0",
                "outline_color": "230,126,34,230",
                "outline_width": "0.6",
                "outline_style": "dash",
            }
        )
        layer.setRenderer(QgsSingleSymbolRenderer(symbol))
        layer.setOpacity(1.0)
        layer.triggerRepaint()
