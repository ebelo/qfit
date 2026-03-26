"""
GeoPackage layer builders for qfit.

This module provides standalone functions that build ``QgsVectorLayer`` objects
from activity records and atlas plans.  It contains no I/O — callers are
responsible for writing the returned layers to disk.

Geometry-less atlas helper-table builders (document summary, cover highlights,
page detail items, profile samples, TOC) live in
:mod:`gpkg_atlas_table_builders`.
"""

import json

from qgis.core import (
    QgsFeature,
    QgsGeometry,
    QgsPointXY,
    QgsRectangle,
    QgsVectorLayer,
)

from .gpkg_schema import (
    ATLAS_FIELDS,
    POINT_FIELDS,
    START_FIELDS,
    TRACK_FIELDS,
    make_qgs_fields,
)
from .polyline_utils import decode_polyline
from .gpkg_atlas_table_builders import (
    build_cover_highlight_layer,
    build_document_summary_layer,
    build_page_detail_item_layer,
    build_profile_sample_layer,
    build_toc_layer,
)
from .atlas.publish_atlas import build_atlas_page_plans
from .time_utils import add_seconds_iso


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
        geometry_points = record.get("geometry_points") or []
        if len(geometry_points) < 1:
            continue

        stream_metrics = ((record.get("details_json") or {}).get("stream_metrics") or {})
        sampled_points = _sample_points(geometry_points, stride)
        total_points = max(1, len(geometry_points) - 1)
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
            feature["geometry_source"] = record.get("geometry_source") or "stream"
            feature["last_synced_at"] = record.get("last_synced_at")
            features.append(feature)

    provider.addFeatures(features)
    layer.updateExtents()
    return layer


def build_atlas_layer(records, atlas_page_settings, plans=None):
    """Build and return a memory ``QgsVectorLayer`` of atlas page extents.

    Layer CRS is EPSG:3857 (Web Mercator) so that the QGIS atlas map frame
    uses extents as-is without reprojection distortion.
    """
    layer = QgsVectorLayer("Polygon?crs=EPSG:3857", "activity_atlas_pages", "memory")
    provider = layer.dataProvider()
    provider.addAttributes(make_qgs_fields(ATLAS_FIELDS))
    layer.updateFields()

    features = []
    resolved_plans = plans if plans is not None else build_atlas_page_plans(records, settings=atlas_page_settings)
    for plan in resolved_plans:
        half_w = plan.extent_width_m / 2.0
        half_h = plan.extent_height_m / 2.0
        rect = QgsRectangle(
            plan.center_x_3857 - half_w,
            plan.center_y_3857 - half_h,
            plan.center_x_3857 + half_w,
            plan.center_y_3857 + half_h,
        )
        feature = QgsFeature(layer.fields())
        feature.setGeometry(QgsGeometry.fromRect(rect))
        feature["activity_fk"] = plan.page_number
        feature["source"] = plan.source
        feature["source_activity_id"] = plan.source_activity_id
        feature["name"] = plan.name
        feature["activity_type"] = plan.activity_type
        feature["start_date"] = plan.start_date
        feature["distance_m"] = plan.distance_m
        feature["moving_time_s"] = plan.moving_time_s
        feature["geometry_source"] = plan.geometry_source
        feature["page_number"] = plan.page_number
        feature["page_sort_key"] = plan.page_sort_key
        feature["page_name"] = plan.page_name
        feature["page_title"] = plan.page_title
        feature["page_subtitle"] = plan.page_subtitle
        feature["page_date"] = plan.page_date
        feature["page_toc_label"] = plan.page_toc_label
        feature["page_distance_label"] = plan.page_distance_label
        feature["page_duration_label"] = plan.page_duration_label
        feature["page_average_speed_label"] = plan.page_average_speed_label
        feature["page_average_pace_label"] = plan.page_average_pace_label
        feature["page_elevation_gain_label"] = plan.page_elevation_gain_label
        feature["page_stats_summary"] = plan.page_stats_summary
        feature["page_profile_summary"] = plan.page_profile_summary
        feature["document_activity_count"] = plan.document_activity_count
        feature["document_date_range_label"] = plan.document_date_range_label
        feature["document_total_distance_label"] = plan.document_total_distance_label
        feature["document_total_duration_label"] = plan.document_total_duration_label
        feature["document_total_elevation_gain_label"] = plan.document_total_elevation_gain_label
        feature["document_activity_types_label"] = plan.document_activity_types_label
        feature["document_cover_summary"] = plan.document_cover_summary
        feature["profile_available"] = int(plan.profile_available)
        feature["profile_point_count"] = plan.profile_point_count
        feature["profile_distance_m"] = plan.profile_distance_m
        feature["profile_distance_label"] = plan.profile_distance_label
        feature["profile_min_altitude_m"] = plan.profile_min_altitude_m
        feature["profile_max_altitude_m"] = plan.profile_max_altitude_m
        feature["profile_altitude_range_label"] = plan.profile_altitude_range_label
        feature["profile_relief_m"] = plan.profile_relief_m
        feature["profile_elevation_gain_m"] = plan.profile_elevation_gain_m
        feature["profile_elevation_gain_label"] = plan.profile_elevation_gain_label
        feature["profile_elevation_loss_m"] = plan.profile_elevation_loss_m
        feature["profile_elevation_loss_label"] = plan.profile_elevation_loss_label
        feature["center_x_3857"] = plan.center_x_3857
        feature["center_y_3857"] = plan.center_y_3857
        feature["extent_width_deg"] = plan.extent_width_deg
        feature["extent_height_deg"] = plan.extent_height_deg
        feature["extent_width_m"] = plan.extent_width_m
        feature["extent_height_m"] = plan.extent_height_m
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


def _sample_points(points, stride):
    if not points:
        return []
    if stride <= 1:
        return [(index, lat, lon) for index, (lat, lon) in enumerate(points)]

    sampled_indexes = list(range(0, len(points), stride))
    if sampled_indexes[-1] != len(points) - 1:
        sampled_indexes.append(len(points) - 1)
    return [(index, points[index][0], points[index][1]) for index in sampled_indexes]


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
