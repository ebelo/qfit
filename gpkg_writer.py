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


class GeoPackageWriter:
    """Persist QFIT activity sync data to a GeoPackage and rebuild visible layers from the registry."""

    def __init__(self, output_path=None):
        self.output_path = output_path

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
        }

    def write_activities(self, activities, sync_metadata=None):
        if not self.output_path:
            raise ValueError("output_path is required")
        os.makedirs(os.path.dirname(self.output_path) or ".", exist_ok=True)

        repository = SyncRepository(self.output_path)
        new_file = not os.path.exists(self.output_path) or os.path.getsize(self.output_path) == 0
        if new_file:
            bootstrap_tracks = self._build_track_layer(self._normalize_records(activities))
            bootstrap_starts = self._build_start_layer(self._normalize_records(activities))
            self._write_layer(bootstrap_tracks, "activity_tracks", overwrite_file=True)
            self._write_layer(bootstrap_starts, "activity_starts", overwrite_file=False)

        repository.ensure_schema()
        sync_result = repository.upsert_activities(activities, sync_metadata=sync_metadata)
        records = repository.load_all_activity_records()

        track_layer = self._build_track_layer(records)
        start_layer = self._build_start_layer(records)
        self._write_layer(track_layer, "activity_tracks", overwrite_file=False)
        self._write_layer(start_layer, "activity_starts", overwrite_file=False)

        return {
            "schema": self.schema(),
            "path": self.output_path,
            "fetched_count": len(activities),
            "track_count": track_layer.featureCount(),
            "start_count": start_layer.featureCount(),
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
            record["geometry_source"] = geometry_source
            record["geometry_point_count"] = geometry_point_count
            record["details_json"] = json.dumps(record.get("details_json") or {}, sort_keys=True)
            for field_name, _field_type in TRACK_FIELDS:
                feature[field_name] = record.get(field_name)
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
            raise RuntimeError("Failed to write layer '{name}' to {path}: {result}".format(
                name=layer_name,
                path=self.output_path,
                result=result,
            ))

    def _make_fields(self, field_defs):
        fields = QgsFields()
        for name, field_type in field_defs:
            fields.append(QgsField(name, field_type))
        return fields

    def _normalize_records(self, activities):
        records = []
        for activity in activities:
            if hasattr(activity, "to_record"):
                records.append(activity.to_record())
            else:
                records.append(dict(activity))
        return records

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
