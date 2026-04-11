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

    heatmap_layer = _build_memory_heatmap_layer(source_layer)
    features = _collect_heatmap_features(points_layer, activities_layer)

    if not features:
        return None, 0

    heatmap_layer.dataProvider().addFeatures(features)
    heatmap_layer.updateExtents()
    heatmap_layer.setRenderer(build_qfit_visualize_heatmap_renderer())
    heatmap_layer.setOpacity(1.0)
    heatmap_layer.triggerRepaint()
    return heatmap_layer, len(features)


def _build_memory_heatmap_layer(source_layer):
    layer_crs = source_layer.crs()
    authid = (
        layer_crs.authid()
        if layer_crs is not None and layer_crs.isValid()
        else "EPSG:3857"
    )
    return QgsVectorLayer(
        f"Point?crs={authid}",
        ACTIVITY_HEATMAP_LAYER_NAME,
        "memory",
    )


def _collect_heatmap_features(points_layer, activities_layer):
    if _has_features(points_layer):
        return list(_point_features_from_points_layer(points_layer))
    if _has_features(activities_layer):
        return list(_point_features_from_activity_layer(activities_layer))
    return []


def _point_features_from_points_layer(points_layer):
    for source_feature in points_layer.getFeatures():
        geometry = source_feature.geometry()
        if geometry is None or geometry.isEmpty():
            continue
        point = geometry.asPoint()
        if point.isEmpty():
            continue
        yield _build_point_feature(point.x(), point.y())


def _point_features_from_activity_layer(activities_layer):
    for source_feature in activities_layer.getFeatures():
        geometry = source_feature.geometry()
        if geometry is None or geometry.isEmpty():
            continue
        for vertex in geometry.vertices():
            yield _build_point_feature(vertex.x(), vertex.y())


def _build_point_feature(x, y):
    feature = QgsFeature()
    feature.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(x, y)))
    return feature


def _has_features(layer):
    return layer is not None and layer.isValid() and layer.featureCount() > 0


def _preferred_source_layer(points_layer, activities_layer):
    if _has_features(points_layer):
        return points_layer
    if _has_features(activities_layer):
        return activities_layer
    return None
