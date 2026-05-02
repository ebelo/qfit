"""GeoPackage layer builders for saved/planned route catalog data."""

import json

from qgis.core import QgsFeature, QgsGeometry, QgsPoint, QgsPointXY, QgsVectorLayer

from ....activities.infrastructure.geopackage.gpkg_schema import (
    ROUTE_POINT_FIELDS,
    ROUTE_TRACK_FIELDS,
    make_qgs_fields,
)
from ....polyline_utils import decode_polyline


def build_route_track_layer(records):
    """Build a route track layer, using LineStringZ when altitude samples exist."""
    use_z = any(_record_has_altitude(record) for record in records)
    layer_type = "LineStringZ" if use_z else "LineString"
    layer = QgsVectorLayer(f"{layer_type}?crs=EPSG:4326", "route_tracks", "memory")
    provider = layer.dataProvider()
    provider.addAttributes(make_qgs_fields(ROUTE_TRACK_FIELDS))
    layer.updateFields()

    features = []
    for record in records:
        geometry, geometry_source, point_count = _route_geometry(record, force_z=use_z)
        if geometry is None:
            continue

        feature = QgsFeature(layer.fields())
        feature.setGeometry(geometry)
        _set_route_track_attributes(feature, record, geometry_source, point_count)
        features.append(feature)

    provider.addFeatures(features)
    layer.updateExtents()
    return layer


def build_route_point_layer(records):
    """Build an ordered route profile sample layer."""
    use_z = any(_record_has_altitude(record) for record in records)
    layer_type = "PointZ" if use_z else "Point"
    layer = QgsVectorLayer(f"{layer_type}?crs=EPSG:4326", "route_points", "memory")
    provider = layer.dataProvider()
    provider.addAttributes(make_qgs_fields(ROUTE_POINT_FIELDS))
    layer.updateFields()

    features = []
    for record in records:
        features.extend(_route_point_features(layer, record, use_z))

    provider.addFeatures(features)
    layer.updateExtents()
    return layer


def _set_route_track_attributes(feature, record, geometry_source, point_count):
    for field_name in [name for name, _field_type in ROUTE_TRACK_FIELDS]:
        if field_name == "geometry_source":
            feature[field_name] = geometry_source
        elif field_name == "geometry_point_count":
            feature[field_name] = point_count
        elif field_name == "details_json":
            feature[field_name] = json.dumps(record.get("details_json") or {}, sort_keys=True)
        elif field_name in {"starred", "private"}:
            value = record.get(field_name)
            feature[field_name] = None if value is None else int(bool(value))
        else:
            feature[field_name] = record.get(field_name)


def _route_geometry(record, force_z=False):
    route_points = _normalize_route_points(record.get("geometry_points") or [])
    geometry = _geometry_from_route_points(route_points, force_z=force_z)
    if geometry is not None:
        return geometry, "gpx", len(route_points)

    polyline_points = decode_polyline(record.get("summary_polyline"))
    geometry = _geometry_from_latlon_pairs(polyline_points, force_z=force_z)
    if geometry is not None:
        return geometry, "summary_polyline", len(polyline_points)

    geometry = _fallback_geometry(record, force_z=force_z)
    if geometry is not None:
        return geometry, "start_end", 2

    return None, None, 0


def _geometry_from_route_points(points, force_z=False):
    valid_points = [
        point for point in points
        if point.get("latitude") is not None and point.get("longitude") is not None
    ]
    if len(valid_points) < 2:
        return None
    if force_z:
        return QgsGeometry.fromPolyline([
            QgsPoint(float(point["longitude"]), float(point["latitude"]), _z_value(point.get("altitude_m")))
            for point in valid_points
        ])
    return QgsGeometry.fromPolylineXY([
        QgsPointXY(float(point["longitude"]), float(point["latitude"]))
        for point in valid_points
    ])


def _geometry_from_latlon_pairs(points, force_z=False):
    if len(points) < 2:
        return None
    if force_z:
        return QgsGeometry.fromPolyline([QgsPoint(float(lon), float(lat), 0.0) for lat, lon in points])
    return QgsGeometry.fromPolylineXY([QgsPointXY(float(lon), float(lat)) for lat, lon in points])


