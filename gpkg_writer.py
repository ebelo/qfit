import json
from datetime import UTC, datetime

from .polyline_utils import decode_polyline


ACTIVITY_FIELDS = [
    "source",
    "source_activity_id",
    "external_id",
    "name",
    "activity_type",
    "sport_type",
    "start_date",
    "start_date_local",
    "timezone",
    "distance_m",
    "moving_time_s",
    "elapsed_time_s",
    "total_elevation_gain_m",
    "average_speed_mps",
    "max_speed_mps",
    "average_heartrate",
    "max_heartrate",
    "average_watts",
    "kilojoules",
    "calories",
    "suffer_score",
    "start_lat",
    "start_lon",
    "end_lat",
    "end_lon",
    "summary_polyline",
    "details_json",
    "imported_at",
    "updated_at",
]


class GeoPackageWriter:
    """Initial schema and feature-preparation helper for GeoPackage export."""

    def __init__(self, output_path=None):
        self.output_path = output_path

    def schema(self):
        return {
            "activities": {
                "geometry": "LINESTRING",
                "fields": list(ACTIVITY_FIELDS),
                "unique_key": ["source", "source_activity_id"],
            },
            "activity_starts": {
                "geometry": "POINT",
                "fields": [
                    "activity_fk",
                    "source",
                    "source_activity_id",
                    "name",
                    "activity_type",
                    "start_date",
                    "distance_m",
                    "imported_at",
                ],
            },
        }

    def prepare_activity_feature(self, activity):
        imported_at = datetime.now(UTC).isoformat()
        record = self._normalize_record(activity)
        record["details_json"] = json.dumps(record.get("details_json") or {})
        record["imported_at"] = imported_at
        record["updated_at"] = imported_at

        geometry = self._polyline_to_wkt(record.get("summary_polyline"))
        return {"layer": "activities", "geometry_wkt": geometry, "attributes": record}

    def prepare_start_feature(self, activity, activity_fk=None):
        record = self._normalize_record(activity)
        lat = record.get("start_lat")
        lon = record.get("start_lon")
        if lat is None or lon is None:
            return None

        return {
            "layer": "activity_starts",
            "geometry_wkt": f"POINT ({lon} {lat})",
            "attributes": {
                "activity_fk": activity_fk,
                "source": record.get("source"),
                "source_activity_id": record.get("source_activity_id"),
                "name": record.get("name"),
                "activity_type": record.get("activity_type"),
                "start_date": record.get("start_date"),
                "distance_m": record.get("distance_m"),
                "imported_at": datetime.now(UTC).isoformat(),
            },
        }

    def write_activities(self, activities):
        return {
            "schema": self.schema(),
            "features": [self.prepare_activity_feature(activity) for activity in activities],
            "start_features": [
                feature
                for feature in (self.prepare_start_feature(activity) for activity in activities)
                if feature is not None
            ],
        }

    def _normalize_record(self, activity):
        if hasattr(activity, "to_record"):
            return activity.to_record()
        return dict(activity)

    def _polyline_to_wkt(self, encoded_polyline):
        coordinates = decode_polyline(encoded_polyline)
        if len(coordinates) < 2:
            return None
        coordinate_text = ", ".join(f"{lon} {lat}" for lat, lon in coordinates)
        return f"LINESTRING ({coordinate_text})"
