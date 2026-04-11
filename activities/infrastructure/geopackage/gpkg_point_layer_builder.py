"""
GeoPackage activity-point layer builder for qfit.

This module provides the standalone ``build_point_layer`` function plus the
point-stream sampling helpers it depends on. It contains no I/O — callers are
responsible for writing the returned layer to disk.

The remaining geometry and atlas builders live in :mod:`gpkg_layer_builders`.
"""

from qgis.core import (
    QgsFeature,
    QgsGeometry,
    QgsPointXY,
    QgsVectorLayer,
)

from .gpkg_schema import (
    POINT_FIELDS,
    make_qgs_fields,
)
from ....polyline_utils import decode_polyline
from ....time_utils import add_seconds_iso


def build_point_layer(records, write_activity_points=False, point_stride=1):
    """Build and return a memory ``QgsVectorLayer`` of per-point stream data."""
    layer = QgsVectorLayer("Point?crs=EPSG:4326", "activity_points", "memory")
    provider = layer.dataProvider()
    provider.addAttributes(make_qgs_fields(POINT_FIELDS))
    layer.updateFields()

    features = []
    if not write_activity_points:
        provider.addFeatures(features)
        layer.updateExtents()
        return layer

    stride = max(1, int(point_stride or 1))
    for index, record in enumerate(records, start=1):
        source_points, geometry_source = _activity_point_sequence(record)
        if len(source_points) < 1:
            continue

        stream_metrics = _stream_metrics(record, geometry_source)
        sampled_points = _sample_points(source_points, stride)
        total_points = max(1, len(source_points) - 1)
        for point_index, lat, lon in sampled_points:
            stream_time_s = _metric_value(stream_metrics, "time", point_index, as_int=True)
            feature = QgsFeature(layer.fields())
            feature.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(float(lon), float(lat))))
            feature["activity_fk"] = index
            feature["source"] = record.get("source")
            feature["source_activity_id"] = record.get("source_activity_id")
            feature["point_index"] = point_index
            feature["point_ratio"] = float(point_index) / float(total_points)
            feature["stream_time_s"] = stream_time_s
            feature["point_timestamp_utc"] = add_seconds_iso(record.get("start_date"), stream_time_s)
            feature["point_timestamp_local"] = add_seconds_iso(record.get("start_date_local"), stream_time_s)
            feature["stream_distance_m"] = _metric_value(stream_metrics, "distance", point_index)
            feature["altitude_m"] = _metric_value(stream_metrics, "altitude", point_index)
            feature["heartrate_bpm"] = _metric_value(stream_metrics, "heartrate", point_index)
            feature["cadence_rpm"] = _metric_value(stream_metrics, "cadence", point_index)
            feature["watts"] = _metric_value(stream_metrics, "watts", point_index)
            feature["velocity_mps"] = _metric_value(stream_metrics, "velocity_smooth", point_index)
            feature["temp_c"] = _metric_value(stream_metrics, "temp", point_index)
            feature["grade_smooth_pct"] = _metric_value(stream_metrics, "grade_smooth", point_index)
            feature["moving"] = _metric_value(stream_metrics, "moving", point_index, as_int=True)
            feature["name"] = record.get("name")
            feature["activity_type"] = record.get("activity_type")
            feature["start_date"] = record.get("start_date")
            feature["distance_m"] = record.get("distance_m")
            feature["geometry_source"] = geometry_source
            feature["last_synced_at"] = record.get("last_synced_at")
            features.append(feature)

    provider.addFeatures(features)
    layer.updateExtents()
    return layer


def _sample_points(points, stride):
    if not points:
        return []
    if stride <= 1:
        return [(index, lat, lon) for index, (lat, lon) in enumerate(points)]

    sampled_indexes = list(range(0, len(points), stride))
    if sampled_indexes[-1] != len(points) - 1:
        sampled_indexes.append(len(points) - 1)
    return [(index, points[index][0], points[index][1]) for index in sampled_indexes]


def _activity_point_sequence(record):
    geometry_points = _normalized_points(record.get("geometry_points") or [])
    if geometry_points:
        return geometry_points, "stream"

    polyline_points = _normalized_points(decode_polyline(record.get("summary_polyline")))
    if polyline_points:
        return polyline_points, "summary_polyline"

    fallback_points = _normalized_points(_fallback_points(record))
    if fallback_points:
        return fallback_points, "start_end"

    return [], None


def _fallback_points(record):
    start_lat = record.get("start_lat")
    start_lon = record.get("start_lon")
    end_lat = record.get("end_lat")
    end_lon = record.get("end_lon")
    if None in (start_lat, start_lon, end_lat, end_lon):
        return []
    return [(start_lat, start_lon), (end_lat, end_lon)]


def _normalized_points(points):
    normalized = []
    for point in points or []:
        if not isinstance(point, (list, tuple)) or len(point) < 2:
            continue
        try:
            normalized.append((float(point[0]), float(point[1])))
        except (TypeError, ValueError):
            continue
    return normalized


def _stream_metrics(record, geometry_source):
    if geometry_source != "stream":
        return {}
    return ((record.get("details_json") or {}).get("stream_metrics") or {})


def _metric_value(stream_metrics, key, index, as_int=False):
    values = stream_metrics.get(key) if isinstance(stream_metrics, dict) else None
    if not isinstance(values, list) or index >= len(values):
        return None
    value = values[index]
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value) if as_int else value
    if as_int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
