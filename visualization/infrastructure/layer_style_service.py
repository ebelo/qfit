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

from ...mapbox_config import BACKGROUND_LAYER_PREFIX
from ..application.render_plan import (
    BY_ACTIVITY_TYPE_PRESET,
    DEFAULT_RENDER_PRESET,
    RENDERER_ATLAS_PAGE,
    RENDERER_CATEGORIZED_LINES,
    RENDERER_CATEGORIZED_POINTS,
    RENDERER_CLUSTERISH,
    RENDERER_HEATMAP,
    RENDERER_SIMPLE_LINES,
    RENDERER_START_POINTS,
    RENDERER_TRACK_POINTS,
    RenderPlan,
    build_render_plan,
)
from ..map_style import (
    DEFAULT_SIMPLE_LINE_HEX,
    pick_activity_style_field,
    resolve_activity_color,
    resolve_basemap_line_style,
)

OTHER_ACTIVITY_LABEL = "Other"
HEATMAP_ANALYSIS_RADIUS_M = 750
HEATMAP_VISUALIZE_RADIUS_M = 250
HEATMAP_VISUALIZE_MAXIMUM = 25


def _fixed_visualize_heatmap_maximum(layer):
    if layer is None:
        return None

    feature_count = layer.featureCount()
    if feature_count is None or feature_count < 0:
        return float(HEATMAP_VISUALIZE_MAXIMUM)
    if feature_count == 0:
        return None
    return float(min(HEATMAP_VISUALIZE_MAXIMUM, feature_count))


def build_qfit_heatmap_renderer(*, maximum_value=None):
    renderer = QgsHeatmapRenderer()
    renderer.setRadius(HEATMAP_ANALYSIS_RADIUS_M)
    renderer.setRadiusUnit(QgsUnitTypes.RenderMapUnits)
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
    if maximum_value is not None and maximum_value > 0:
        renderer.setMaximumValue(float(maximum_value))
    return renderer


def build_qfit_visualize_heatmap_renderer(
    *,
    radius_map_units=HEATMAP_VISUALIZE_RADIUS_M,
    maximum_value=HEATMAP_VISUALIZE_MAXIMUM,
):
    renderer = QgsHeatmapRenderer()
    renderer.setRadius(radius_map_units)
    renderer.setRadiusUnit(QgsUnitTypes.RenderMapUnits)
    renderer.setRenderQuality(2)
    heat_ramp = QgsGradientColorRamp(
        QColor("#00000000"),
        QColor(244, 81, 30, 255),
        False,
        [
            QgsGradientStop(0.08, QColor("#00000000")),
            QgsGradientStop(0.22, QColor(33, 150, 243, 110)),
            QgsGradientStop(0.48, QColor(255, 179, 0, 220)),
            QgsGradientStop(0.78, QColor(244, 81, 30, 255)),
        ],
    )
    renderer.setColorRamp(heat_ramp)
    if maximum_value is not None and maximum_value > 0:
        renderer.setMaximumValue(float(maximum_value))
    return renderer


class LayerStyleService:
    """Applies visual styles (renderers, opacity) to qfit output layers.

    Extracted from ``LayerManager`` so that styling logic can be tested and
    evolved independently of layer-loading and canvas management.
    """

    def apply_style(
        self,
        activities_layer,
        starts_layer,
        points_layer,
        atlas_layer,
        preset=None,
        background_preset_name=None,
        *,
        render_plan: RenderPlan | None = None,
    ):
        basemap_preset_name = background_preset_name or self._infer_background_preset_name()
        render_plan = render_plan or build_render_plan(
            preset or DEFAULT_RENDER_PRESET,
            has_start_features=self._has_features(starts_layer),
            has_point_features=self._has_features(points_layer),
            has_points_layer=points_layer is not None,
            background_preset_name=basemap_preset_name,
        )

        self._apply_layer_render_plan(activities_layer, render_plan.activities, basemap_preset_name)
        self._apply_layer_render_plan(starts_layer, render_plan.starts, basemap_preset_name)
        self._apply_layer_render_plan(points_layer, render_plan.points, basemap_preset_name)

        if atlas_layer is not None:
            self._apply_layer_render_plan(atlas_layer, render_plan.atlas, basemap_preset_name)

    def _apply_layer_render_plan(self, layer, layer_plan, basemap_preset_name):
        if layer is None or layer_plan is None:
            return
        self._apply_renderer_family(
            layer,
            layer_plan.renderer_family,
            basemap_preset_name,
            subtle=layer_plan.subtle,
            size=layer_plan.size,
        )
        if not layer_plan.visible:
            layer.setOpacity(0.0)
            layer.triggerRepaint()

    def _apply_renderer_family(
        self,
        layer,
        renderer_family,
        basemap_preset_name,
        *,
        subtle=False,
        size=None,
    ):
        if renderer_family == RENDERER_SIMPLE_LINES:
            self._apply_simple_line_style(layer, basemap_preset_name, subtle=subtle)
            return
        if renderer_family == RENDERER_CATEGORIZED_LINES:
            self._apply_categorized_line_style(layer, basemap_preset_name)
            return
        if renderer_family == RENDERER_TRACK_POINTS:
            self._apply_track_point_style(layer, subtle=subtle)
            return
        if renderer_family == RENDERER_START_POINTS:
            self._apply_start_point_style(layer, subtle=subtle)
            return
        if renderer_family == RENDERER_CATEGORIZED_POINTS:
            self._apply_categorized_point_style(layer, basemap_preset_name, size=size or "1.8")
            return
        if renderer_family == RENDERER_HEATMAP:
            self._apply_heatmap_style(layer)
            return
        if renderer_family == RENDERER_CLUSTERISH:
            self._apply_clusterish_style(layer)
            return
        if renderer_family == RENDERER_ATLAS_PAGE:
            self._apply_atlas_page_style(layer)
            return
        raise ValueError("Unsupported renderer family: {family}".format(family=renderer_family))

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
        layer.setRenderer(
            build_qfit_visualize_heatmap_renderer(
                radius_map_units=HEATMAP_VISUALIZE_RADIUS_M,
                maximum_value=_fixed_visualize_heatmap_maximum(layer),
            )
        )
        layer.setOpacity(1.0)
        layer.triggerRepaint()

    def _has_features(self, layer):
        return layer is not None and layer.featureCount() > 0

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
