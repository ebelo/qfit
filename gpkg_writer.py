import json
import os

from qgis.PyQt.QtCore import QVariant
from qgis.core import (
    QgsCoordinateTransformContext,
    QgsFeature,
    QgsField,
    QgsFields,
    QgsGeometry,
    QgsPointXY,
    QgsProject,
    QgsVectorFileWriter,
    QgsVectorLayer,
)

from .polyline_utils import decode_polyline
from .sync_repository import REGISTRY_TABLE, SYNC_STATE_TABLE, SyncRepository


TRACK_FIELDS = [
    ("source", QVariant.String),
    ("source_activity_id", QVariant.String),
    ("external_id", QVariant.String),
    ("name", QVariant.String),
    ("activity_type", QVariant.String),
    ("sport_type", QVariant.String),
    ("start_date", QVariant.String),
    ("start_date_local", QVariant.String),
    ("timezone", QVariant.String),
    ("distance_m", QVariant.Double),
    ("moving_time_s", QVariant.Int),
    ("elapsed_time_s", QVariant.Int),
    ("total_elevation_gain_m", QVariant.Double),
    ("average_speed_mps", QVariant.Double),
    ("max_speed_mps", QVariant.Double),
    ("average_heartrate", QVariant.Double),
    ("max_heartrate", QVariant.Double),
    ("average_watts", QVariant.Double),
    ("kilojoules", QVariant.Double),
    ("calories", QVariant.Double),
    ("suffer_score", QVariant.Double),
    ("start_lat", QVariant.Double),
    ("start_lon", QVariant.Double),
    ("end_lat", QVariant.Double),
    ("end_lon", QVariant.Double),
    ("summary_polyline", QVariant.String),
    ("geometry_source", QVariant.String),
    ("geometry_point_count", QVariant.Int),
    ("details_json", QVariant.String),
    ("summary_hash", QVariant.String),
    ("first_seen_at", QVariant.String),
    ("last_synced_at", QVariant.String),
]

START_FIELDS = [
    ("activity_fk", QVariant.Int),
    ("source", QVariant.String),
    ("source_activity_id", QVariant.String),
    ("name", QVariant.String),
    ("activity_type", QVariant.String),
    ("start_date", QVariant.String),
    ("distance_m", QVariant.Double),
    ("last_synced_at", QVariant.String),
]

POINT_FIELDS = [
    ("activity_fk", QVariant.Int),
    ("source", QVariant.String),
    ("source_activity_id", QVariant.String),
    ("point_index", QVariant.Int),
    ("point_ratio", QVariant.Double),
    ("stream_time_s", QVariant.Int),
    ("stream_distance_m", QVariant.Double),
    ("altitude_m", QVariant.Double),
    ("heartrate_bpm", QVariant.Double),
    ("cadence_rpm", QVariant.Double),
    ("watts", QVariant.Double),
    ("velocity_mps", QVariant.Double),
    ("temp_c", QVariant.Double),
    ("grade_smooth_pct", QVariant.Double),
    ("moving", QVariant.Int),
    ("name", QVariant.String),
    ("activity_type", QVariant.String),
    ("start_date", QVariant.String),
    ("distance_m", QVariant.Double),
    ("geometry_source", QVariant.String),
    ("last_synced_at", QVariant.String),
]


