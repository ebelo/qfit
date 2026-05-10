from __future__ import annotations

from itertools import count
from math import log, pi, tan

from qgis.PyQt.QtCore import QVariant
from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsFeature,
    QgsField,
    QgsGeometry,
    QgsPointXY,
    QgsProject,
    QgsVectorLayer,
)

from ...visualization.infrastructure.layer_style_service import (
    build_qfit_visualize_heatmap_renderer,
)

ACTIVITY_HEATMAP_LAYER_NAME = "qfit activity heatmap"
_WEB_MERCATOR_AUTHID = "EPSG:3857"
_WGS84_AUTHID = "EPSG:4326"
_WEB_MERCATOR_HALF_WORLD_M = 20037508.342789244
_WEB_MERCATOR_EARTH_RADIUS_M = _WEB_MERCATOR_HALF_WORLD_M / pi
_WEB_MERCATOR_MAX_LAT = 85.05112878


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
    features = _collect_heatmap_features(heatmap_layer, points_layer, activities_layer)

    if not features:
        return None, 0

    heatmap_layer.dataProvider().addFeatures(features)
    heatmap_layer.updateExtents()
    heatmap_layer.setRenderer(
        build_qfit_visualize_heatmap_renderer(
            maximum_value=_heatmap_maximum_value(len(features)),
        )
    )
    heatmap_layer.setOpacity(1.0)
    heatmap_layer.triggerRepaint()
    return heatmap_layer, len(features)


def _build_memory_heatmap_layer(_source_layer):
    layer = QgsVectorLayer(
        f"Point?crs={_WEB_MERCATOR_AUTHID}",
        ACTIVITY_HEATMAP_LAYER_NAME,
        "memory",
    )
    layer.dataProvider().addAttributes(
        [
            QgsField("sample_index", QVariant.Int),
            QgsField("source_layer", QVariant.String),
            QgsField("source_feature_id", QVariant.Int),
            QgsField("source_activity_id", QVariant.String),
            QgsField("point_index", QVariant.Int),
        ]
    )
    layer.updateFields()
    return layer


def _collect_heatmap_features(heatmap_layer, points_layer, activities_layer):
    if _has_features(points_layer):
        return list(_point_features_from_points_layer(heatmap_layer, points_layer))
    if _has_features(activities_layer):
        return list(_point_features_from_activity_layer(heatmap_layer, activities_layer))
    return []


def _point_features_from_points_layer(heatmap_layer, points_layer):
    sample_indexes = count(1)
    for source_feature in points_layer.getFeatures():
        geometry = source_feature.geometry()
        if geometry is None or geometry.isEmpty():
            continue
        point = geometry.asPoint()
        if point.isEmpty():
            continue
        x, y = _heatmap_coordinates(points_layer, point)
        yield _build_point_feature(
            heatmap_layer,
            x=x,
            y=y,
            sample_index=next(sample_indexes),
            source_layer="activity_points",
            source_feature=source_feature,
            source_activity_id=_field_value(source_feature, "source_activity_id"),
            point_index=_field_value(source_feature, "point_index"),
        )


def _point_features_from_activity_layer(heatmap_layer, activities_layer):
    sample_indexes = count(1)
    for source_feature in activities_layer.getFeatures():
        geometry = source_feature.geometry()
        if geometry is None or geometry.isEmpty():
            continue
        for point_index, vertex in enumerate(geometry.vertices(), start=1):
            x, y = _heatmap_coordinates(activities_layer, vertex)
            yield _build_point_feature(
                heatmap_layer,
                x=x,
                y=y,
                sample_index=next(sample_indexes),
                source_layer="activity_tracks",
                source_feature=source_feature,
                source_activity_id=_field_value(source_feature, "source_activity_id"),
                point_index=point_index,
            )


def _build_point_feature(
    target_layer,
    *,
    x,
    y,
    sample_index,
    source_layer,
    source_feature,
    source_activity_id,
    point_index,
):
    feature = QgsFeature(target_layer.fields())
    feature.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(x, y)))
    feature["sample_index"] = sample_index
    feature["source_layer"] = source_layer
    feature["source_feature_id"] = _feature_id(source_feature)
    feature["source_activity_id"] = source_activity_id
    feature["point_index"] = point_index
    return feature


def _heatmap_coordinates(source_layer, point):
    x = float(point.x())
    y = float(point.y())
    authid = _layer_authid(source_layer)
    if authid == _WEB_MERCATOR_AUTHID:
        return x, y
    if authid == _WGS84_AUTHID:
        return _lon_lat_to_web_mercator(x, y)

    transform = _coordinate_transform_to_web_mercator(source_layer)
    if transform is None:
        return x, y
    transformed = transform.transform(QgsPointXY(x, y))
    return float(transformed.x()), float(transformed.y())


def _coordinate_transform_to_web_mercator(source_layer):
    source_crs = source_layer.crs() if source_layer is not None else None
    if source_crs is None or not source_crs.isValid():
        return None
    return QgsCoordinateTransform(
        source_crs,
        QgsCoordinateReferenceSystem(_WEB_MERCATOR_AUTHID),
        QgsProject.instance(),
    )


def _layer_authid(layer):
    crs = layer.crs() if layer is not None else None
    if crs is None or not crs.isValid():
        return _WEB_MERCATOR_AUTHID
    return crs.authid()


def _lon_lat_to_web_mercator(lon, lat):
    clamped_lat = max(-_WEB_MERCATOR_MAX_LAT, min(_WEB_MERCATOR_MAX_LAT, lat))
    x = lon * _WEB_MERCATOR_HALF_WORLD_M / 180.0
    y = _WEB_MERCATOR_EARTH_RADIUS_M * log(tan((90.0 + clamped_lat) * pi / 360.0))
    return x, y


def _heatmap_maximum_value(sample_count):
    if sample_count < 25:
        return 1
    if sample_count < 100:
        return 4
    return None


def _field_value(feature, field_name):
    fields = getattr(feature, "fields", lambda: None)()
    field_names = fields.names() if fields is not None and hasattr(fields, "names") else []
    if field_name not in field_names:
        return None
    try:
        return feature[field_name]
    except (KeyError, RuntimeError):
        return None


def _feature_id(feature):
    feature_id = getattr(feature, "id", None)
    return feature_id() if callable(feature_id) else None


def _has_features(layer):
    return layer is not None and layer.isValid() and layer.featureCount() > 0


def _preferred_source_layer(points_layer, activities_layer):
    if _has_features(points_layer):
        return points_layer
    if _has_features(activities_layer):
        return activities_layer
    return None
