from __future__ import annotations

from qgis.PyQt.QtCore import QVariant
from qgis.PyQt.QtGui import QColor
from qgis.core import (
    QgsCategorizedSymbolRenderer,
    QgsFeature,
    QgsField,
    QgsGeometry,
    QgsLineSymbol,
    QgsPointXY,
    QgsRendererCategory,
    QgsSimpleLineSymbolLayer,
    QgsVectorLayer,
)

from ..application.slope_grade_analysis import (
    SLOPE_GRADE_CLASSES,
    build_activity_slope_grade_line_segments,
    build_slope_grade_analysis_plan,
)

SLOPE_GRADE_LAYER_NAME = "qfit slope grade lines"


def build_slope_grade_layer(
    *,
    activities_layer=None,
    points_layer=None,
):
    """Create a styled memory line layer for slope-grade analysis segments."""

    plan = build_slope_grade_analysis_plan(
        activities_layer=activities_layer,
        points_layer=points_layer,
    )
    line_segments = []
    if _plan_enables_layer(plan, "activity_tracks"):
        line_segments.extend(build_activity_slope_grade_line_segments(points_layer))

    if not line_segments:
        return None, ()

    layer = _build_memory_layer(points_layer)
    provider = layer.dataProvider()
    provider.addAttributes(
        [
            QgsField("layer_key", QVariant.String),
            QgsField("layer_label", QVariant.String),
            QgsField("source", QVariant.String),
            QgsField("source_id", QVariant.String),
            QgsField("grade_class", QVariant.String),
            QgsField("grade_label", QVariant.String),
            QgsField("grade_percent", QVariant.Double),
            QgsField("start_distance_m", QVariant.Double),
            QgsField("end_distance_m", QVariant.Double),
        ]
    )
    layer.updateFields()

    provider.addFeatures(_features_for_segments(layer, line_segments))
    layer.updateExtents()
    _apply_slope_grade_style(layer)
    return layer, tuple(line_segments)


def _plan_enables_layer(plan, layer_key):
    return any(layer.key == layer_key for layer in plan.enabled_layers)


def _build_memory_layer(source_layer):
    crs = _layer_crs(source_layer)
    authid = crs.authid() if crs is not None and crs.isValid() else "EPSG:4326"
    return QgsVectorLayer(
        f"LineString?crs={authid}",
        SLOPE_GRADE_LAYER_NAME,
        "memory",
    )



def _layer_crs(layer):
    crs = getattr(layer, "crs", None)
    return crs() if callable(crs) else None


def _features_for_segments(layer, line_segments):
    features = []
    for line_segment in line_segments:
        feature = QgsFeature(layer.fields())
        feature.setGeometry(
            QgsGeometry.fromPolylineXY(
                [
                    QgsPointXY(*line_segment.start_xy),
                    QgsPointXY(*line_segment.end_xy),
                ]
            )
        )
        feature["layer_key"] = line_segment.layer_key
        feature["layer_label"] = line_segment.layer_label
        feature["source"] = _string_or_empty(line_segment.source)
        feature["source_id"] = _string_or_empty(line_segment.source_id)
        feature["grade_class"] = line_segment.grade_class.key
        feature["grade_label"] = line_segment.grade_class.label
        feature["grade_percent"] = line_segment.grade_percent
        feature["start_distance_m"] = line_segment.start_distance_m
        feature["end_distance_m"] = line_segment.end_distance_m
        features.append(feature)
    return features


def _string_or_empty(value):
    return "" if value is None else str(value)


def _apply_slope_grade_style(layer):
    categories = []
    for grade_class in SLOPE_GRADE_CLASSES:
        symbol = _build_slope_grade_symbol(grade_class.color_hex)
        categories.append(
            QgsRendererCategory(grade_class.key, symbol, grade_class.label)
        )
    layer.setRenderer(QgsCategorizedSymbolRenderer("grade_class", categories))
    layer.setOpacity(0.95)
    layer.triggerRepaint()


def _build_slope_grade_symbol(color_hex):
    symbol = QgsLineSymbol()
    symbol.deleteSymbolLayer(0)
    line_layer = QgsSimpleLineSymbolLayer()
    line_layer.setColor(QColor(color_hex))
    line_layer.setWidth(0.9)
    symbol.appendSymbolLayer(line_layer)
    return symbol


__all__ = [
    "SLOPE_GRADE_LAYER_NAME",
    "build_slope_grade_layer",
]
