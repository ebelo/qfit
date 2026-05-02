"""
GeoPackage route-catalog layer builders for qfit.

Routes are intentionally separate from completed activity layers.  Tracks use
stable ``source`` + ``source_route_id`` identity, with ``route_fk`` encoded as
compact JSON for joins to spatial route sample points.  Profile samples also
keep the provider identity so consumers do not need to rely on layer order.
"""

import json

from qgis.core import (
    QgsFeature,
    QgsGeometry,
    QgsPoint,
    QgsPointXY,
    QgsVectorLayer,
)

from .gpkg_schema import (
    ROUTE_POINT_FIELDS,
    ROUTE_PROFILE_SAMPLE_FIELDS,
    ROUTE_TRACK_FIELDS,
    make_qgs_fields,
)
from ....polyline_utils import decode_polyline


__all__ = [
    "build_route_point_layer",
    "build_route_profile_sample_layer",
    "build_route_track_layer",
    "route_feature_key",
    "route_tracks_have_elevation",
    "_route_geometry",
]


def build_route_track_layer(records):
    """Build the saved-route track layer."""
    layer = QgsVectorLayer("LineString?crs=EPSG:4326", "route_tracks", "memory")
    provider = layer.dataProvider()
    provider.addAttributes(make_qgs_fields(ROUTE_TRACK_FIELDS))
    layer.updateFields()

    features = []
    for record in records:
        route_key = route_feature_key(record)
        if route_key is None:
            continue

        (
            geometry,
            geometry_source,
            point_count,
            profile_point_count,
            route_has_z,
        ) = _route_geometry(record)
        if geometry is None:
            continue

        feature = QgsFeature(layer.fields())
        feature.setGeometry(geometry)
        feature["route_fk"] = route_key
        feature["source"] = record.get("source")
        feature["source_route_id"] = record.get("source_route_id")
        feature["external_id"] = record.get("external_id")
        feature["name"] = record.get("name")
        feature["description"] = record.get("description")
        feature["private"] = _int_or_none(record.get("private"))
        feature["starred"] = _int_or_none(record.get("starred"))
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
        feature["geometry_point_count"] = point_count
        feature["profile_point_count"] = profile_point_count
        feature["has_elevation"] = int(route_has_z)
        feature["details_json"] = json.dumps(
            record.get("details_json") or {},
            sort_keys=True,
        )
        feature["summary_hash"] = record.get("summary_hash")
        feature["first_seen_at"] = record.get("first_seen_at")
        feature["last_synced_at"] = record.get("last_synced_at")
        features.append(feature)

    provider.addFeatures(features)
    layer.updateExtents()
    return layer


def build_route_point_layer(records):
    """Build a spatial point layer of ordered saved-route samples."""
    layer = QgsVectorLayer("Point?crs=EPSG:4326", "route_points", "memory")
    provider = layer.dataProvider()
    provider.addAttributes(make_qgs_fields(ROUTE_POINT_FIELDS))
    layer.updateFields()

    features = []
    for record in records:
        route_key = route_feature_key(record)
        if route_key is None:
            continue

        track_geometry, geometry_source, *_ = _route_geometry(record)
        if track_geometry is None:
            continue

        for point in _profile_points(record):
            lat = point.get("lat")
            lon = point.get("lon")
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
            feature["point_index"] = int(point.get("point_index") or 0)
            feature["segment_index"] = int(point.get("segment_index") or 0)
            feature["distance_m"] = _float_or_none(point.get("distance_m"))
            feature["altitude_m"] = _float_or_none(point.get("altitude_m"))
            feature["geometry_source"] = geometry_source
            features.append(feature)

    provider.addFeatures(features)
    layer.updateExtents()
    return layer


