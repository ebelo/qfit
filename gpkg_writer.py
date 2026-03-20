import json
import os
from datetime import UTC, datetime

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


ACTIVITY_FIELDS = [
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
    ("details_json", QVariant.String),
    ("imported_at", QVariant.String),
    ("updated_at", QVariant.String),
]

START_FIELDS = [
    ("activity_fk", QVariant.Int),
    ("source", QVariant.String),
    ("source_activity_id", QVariant.String),
    ("name", QVariant.String),
    ("activity_type", QVariant.String),
    ("start_date", QVariant.String),
    ("distance_m", QVariant.Double),
    ("imported_at", QVariant.String),
]


class GeoPackageWriter:
    """Write QFIT activities and start points to a GeoPackage via QGIS APIs."""

    def __init__(self, output_path=None):
        self.output_path = output_path

    def schema(self):
        return {
            "activities": {
                "geometry": "LINESTRING",
                "fields": [name for name, _ in ACTIVITY_FIELDS],
                "unique_key": ["source", "source_activity_id"],
            },
            "activity_starts": {
                "geometry": "POINT",
                "fields": [name for name, _ in START_FIELDS],
            },
        }

    def write_activities(self, activities):
        if not self.output_path:
            raise ValueError("output_path is required")
        os.makedirs(os.path.dirname(self.output_path) or ".", exist_ok=True)

        activity_layer = self._build_activity_layer(activities)
        start_layer = self._build_start_layer(activities)
        self._write_layer(activity_layer, "activities", overwrite_file=True)
        self._write_layer(start_layer, "activity_starts", overwrite_file=False)
        return {
            "schema": self.schema(),
            "path": self.output_path,
            "activity_count": len(activities),
            "start_count": start_layer.featureCount(),
        }

    def _build_activity_layer(self, activities):
        layer = QgsVectorLayer("LineString?crs=EPSG:4326", "activities", "memory")
        provider = layer.dataProvider()
        provider.addAttributes(self._make_fields(ACTIVITY_FIELDS))
        layer.updateFields()

        features = []
        imported_at = datetime.now(UTC).isoformat()
        for activity in activities:
            record = self._normalize_record(activity)
            geometry = self._polyline_geometry(record.get("summary_polyline"))
            if geometry is None:
                geometry = self._fallback_geometry(record)
            if geometry is None:
                continue

            feature = QgsFeature(layer.fields())
            feature.setGeometry(geometry)
            record["details_json"] = json.dumps(record.get("details_json") or {})
            record["imported_at"] = imported_at
            record["updated_at"] = imported_at
            for field_name, _field_type in ACTIVITY_FIELDS:
                feature[field_name] = record.get(field_name)
            features.append(feature)

        provider.addFeatures(features)
        layer.updateExtents()
        return layer

    def _build_start_layer(self, activities):
        layer = QgsVectorLayer("Point?crs=EPSG:4326", "activity_starts", "memory")
        provider = layer.dataProvider()
        provider.addAttributes(self._make_fields(START_FIELDS))
        layer.updateFields()

        features = []
        imported_at = datetime.now(UTC).isoformat()
        for index, activity in enumerate(activities, start=1):
            record = self._normalize_record(activity)
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
            feature["imported_at"] = imported_at
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
            raise RuntimeError(f"Failed to write layer '{layer_name}' to {self.output_path}: {result}")

    def _make_fields(self, field_defs):
        fields = QgsFields()
        for name, field_type in field_defs:
            fields.append(QgsField(name, field_type))
        return fields

    def _normalize_record(self, activity):
        if hasattr(activity, "to_record"):
            return activity.to_record()
        return dict(activity)

    def _polyline_geometry(self, encoded_polyline):
        coordinates = decode_polyline(encoded_polyline)
        if len(coordinates) < 2:
            return None
        return QgsGeometry.fromPolylineXY([QgsPointXY(lon, lat) for lat, lon in coordinates])

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
