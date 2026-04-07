from __future__ import annotations

from qgis.PyQt.QtCore import QVariant
from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsFeature,
    QgsField,
    QgsGeometry,
    QgsMarkerSymbol,
    QgsPointXY,
    QgsProject,
    QgsProperty,
    QgsSingleSymbolRenderer,
    QgsSymbolLayer,
    QgsVectorLayer,
)

from ..application.frequent_start_points import StartPointSample, analyze_frequent_start_points

FREQUENT_STARTING_POINTS_LAYER_NAME = "qfit frequent starting points"
_METRIC_CRS = QgsCoordinateReferenceSystem("EPSG:3857")


def build_frequent_start_points_layer(starts_layer):
    """Create a styled memory layer for the most frequent starting-point clusters."""

    if starts_layer is None or not starts_layer.isValid():
        return None, []

    layer_crs = starts_layer.crs()
    if not layer_crs.isValid() or not layer_crs.authid():
        layer_crs = QgsCoordinateReferenceSystem("EPSG:4326")
    transform_context = QgsProject.instance().transformContext()
    to_metric = QgsCoordinateTransform(layer_crs, _METRIC_CRS, transform_context)
    from_metric = QgsCoordinateTransform(_METRIC_CRS, layer_crs, transform_context)

    samples = []
    for feature in starts_layer.getFeatures():
        geometry = feature.geometry()
        if geometry is None or geometry.isEmpty():
            continue
        point = geometry.asPoint()
        metric_point = to_metric.transform(QgsPointXY(point.x(), point.y()))
        samples.append(
            StartPointSample(
                x=metric_point.x(),
                y=metric_point.y(),
                source_activity_id=str(feature["source_activity_id"])
                if "source_activity_id" in feature.fields().names()
                else None,
            )
        )

    clusters, _radius_m = analyze_frequent_start_points(samples)

    layer = QgsVectorLayer(
        f"Point?crs={layer_crs.authid()}",
        FREQUENT_STARTING_POINTS_LAYER_NAME,
        "memory",
    )
    provider = layer.dataProvider()
    provider.addAttributes(
        [
            QgsField("rank", QVariant.Int),
            QgsField("activity_count", QVariant.Int),
            QgsField("marker_size", QVariant.Double),
        ]
    )
    layer.updateFields()

    features = []
    for cluster in clusters:
        display_point = from_metric.transform(QgsPointXY(cluster.center_x, cluster.center_y))
        feature = QgsFeature(layer.fields())
        feature.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(display_point.x(), display_point.y())))
        feature["rank"] = cluster.rank
        feature["activity_count"] = cluster.activity_count
        feature["marker_size"] = cluster.marker_size
        features.append(feature)

    provider.addFeatures(features)
    layer.updateExtents()
    _apply_analysis_style(layer)
    return layer, clusters


def _apply_analysis_style(layer):
    symbol = QgsMarkerSymbol.createSimple(
        {
            "name": "circle",
            "color": "255,235,59,235",
            "outline_color": "120,90,0,220",
            "outline_width": "0.5",
        }
    )
    symbol_layer = symbol.symbolLayer(0)
    if symbol_layer is not None:
        symbol_layer.setDataDefinedProperty(
            QgsSymbolLayer.PropertySize, QgsProperty.fromField("marker_size")
        )
    layer.setRenderer(QgsSingleSymbolRenderer(symbol))
    layer.setOpacity(0.95)
    layer.triggerRepaint()
