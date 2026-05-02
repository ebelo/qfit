from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime

from .route_layer_builders import build_route_point_layer, build_route_track_layer
from ....activities.infrastructure.geopackage.gpkg_io import write_layer_to_gpkg


ROUTE_REGISTRY_TABLE = "route_registry"
ROUTE_REGISTRY_COLUMNS = [
    "source",
    "source_route_id",
    "name",
    "description",
    "route_type",
    "sub_type",
    "distance_m",
    "estimated_moving_time_s",
    "total_elevation_gain_m",
    "created_at",
    "updated_at",
    "starred",
    "private",
    "start_lat",
    "start_lon",
    "end_lat",
    "end_lon",
    "summary_polyline",
    "geometry_source",
    "geometry_points_json",
    "details_json",
    "summary_hash",
    "first_seen_at",
    "last_synced_at",
]
ROUTE_HASH_FIELDS = [
    "source",
    "source_route_id",
    "name",
    "description",
    "route_type",
    "sub_type",
    "distance_m",
    "estimated_moving_time_s",
    "total_elevation_gain_m",
    "created_at",
    "updated_at",
    "starred",
    "private",
    "start_lat",
    "start_lon",
    "end_lat",
    "end_lon",
    "summary_polyline",
    "geometry_source",
    "geometry_points",
    "details_json",
]
ROUTE_VOLATILE_DETAILS_KEYS = {"normalized_at", "gpx_enriched_at", "gpx_error", "gpx_point_count", "gpx_skipped_reason"}


@dataclass(frozen=True)
class RouteSyncStats:
    inserted: int
    updated: int
    unchanged: int
    total_count: int


