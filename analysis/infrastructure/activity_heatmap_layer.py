from __future__ import annotations

from qgis.core import QgsFeature, QgsGeometry, QgsPointXY, QgsVectorLayer

from ...visualization.infrastructure.layer_style_service import (
    build_qfit_visualize_heatmap_renderer,
)

ACTIVITY_HEATMAP_LAYER_NAME = "qfit activity heatmap"


def build_activity_heatmap_layer(activities_layer=None, points_layer=None):
    """Build a memory point layer suitable for heatmap rendering.

    Prefer the existing sampled route-points layer when available. When it is
    missing, fall back to deriving sample points from the current activity-line
    layer so Heatmap analysis still works without pre-generated points.
    """

    source_layer = _preferred_source_layer(points_layer, activities_layer)
    if source_layer is None or not source_layer.isValid():
        return None, 0

    layer_crs = source_layer.crs()
    authid = layer_crs.authid() if layer_crs is not None and layer_crs.isValid() else "EPSG:3857"
    heatmap_layer = QgsVectorLayer(
        f"Point?crs={authid}",
        ACTIVITY_HEATMAP_LAYER_NAME,
        "memory",
    )
    provider = heatmap_layer.dataProvider()

    features = []
    if points_layer is not None and points_layer.isValid() and points_layer.featureCount() > 0:
        for source_feature in points_layer.getFeatures():
            geometry = source_feature.geometry()
            if geometry is None or geometry.isEmpty():
                continue
            point = geometry.asPoint()
            if point.isEmpty():
                continue
            feature = QgsFeature()
            feature.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(point.x(), point.y())))
            features.append(feature)
    else:
        for source_feature in activities_layer.getFeatures():
            geometry = source_feature.geometry()
            if geometry is None or geometry.isEmpty():
                continue
            for vertex in geometry.vertices():
                feature = QgsFeature()
                feature.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(vertex.x(), vertex.y())))
                features.append(feature)

    if not features:
        return None, 0

    provider.addFeatures(features)
    heatmap_layer.updateExtents()
    heatmap_layer.setRenderer(build_qfit_visualize_heatmap_renderer())
    heatmap_layer.setOpacity(1.0)
    heatmap_layer.triggerRepaint()
    return heatmap_layer, len(features)


def _preferred_source_layer(points_layer, activities_layer):
    if points_layer is not None and points_layer.isValid() and points_layer.featureCount() > 0:
        return points_layer
    if activities_layer is not None and activities_layer.isValid() and activities_layer.featureCount() > 0:
        return activities_layer
    return None
