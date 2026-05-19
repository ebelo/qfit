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

from ..application.power_output_analysis import (
    POWER_OUTPUT_CLASSES,
    build_activity_power_output_line_segments,
    build_power_output_analysis_plan,
)

POWER_OUTPUT_LAYER_NAME = "qfit power output lines"


def build_power_output_layer(
    *,
    activities_layer=None,
    points_layer=None,
    **route_layers,
):
    """Create a styled memory line layer for activity power-output segments."""

    plan = build_power_output_analysis_plan(
        activities_layer=activities_layer,
        points_layer=points_layer,
        **route_layers,
    )
    line_segments = []
    if _plan_enables_layer(plan, "activity_tracks"):
        line_segments.extend(
            build_activity_power_output_line_segments(points_layer)
        )

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
            QgsField("power_class", QVariant.String),
            QgsField("power_label", QVariant.String),
            QgsField("watts", QVariant.Double),
            QgsField("start_distance_m", QVariant.Double),
            QgsField("end_distance_m", QVariant.Double),
        ]
    )
    layer.updateFields()

    provider.addFeatures(_features_for_segments(layer, line_segments))
    layer.updateExtents()
    _apply_power_output_style(layer)
    return layer, tuple(line_segments)


def _plan_enables_layer(plan, layer_key):
    return any(layer.key == layer_key for layer in plan.enabled_layers)


def _build_memory_layer(source_layer):
    crs = _layer_crs(source_layer)
    authid = crs.authid() if crs is not None and crs.isValid() else "EPSG:4326"
    return QgsVectorLayer(
        f"LineString?crs={authid}",
        POWER_OUTPUT_LAYER_NAME,
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
        feature["power_class"] = line_segment.power_class.key
        feature["power_label"] = line_segment.power_class.label
        feature["watts"] = line_segment.watts
        feature["start_distance_m"] = line_segment.start_distance_m
        feature["end_distance_m"] = line_segment.end_distance_m
        features.append(feature)
    return features


def _string_or_empty(value):
    return "" if value is None else str(value)


def _apply_power_output_style(layer):
    categories = []
    for power_class in POWER_OUTPUT_CLASSES:
        symbol = _build_power_output_symbol(power_class.color_hex)
        categories.append(
            QgsRendererCategory(power_class.key, symbol, power_class.label)
        )
    layer.setRenderer(QgsCategorizedSymbolRenderer("power_class", categories))
    layer.setOpacity(0.95)
    layer.triggerRepaint()


def _build_power_output_symbol(color_hex):
    symbol = QgsLineSymbol()
    symbol.deleteSymbolLayer(0)
    line_layer = QgsSimpleLineSymbolLayer()
    line_layer.setColor(QColor(color_hex))
    line_layer.setWidth(0.9)
    symbol.appendSymbolLayer(line_layer)
    return symbol


__all__ = [
    "POWER_OUTPUT_LAYER_NAME",
    "build_power_output_layer",
]