def _fallback_geometry(record, force_z=False):
    start_lat = record.get("start_lat")
    start_lon = record.get("start_lon")
    end_lat = record.get("end_lat")
    end_lon = record.get("end_lon")
    if None in (start_lat, start_lon, end_lat, end_lon):
        return None
    if force_z:
        return QgsGeometry.fromPolyline([
            QgsPoint(float(start_lon), float(start_lat), 0.0),
            QgsPoint(float(end_lon), float(end_lat), 0.0),
        ])
    return QgsGeometry.fromPolylineXY([
        QgsPointXY(float(start_lon), float(start_lat)),
        QgsPointXY(float(end_lon), float(end_lat)),
    ])


def _route_point_features(layer, record, use_z):
    points = _normalize_route_points(record.get("geometry_points") or [])
    if not points:
        return []
    route_fk = _stable_route_fk(record)
    max_distance = max((point.get("distance_m") or 0.0 for point in points), default=0.0)
    return [
        feature
        for point_index, point in enumerate(points)
        for feature in [_route_point_feature(layer, record, point, point_index, len(points), max_distance, route_fk, use_z)]
        if feature is not None
    ]


def _route_point_feature(layer, record, point, point_index, point_count, max_distance, route_fk, use_z):
    latitude = point.get("latitude")
    longitude = point.get("longitude")
    if latitude is None or longitude is None:
        return None
    altitude = point.get("altitude_m")
    feature = QgsFeature(layer.fields())
    feature.setGeometry(_point_geometry(latitude, longitude, altitude, use_z))
    feature["route_fk"] = route_fk
    feature["source"] = record.get("source")
    feature["source_route_id"] = record.get("source_route_id")
    feature["name"] = record.get("name")
    feature["route_type"] = record.get("route_type")
    feature["point_index"] = int(point.get("point_index", point_index))
    feature["point_ratio"] = _point_ratio(point.get("distance_m"), max_distance, point_index, point_count)
    feature["distance_m"] = point.get("distance_m")
    feature["altitude_m"] = altitude
    feature["geometry_source"] = record.get("geometry_source")
    feature["last_synced_at"] = record.get("last_synced_at")
    return feature


def _point_geometry(latitude, longitude, altitude, use_z):
    if use_z:
        return QgsGeometry(QgsPoint(float(longitude), float(latitude), _z_value(altitude)))
    return QgsGeometry.fromPointXY(QgsPointXY(float(longitude), float(latitude)))


def _normalize_route_points(points):
    return [_normalize_route_point(point, index) for index, point in enumerate(points)]


def _normalize_route_point(point, index):
    value = _route_point_record(point)
    if "latitude" not in value and "lat" in value:
        value["latitude"] = value.get("lat")
    if "longitude" not in value and "lon" in value:
        value["longitude"] = value.get("lon")
    value.setdefault("point_index", index)
    return value


def _route_point_record(point):
    if hasattr(point, "to_record"):
        return point.to_record()
    if isinstance(point, dict):
        return dict(point)
    if isinstance(point, (list, tuple)) and len(point) >= 2:
        return _tuple_route_point_record(point)
    return {}


def _tuple_route_point_record(point):
    value = {"latitude": point[0], "longitude": point[1]}
    if len(point) >= 3:
        value["altitude_m"] = point[2]
    return value


def _record_has_altitude(record):
    return any(point.get("altitude_m") is not None for point in _normalize_route_points(record.get("geometry_points") or []))


def _z_value(value):
    return 0.0 if value is None else float(value)


def _point_ratio(distance_m, max_distance, index, count):
    if distance_m is not None and max_distance and max_distance > 0:
        return float(distance_m) / float(max_distance)
    if count <= 1:
        return 0.0
    return float(index) / float(count - 1)


def _stable_route_fk(record):
    source = record.get("source") or ""
    route_id = record.get("source_route_id") or ""
    return f"{source}:{route_id}"
