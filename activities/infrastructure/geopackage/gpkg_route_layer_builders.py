"""
GeoPackage route catalog layer builders for qfit.

This module builds in-memory QGIS layers for saved/planned routes.  It does
not perform GeoPackage I/O; storage orchestration can write the returned layers
once route catalog persistence is wired in.
"""

import json

from qgis.core import (
    QgsFeature,
    QgsGeometry,
    QgsPointXY,
    QgsVectorLayer,
)

from .gpkg_schema import (
    ROUTE_POINT_FIELDS,
    ROUTE_TRACK_FIELDS,
    make_qgs_fields,
)
from ....polyline_utils import decode_polyline

__all__ = [
    "build_route_point_layer",
    "build_route_track_layer",
    "route_feature_key",
    "_route_geometry",
]


def build_route_track_layer(records):
    """Build and return a memory ``QgsVectorLayer`` of saved route tracks."""
    layer = QgsVectorLayer(
        "LineString?crs=EPSG:4326",
        "route_tracks",
        "memory",
    )
    provider = layer.dataProvider()
    provider.addAttributes(make_qgs_fields(ROUTE_TRACK_FIELDS))
    layer.updateFields()

    features = []
    for record in records:
        geometry, geometry_source, geometry_point_count = _route_geometry(
            record
        )
        route_key = route_feature_key(record)
        if geometry is None or route_key is None:
            continue

        feature = QgsFeature(layer.fields())
        feature.setGeometry(geometry)
        feature["route_fk"] = route_key
        feature["source"] = record.get("source")
        feature["source_route_id"] = record.get("source_route_id")
        feature["external_id"] = record.get("external_id")
        feature["name"] = record.get("name")
        feature["description"] = record.get("description")
        feature["private"] = _bool_as_int(record.get("private"))
        feature["starred"] = _bool_as_int(record.get("starred"))
        feature["distance_m"] = record.get("distance_m")
        feature["elevation_gain_m"] = record.get("elevation_gain_m")
        feature["estimated_moving_time_s"] = record.get(
            "estimated_moving_time_s"
        )
        feature["route_type"] = record.get("route_type")
        feature["sub_type"] = record.get("sub_type")
        feature["created_at"] = record.get("created_at")
        feature["updated_at"] = record.get("updated_at")
        feature["summary_polyline"] = record.get("summary_polyline")
        feature["geometry_source"] = geometry_source
        feature["geometry_point_count"] = geometry_point_count
        feature["details_json"] = json.dumps(
            record.get("details_json") or {},
            sort_keys=True,
        )
        features.append(feature)

    provider.addFeatures(features)
    layer.updateExtents()
    return layer


def build_route_point_layer(records):
    """Build and return a memory ``QgsVectorLayer`` of saved route samples."""
    layer = QgsVectorLayer("Point?crs=EPSG:4326", "route_points", "memory")
    provider = layer.dataProvider()
    provider.addAttributes(make_qgs_fields(ROUTE_POINT_FIELDS))
    layer.updateFields()

    features = []
    for record in records:
        route_key = route_feature_key(record)
        if route_key is None:
            continue

        track_geometry, _, _ = _route_geometry(record)
        if track_geometry is None:
            continue

        profile_points = record.get("profile_points") or []
        for point in profile_points:
            lat = _point_value(point, "lat")
            lon = _point_value(point, "lon")
            if lat is None or lon is None:
                continue

            feature = QgsFeature(layer.fields())
            feature.setGeometry(
                QgsGeometry.fromPointXY(QgsPointXY(float(lon), float(lat)))
            )
            feature["route_fk"] = route_key
            feature["source"] = record.get("source")
            feature["source_route_id"] = record.get("source_route_id")
            feature["name"] = record.get("name")
            feature["point_index"] = _point_value(point, "point_index")
            feature["segment_index"] = (
                _point_value(point, "segment_index") or 0
            )
            feature["distance_m"] = _point_value(point, "distance_m")
            feature["altitude_m"] = _point_value(point, "altitude_m")
            feature["geometry_source"] = (
                record.get("geometry_source") or "profile"
            )
            features.append(feature)

    provider.addFeatures(features)
    layer.updateExtents()
    return layer


def route_feature_key(record):
    """Return the stable feature key used to join route tracks and samples."""
    source = record.get("source")
    source_route_id = record.get("source_route_id")
    if source in (None, "") or source_route_id in (None, ""):
        return None
    return json.dumps(
        [str(source), str(source_route_id)],
        separators=(",", ":"),
    )


def _route_geometry(record):
    profile_points = record.get("profile_points") or []
    geometry, point_count = _geometry_from_profile_points(profile_points)
    if geometry is not None:
        return (
            geometry,
            record.get("geometry_source") or "profile",
            point_count,
        )

    geometry_points = record.get("geometry_points") or []
    geometry, point_count = _geometry_from_lat_lon_pairs(geometry_points)
    if geometry is not None:
        return (
            geometry,
            record.get("geometry_source") or "geometry_points",
            point_count,
        )

    polyline_points = decode_polyline(record.get("summary_polyline"))
    geometry, point_count = _geometry_from_lat_lon_pairs(polyline_points)
    if geometry is not None:
        return (
            geometry,
            record.get("geometry_source") or "summary_polyline",
            point_count,
        )

    geometry = _fallback_route_geometry(record)
    if geometry is not None:
        return geometry, record.get("geometry_source") or "start_end", 2

    return None, None, 0


def _geometry_from_profile_points(points):
    lat_lon_pairs = [
        (_point_value(point, "lat"), _point_value(point, "lon"))
        for point in points
    ]
    return _geometry_from_lat_lon_pairs(lat_lon_pairs)


def _geometry_from_lat_lon_pairs(points):
    valid_points = [
        QgsPointXY(float(lon), float(lat))
        for lat, lon in points
        if lat is not None and lon is not None
    ]
    if len(valid_points) < 2:
        return None, len(valid_points)
    return QgsGeometry.fromPolylineXY(valid_points), len(valid_points)


def _fallback_route_geometry(record):
    start_lat = record.get("start_lat")
    start_lon = record.get("start_lon")
    end_lat = record.get("end_lat")
    end_lon = record.get("end_lon")
    if None in (start_lat, start_lon, end_lat, end_lon):
        return None
    return QgsGeometry.fromPolylineXY([
        QgsPointXY(start_lon, start_lat),
        QgsPointXY(end_lon, end_lat),
    ])


def _point_value(point, key):
    if isinstance(point, dict):
        return point.get(key)
    return getattr(point, key, None)


def _bool_as_int(value):
    if value is None:
        return None
    return int(bool(value))
