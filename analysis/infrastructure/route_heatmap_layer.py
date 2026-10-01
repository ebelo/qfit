"""QGIS display adapter: fixed red ramp for an immutable cached raster."""
import math


def create_route_heatmap_layer(artifact):
    from qgis.PyQt.QtGui import QColor
    from qgis.core import (QgsRasterLayer, QgsRasterShader, QgsColorRampShader,
                           QgsSingleBandPseudoColorRenderer, QgsBilinearRasterResampler)
    from ...ui.qt_enum_compat import qt_class_enum_value

    layer = QgsRasterLayer(artifact.path, "qfit activity heatmap", "gdal")
    if not layer.isValid():
        raise ValueError("The cached heatmap raster could not be loaded")
    shader_function = QgsColorRampShader(0, artifact.maximum)
    shader_function.setColorRampType(qt_class_enum_value(QgsColorRampShader, "Type", "Interpolated"))
    stops = [(0, (0, 0, 0, 0)), (0.001, (252, 165, 165, 110)),
             (0.25, (248, 113, 113, 180)), (0.55, (239, 68, 68, 225)),
             (0.8, (220, 38, 38, 245)), (1, (153, 0, 0, 255))]
    items = [QgsColorRampShader.ColorRampItem(math.expm1(fraction * math.log1p(artifact.maximum)),
                                           QColor(*color), "Route usage") for fraction, color in stops]
    shader_function.setColorRampItemList(items)
    shader = QgsRasterShader(0, artifact.maximum)
    shader.setRasterShaderFunction(shader_function)
    renderer = QgsSingleBandPseudoColorRenderer(layer.dataProvider(), 1, shader)
    renderer.setClassificationMin(0)
    renderer.setClassificationMax(artifact.maximum)
    layer.setRenderer(renderer)
    layer.resampleFilter().setZoomedInResampler(QgsBilinearRasterResampler())
    layer.setCustomProperty("qfit/heatmap/cache_key", artifact.cache_key)
    layer.setCustomProperty("qfit/heatmap/activity_count", artifact.activity_count)
    layer.setCustomProperty("qfit/heatmap/maximum", artifact.maximum)
    return layer