class GeoPackageWriter:
    """Persist QFIT sync data to a GeoPackage and rebuild derived visualization layers."""

    def __init__(self, output_path=None, write_activity_points=False, point_stride=5):
        self.output_path = output_path
        self.write_activity_points = bool(write_activity_points)
        self.point_stride = max(1, int(point_stride or 1))

    def schema(self):
        return {
            REGISTRY_TABLE: {
                "geometry": None,
                "kind": "table",
                "primary_key": ["source", "source_activity_id"],
            },
            SYNC_STATE_TABLE: {
                "geometry": None,
                "kind": "table",
                "primary_key": ["provider"],
            },
            "activity_tracks": {
                "geometry": "LINESTRING",
                "kind": "layer",
                "fields": [name for name, _ in TRACK_FIELDS],
            },
            "activity_starts": {
                "geometry": "POINT",
                "kind": "layer",
                "fields": [name for name, _ in START_FIELDS],
            },
            "activity_points": {
                "geometry": "POINT",
                "kind": "layer",
                "fields": [name for name, _ in POINT_FIELDS],
            },
        }

    def write_activities(self, activities, sync_metadata=None):
        if not self.output_path:
            raise ValueError("output_path is required")
        os.makedirs(os.path.dirname(self.output_path) or ".", exist_ok=True)

        repository = SyncRepository(self.output_path)
        new_file = not os.path.exists(self.output_path) or os.path.getsize(self.output_path) == 0
        if new_file:
            self._write_layer(self._build_track_layer([]), "activity_tracks", overwrite_file=True)
            self._write_layer(self._build_start_layer([]), "activity_starts", overwrite_file=False)
            self._write_layer(self._build_point_layer([]), "activity_points", overwrite_file=False)

        repository.ensure_schema()
        sync_result = repository.upsert_activities(activities, sync_metadata=sync_metadata)
        records = repository.load_all_activity_records()

        track_layer = self._build_track_layer(records)
        start_layer = self._build_start_layer(records)
        point_layer = self._build_point_layer(records)
        self._write_layer(track_layer, "activity_tracks", overwrite_file=False)
        self._write_layer(start_layer, "activity_starts", overwrite_file=False)
        self._write_layer(point_layer, "activity_points", overwrite_file=False)

        return {
            "schema": self.schema(),
            "path": self.output_path,
            "fetched_count": len(activities),
            "track_count": track_layer.featureCount(),
            "start_count": start_layer.featureCount(),
            "point_count": point_layer.featureCount(),
            "sync": sync_result,
        }

    def _build_track_layer(self, records):
        layer = QgsVectorLayer("LineString?crs=EPSG:4326", "activity_tracks", "memory")
        provider = layer.dataProvider()
        provider.addAttributes(self._make_fields(TRACK_FIELDS))
        layer.updateFields()

        features = []
        for record in records:
            geometry, geometry_source, geometry_point_count = self._activity_geometry(record)
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

    def _build_start_layer(self, records):
        layer = QgsVectorLayer("Point?crs=EPSG:4326", "activity_starts", "memory")
        provider = layer.dataProvider()
        provider.addAttributes(self._make_fields(START_FIELDS))
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

    def _build_point_layer(self, records):
        layer = QgsVectorLayer("Point?crs=EPSG:4326", "activity_points", "memory")
        provider = layer.dataProvider()
        provider.addAttributes(self._make_fields(POINT_FIELDS))
        layer.updateFields()

        features = []
        if not self.write_activity_points:
            provider.addFeatures(features)
            layer.updateExtents()
            return layer

        for index, record in enumerate(records, start=1):
            geometry_points = record.get("geometry_points") or []
            if len(geometry_points) < 1:
                continue

            stream_metrics = ((record.get("details_json") or {}).get("stream_metrics") or {})
            sampled_points = self._sample_points(geometry_points)
            total_points = max(1, len(geometry_points) - 1)
            for point_index, lat, lon in sampled_points:
                feature = QgsFeature(layer.fields())
                feature.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(float(lon), float(lat))))
                feature["activity_fk"] = index
                feature["source"] = record.get("source")
                feature["source_activity_id"] = record.get("source_activity_id")
                feature["point_index"] = point_index
                feature["point_ratio"] = float(point_index) / float(total_points)
                feature["stream_time_s"] = self._metric_value(stream_metrics, "time", point_index, as_int=True)
                feature["stream_distance_m"] = self._metric_value(stream_metrics, "distance", point_index)
                feature["altitude_m"] = self._metric_value(stream_metrics, "altitude", point_index)
                feature["heartrate_bpm"] = self._metric_value(stream_metrics, "heartrate", point_index)
                feature["cadence_rpm"] = self._metric_value(stream_metrics, "cadence", point_index)
                feature["watts"] = self._metric_value(stream_metrics, "watts", point_index)
                feature["velocity_mps"] = self._metric_value(stream_metrics, "velocity_smooth", point_index)
                feature["temp_c"] = self._metric_value(stream_metrics, "temp", point_index)
                feature["grade_smooth_pct"] = self._metric_value(stream_metrics, "grade_smooth", point_index)
                feature["moving"] = self._metric_value(stream_metrics, "moving", point_index, as_int=True)
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

    def _write_layer(self, layer, layer_name, overwrite_file):
        options = QgsVectorFileWriter.SaveVectorOptions()
        options.driverName = "GPKG"
        options.layerName = layer_name
        options.fileEncoding = "UTF-8"
        options.actionOnExistingFile = (
            QgsVectorFileWriter.CreateOrOverwriteFile
            if overwrite_file
            else QgsVectorFileWriter.CreateOrOverwriteLayer
        )

        result = QgsVectorFileWriter.writeAsVectorFormatV3(
            layer,
            self.output_path,
            QgsProject.instance().transformContext() if QgsProject.instance() else QgsCoordinateTransformContext(),
            options,
        )
        if result[0] != QgsVectorFileWriter.NoError:
            raise RuntimeError(
                "Failed to write layer '{name}' to {path}: {result}".format(
                    name=layer_name,
                    path=self.output_path,
                    result=result,
                )
            )

    def _make_fields(self, field_defs):
        fields = QgsFields()
        for name, field_type in field_defs:
            fields.append(QgsField(name, field_type))
        return fields

    def _activity_geometry(self, record):
        geometry_points = record.get("geometry_points") or []
        geometry = self._geometry_from_points(geometry_points)
        if geometry is not None:
            return geometry, record.get("geometry_source") or "stream", len(geometry_points)

        polyline_points = decode_polyline(record.get("summary_polyline"))
        geometry = self._geometry_from_points(polyline_points)
        if geometry is not None:
            return geometry, record.get("geometry_source") or "summary_polyline", len(polyline_points)

        geometry = self._fallback_geometry(record)
        if geometry is not None:
            return geometry, record.get("geometry_source") or "start_end", 2

        return None, None, 0

    def _geometry_from_points(self, points):
        if len(points) < 2:
            return None
        return QgsGeometry.fromPolylineXY([QgsPointXY(float(lon), float(lat)) for lat, lon in points])

    def _fallback_geometry(self, record):
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

    def _sample_points(self, points):
        if not points:
            return []
        if self.point_stride <= 1:
            return [(index, lat, lon) for index, (lat, lon) in enumerate(points)]

        sampled_indexes = list(range(0, len(points), self.point_stride))
        if sampled_indexes[-1] != len(points) - 1:
            sampled_indexes.append(len(points) - 1)
        return [(index, points[index][0], points[index][1]) for index in sampled_indexes]

    def _metric_value(self, stream_metrics, key, index, as_int=False):
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
