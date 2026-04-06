"""
GeoPackage activity geometry-layer builders for qfit.

This module provides standalone functions that build the activity track and
start-point ``QgsVectorLayer`` objects from activity records. It contains no
I/O — callers are responsible for writing the returned layers to disk.

The atlas page polygon builder lives in :mod:`gpkg_atlas_page_builder`.
The activity-point builder lives in :mod:`gpkg_point_layer_builder`.
Geometry-less atlas helper tables live in :mod:`gpkg_atlas_table_builders`.
"""

import json

from qgis.core import (
    QgsFeature,
    QgsGeometry,
    QgsPointXY,
    QgsVectorLayer,
)

from .gpkg_schema import (
    START_FIELDS,
    TRACK_FIELDS,
    make_qgs_fields,
)
from ....polyline_utils import decode_polyline
from .gpkg_atlas_page_builder import build_atlas_layer  # re-export for backward compatibility

__all__ = [
    "build_atlas_layer",
    "build_start_layer",
    "build_track_layer",
    "_activity_geometry",
    "_fallback_geometry",
    "_geometry_from_points",
]


def build_track_layer(records):
    """Build and return a memory ``QgsVectorLayer`` of activity tracks."""
    layer = QgsVectorLayer("LineString?crs=EPSG:4326", "activity_tracks", "memory")
    provider = layer.dataProvider()
    provider.addAttributes(make_qgs_fields(TRACK_FIELDS))
    layer.updateFields()

    features = []
    for record in records:
        geometry, geometry_source, geometry_point_count = _activity_geometry(record)
        if geometry is None:
            continue

        feature = QgsFeature(layer.fields())
        feature.setGeometry(geometry)
        feature["source"] = record.get("source")
        feature["source_activity_id"] = record.get("source_activity_id")
        feature["external_id"] = record.get("external_id")
        feature["name"] = record.get("name")
        feature["activity_type"] = record.get("activity_type")
        feature["sport_type"] = record.get("sport_type")
        feature["start_date"] = record.get("start_date")
        feature["start_date_local"] = record.get("start_date_local")
        feature["timezone"] = record.get("timezone")
        feature["distance_m"] = record.get("distance_m")
        feature["moving_time_s"] = record.get("moving_time_s")
        feature["elapsed_time_s"] = record.get("elapsed_time_s")
        feature["total_elevation_gain_m"] = record.get("total_elevation_gain_m")
        feature["average_speed_mps"] = record.get("average_speed_mps")
        feature["max_speed_mps"] = record.get("max_speed_mps")
        feature["average_heartrate"] = record.get("average_heartrate")
        feature["max_heartrate"] = record.get("max_heartrate")
        feature["average_watts"] = record.get("average_watts")
        feature["kilojoules"] = record.get("kilojoules")
        feature["calories"] = record.get("calories")
        feature["suffer_score"] = record.get("suffer_score")
        feature["start_lat"] = record.get("start_lat")
        feature["start_lon"] = record.get("start_lon")
        feature["end_lat"] = record.get("end_lat")
        feature["end_lon"] = record.get("end_lon")
        feature["summary_polyline"] = record.get("summary_polyline")
        feature["geometry_source"] = geometry_source
        feature["geometry_point_count"] = geometry_point_count
        feature["details_json"] = json.dumps(record.get("details_json") or {}, sort_keys=True)
        feature["summary_hash"] = record.get("summary_hash")
        feature["first_seen_at"] = record.get("first_seen_at")
        feature["last_synced_at"] = record.get("last_synced_at")
        features.append(feature)

    provider.addFeatures(features)
    layer.updateExtents()
    return layer


def build_start_layer(records):
    """Build and return a memory ``QgsVectorLayer`` of activity start points."""
    layer = QgsVectorLayer("Point?crs=EPSG:4326", "activity_starts", "memory")
    provider = layer.dataProvider()
    provider.addAttributes(make_qgs_fields(START_FIELDS))
    layer.updateFields()

    features = []
    for index, record in enumerate(records, start=1):
        lat = record.get("start_lat")
        lon = record.get("start_lon")
        if lat is None or lon is None:
            continue

        feature = QgsFeature(layer.fields())
        feature.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(lon, lat)))
        feature["activity_fk"] = index
        feature["source"] = record.get("source")
        feature["source_activity_id"] = record.get("source_activity_id")
        feature["name"] = record.get("name")
        feature["activity_type"] = record.get("activity_type")
        feature["start_date"] = record.get("start_date")
        feature["distance_m"] = record.get("distance_m")
        feature["last_synced_at"] = record.get("last_synced_at")
        features.append(feature)

    provider.addFeatures(features)
    layer.updateExtents()
    return layer

# ---------------------------------------------------------------------------
# Private geometry / stream helpers
# ---------------------------------------------------------------------------


def _activity_geometry(record):
    geometry_points = record.get("geometry_points") or []
    geometry = _geometry_from_points(geometry_points)
    if geometry is not None:
        return geometry, record.get("geometry_source") or "stream", len(geometry_points)

    polyline_points = decode_polyline(record.get("summary_polyline"))
    geometry = _geometry_from_points(polyline_points)
    if geometry is not None:
        return geometry, record.get("geometry_source") or "summary_polyline", len(polyline_points)

    geometry = _fallback_geometry(record)
    if geometry is not None:
        return geometry, record.get("geometry_source") or "start_end", 2

    return None, None, 0


def _geometry_from_points(points):
    if len(points) < 2:
        return None
    return QgsGeometry.fromPolylineXY([QgsPointXY(float(lon), float(lat)) for lat, lon in points])


def _fallback_geometry(record):
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