class GeoPackageRouteStore:
    """GeoPackage-backed route catalog registry and layer writer."""

    def __init__(self, db_path):
        self.db_path = db_path

    def ensure_schema(self):
        with self._connect() as connection:
            cursor = connection.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS route_registry (
                    source TEXT NOT NULL,
                    source_route_id TEXT NOT NULL,
                    name TEXT,
                    description TEXT,
                    route_type TEXT,
                    sub_type TEXT,
                    distance_m REAL,
                    estimated_moving_time_s INTEGER,
                    total_elevation_gain_m REAL,
                    created_at TEXT,
                    updated_at TEXT,
                    starred INTEGER,
                    private INTEGER,
                    start_lat REAL,
                    start_lon REAL,
                    end_lat REAL,
                    end_lon REAL,
                    summary_polyline TEXT,
                    geometry_source TEXT,
                    geometry_points_json TEXT,
                    details_json TEXT,
                    summary_hash TEXT NOT NULL,
                    first_seen_at TEXT,
                    last_synced_at TEXT,
                    PRIMARY KEY (source, source_route_id)
                )
                """
            )
            for statement in (
                "CREATE INDEX IF NOT EXISTS idx_route_registry_source_route_id ON route_registry(source, source_route_id)",
                "CREATE INDEX IF NOT EXISTS idx_route_registry_updated_at ON route_registry(updated_at)",
                "CREATE INDEX IF NOT EXISTS idx_route_registry_distance_m ON route_registry(distance_m)",
                "CREATE INDEX IF NOT EXISTS idx_route_registry_route_type ON route_registry(route_type)",
            ):
                cursor.execute(statement)
            connection.commit()

    def upsert_routes(self, routes):
        now = datetime.now(UTC).isoformat()
        inserted = 0
        updated = 0
        unchanged = 0
        with self._connect() as connection:
            cursor = connection.cursor()
            for route in routes:
                record = self._normalize_record(route)
                summary_hash = self._compute_summary_hash(record)
                existing = cursor.execute(
                    "SELECT summary_hash, first_seen_at FROM route_registry WHERE source = ? AND source_route_id = ?",
                    (record.get("source"), record.get("source_route_id")),
                ).fetchone()
                if existing is not None and existing[0] == summary_hash:
                    unchanged += 1
                    continue
                first_seen_at = now if existing is None else (existing[1] or now)
                registry_record = self._prepare_registry_record(record, summary_hash, first_seen_at, now)
                self._upsert_registry_row(cursor, registry_record)
                if existing is None:
                    inserted += 1
                else:
                    updated += 1
            total_count = cursor.execute("SELECT COUNT(*) FROM route_registry").fetchone()[0]
            connection.commit()
        return RouteSyncStats(inserted=inserted, updated=updated, unchanged=unchanged, total_count=total_count)

    def load_all_route_records(self):
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT {columns} FROM route_registry ORDER BY updated_at DESC, source_route_id DESC".format(
                    columns=", ".join(ROUTE_REGISTRY_COLUMNS)
                )
            ).fetchall()
        return [self._row_to_record(row) for row in rows]

    def write_routes(self, routes):
        os.makedirs(os.path.dirname(self.db_path) or ".", exist_ok=True)
        new_file = not os.path.exists(self.db_path) or os.path.getsize(self.db_path) == 0
        if new_file:
            write_layer_to_gpkg(build_route_track_layer([]), self.db_path, "route_tracks", overwrite_file=True)
            write_layer_to_gpkg(build_route_point_layer([]), self.db_path, "route_points", overwrite_file=False)

        self.ensure_schema()
        sync_result = self.upsert_routes(routes)
        records = self.load_all_route_records()
        track_layer = build_route_track_layer(records)
        point_layer = build_route_point_layer(records)
        write_layer_to_gpkg(track_layer, self.db_path, "route_tracks", overwrite_file=False)
        write_layer_to_gpkg(point_layer, self.db_path, "route_points", overwrite_file=False)
        self._ensure_layer_indexes()
        return {
            "path": self.db_path,
            "fetched_count": len(routes),
            "route_count": track_layer.featureCount(),
            "route_point_count": point_layer.featureCount(),
            "sync": sync_result,
        }

    def _upsert_registry_row(self, cursor, record):
        placeholders = ", ".join("?" for _column in ROUTE_REGISTRY_COLUMNS)
        update_clause = ", ".join(
            "{column} = excluded.{column}".format(column=column)
            for column in ROUTE_REGISTRY_COLUMNS
            if column not in ("source", "source_route_id", "first_seen_at")
        )
        cursor.execute(
            """
            INSERT INTO route_registry ({columns})
            VALUES ({placeholders})
            ON CONFLICT(source, source_route_id) DO UPDATE SET
                {update_clause}
            """.format(
                columns=", ".join(ROUTE_REGISTRY_COLUMNS),
                placeholders=placeholders,
                update_clause=update_clause,
            ),
            [record.get(column) for column in ROUTE_REGISTRY_COLUMNS],
        )

    def _prepare_registry_record(self, record, summary_hash, first_seen_at, last_synced_at):
        return {
            "source": record.get("source"),
            "source_route_id": str(record.get("source_route_id")),
            "name": record.get("name"),
            "description": record.get("description"),
            "route_type": record.get("route_type"),
            "sub_type": record.get("sub_type"),
            "distance_m": record.get("distance_m"),
            "estimated_moving_time_s": record.get("estimated_moving_time_s"),
            "total_elevation_gain_m": record.get("total_elevation_gain_m"),
            "created_at": record.get("created_at"),
            "updated_at": record.get("updated_at"),
            "starred": self._bool_to_int(record.get("starred")),
            "private": self._bool_to_int(record.get("private")),
            "start_lat": record.get("start_lat"),
            "start_lon": record.get("start_lon"),
            "end_lat": record.get("end_lat"),
            "end_lon": record.get("end_lon"),
            "summary_polyline": record.get("summary_polyline"),
            "geometry_source": record.get("geometry_source"),
            "geometry_points_json": json.dumps(self._normalize_points(record.get("geometry_points") or []), sort_keys=True),
            "details_json": json.dumps(record.get("details_json") or {}, sort_keys=True),
            "summary_hash": summary_hash,
            "first_seen_at": first_seen_at,
            "last_synced_at": last_synced_at,
        }

    def _row_to_record(self, row):
        record = dict(zip(ROUTE_REGISTRY_COLUMNS, row))
        record["geometry_points"] = self._decode_json(record.pop("geometry_points_json"), [])
        record["details_json"] = self._decode_json(record.get("details_json"), {})
        record["starred"] = self._int_to_bool(record.get("starred"))
        record["private"] = self._int_to_bool(record.get("private"))
        return record

    def _compute_summary_hash(self, record):
        hash_payload = {}
        for field in ROUTE_HASH_FIELDS:
            if field == "details_json":
                hash_payload[field] = self._stable_details_json(record.get(field) or {})
            elif field == "geometry_points":
                hash_payload[field] = [self._stable_point(point) for point in (record.get(field) or [])]
            else:
                hash_payload[field] = record.get(field)
        encoded = json.dumps(hash_payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()

    def _stable_point(self, point):
        value = self._normalize_point(point)
        return {
            "latitude": self._round_optional(value.get("latitude"), 7),
            "longitude": self._round_optional(value.get("longitude"), 7),
            "altitude_m": self._round_optional(value.get("altitude_m"), 3),
            "distance_m": self._round_optional(value.get("distance_m"), 3),
            "point_index": value.get("point_index"),
        }

    def _stable_details_json(self, details_json):
        return {key: value for key, value in (details_json or {}).items() if key not in ROUTE_VOLATILE_DETAILS_KEYS}

    def _ensure_layer_indexes(self):
        with self._connect() as connection:
            cursor = connection.cursor()
            for statement in (
                "CREATE INDEX IF NOT EXISTS idx_route_tracks_source_route_id ON route_tracks(source, source_route_id)",
                "CREATE INDEX IF NOT EXISTS idx_route_tracks_route_type ON route_tracks(route_type)",
                "CREATE INDEX IF NOT EXISTS idx_route_points_source_route_id ON route_points(source, source_route_id)",
                "CREATE INDEX IF NOT EXISTS idx_route_points_point_index ON route_points(source_route_id, point_index)",
            ):
                cursor.execute(statement)
            connection.commit()

    def _normalize_record(self, route):
        record = route.to_record() if hasattr(route, "to_record") else dict(route)
        if record.get("total_elevation_gain_m") is None and record.get("elevation_gain_m") is not None:
            record["total_elevation_gain_m"] = record.get("elevation_gain_m")
        profile_points = record.pop("profile_points", None) or []
        geometry_points = profile_points or record.get("geometry_points") or []
        record["geometry_points"] = self._normalize_points(geometry_points)
        return record

    def _normalize_points(self, points):
        return [self._normalize_point(point, index=index) for index, point in enumerate(points or [])]

    def _normalize_point(self, point, index=0):
        if hasattr(point, "to_record"):
            value = point.to_record()
        elif isinstance(point, dict):
            value = dict(point)
        elif isinstance(point, (list, tuple)) and len(point) >= 2:
            value = {"latitude": point[0], "longitude": point[1]}
            if len(point) >= 3:
                value["altitude_m"] = point[2]
        else:
            value = {}
        if "latitude" not in value and "lat" in value:
            value["latitude"] = value.get("lat")
        if "longitude" not in value and "lon" in value:
            value["longitude"] = value.get("lon")
        value.setdefault("point_index", index)
        return value

    def _decode_json(self, value, default):
        if not value:
            return default
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return default

    def _connect(self):
        os.makedirs(os.path.dirname(self.db_path) or ".", exist_ok=True)
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    @staticmethod
    def _bool_to_int(value):
        return None if value is None else int(bool(value))

    @staticmethod
    def _int_to_bool(value):
        return None if value is None else bool(value)

    @staticmethod
    def _round_optional(value, digits):
        if value is None:
            return None
        return round(float(value), digits)