def build_route_profile_sample_layer(records):
    """Build a geometry-less table of ordered route profile samples."""
    layer = QgsVectorLayer("None", "route_profile_samples", "memory")
    provider = layer.dataProvider()
    provider.addAttributes(make_qgs_fields(ROUTE_PROFILE_SAMPLE_FIELDS))
    layer.updateFields()

    features = []
    sample_group_index = 0
    for record in records:
        if route_feature_key(record) is None:
            continue
        sample_group_index += 1
        for sample in _profile_points(record):
            feature = QgsFeature(layer.fields())
            feature["sample_group_index"] = sample_group_index
            feature["source"] = record.get("source")
            feature["source_route_id"] = record.get("source_route_id")
            feature["name"] = record.get("name")
            feature["point_index"] = int(sample.get("point_index") or 0)
            feature["segment_index"] = int(sample.get("segment_index") or 0)
            feature["lat"] = _float_or_none(sample.get("lat"))
            feature["lon"] = _float_or_none(sample.get("lon"))
            feature["distance_m"] = _float_or_none(sample.get("distance_m"))
            feature["altitude_m"] = _float_or_none(sample.get("altitude_m"))
            feature["last_synced_at"] = record.get("last_synced_at")
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


def route_tracks_have_elevation(records):
    return any(_record_has_elevation(record) for record in records)


def _route_geometry(record, force_z=False):
    profile_points = _profile_points(record)
    profile_point_count = len(profile_points)
    route_has_z = _profile_points_have_complete_elevation(profile_points)

    result = _geometry_from_profile_points(
        record,
        profile_points,
        route_has_z,
        force_z,
    )
    if result[0] is not None:
        return result

    result = _geometry_from_lat_lon_pairs(
        record.get("geometry_points") or [],
        record.get("geometry_source") or "geometry_points",
        profile_point_count,
        route_has_z,
    )
    if result[0] is not None:
        return result

    result = _geometry_from_lat_lon_pairs(
        decode_polyline(record.get("summary_polyline")),
        record.get("geometry_source") or "summary_polyline",
        profile_point_count,
        route_has_z,
    )
    if result[0] is not None:
        return result

    geometry = _fallback_route_geometry(record)
    if geometry is not None:
        return geometry, record.get("geometry_source") or "start_end", 2, 0, False

    return None, None, 0, profile_point_count, route_has_z


def _geometry_from_profile_points(record, points, route_has_z, force_z):
    valid_points = [
        point for point in points
        if point.get("lat") is not None and point.get("lon") is not None
    ]
    if len(valid_points) < 2:
        return None, None, len(valid_points), len(points), route_has_z

    if force_z and route_has_z:
        geometry = QgsGeometry.fromPolyline([
            QgsPoint(
                float(point.get("lon")),
                float(point.get("lat")),
                float(point.get("altitude_m")),
            )
            for point in valid_points
        ])
    else:
        geometry = QgsGeometry.fromPolylineXY([
            QgsPointXY(float(point.get("lon")), float(point.get("lat")))
            for point in valid_points
        ])

    return (
        geometry,
        record.get("geometry_source") or "profile",
        len(valid_points),
        len(points),
        route_has_z,
    )


def _geometry_from_lat_lon_pairs(
    points,
    geometry_source,
    profile_point_count,
    route_has_z,
):
    valid_points = [
        QgsPointXY(float(lon), float(lat))
        for lat, lon in points
        if lat is not None and lon is not None
    ]
    if len(valid_points) < 2:
        return None, None, len(valid_points), profile_point_count, route_has_z
    return (
        QgsGeometry.fromPolylineXY(valid_points),
        geometry_source,
        len(valid_points),
        profile_point_count,
        False,
    )


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


def _profile_points(record):
    return [
        _profile_point_mapping(point)
        for point in (record.get("profile_points") or [])
    ]


def _profile_point_mapping(point):
    if hasattr(point, "__dataclass_fields__"):
        return {
            "point_index": point.point_index,
            "lat": point.lat,
            "lon": point.lon,
            "distance_m": point.distance_m,
            "segment_index": point.segment_index,
            "altitude_m": point.altitude_m,
        }
    return dict(point)


def _record_has_elevation(record):
    return _profile_points_have_complete_elevation(_profile_points(record))


def _profile_points_have_complete_elevation(profile_points):
    valid_points = [
        point for point in profile_points
        if point.get("lat") is not None and point.get("lon") is not None
    ]
    return len(valid_points) >= 2 and all(
        _has_valid_elevation(point) for point in valid_points
    )


def _has_valid_elevation(point):
    try:
        float(point.get("altitude_m"))
    except (TypeError, ValueError):
        return False
    return True


def _float_or_none(value):
    if value is None:
        return None
    return float(value)


def _int_or_none(value):
    if value is None:
        return None
    return int(bool(value))
