from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any

from ....providers.domain.routes import RouteProfilePoint, SavedRoute


ROUTE_REGISTRY_TABLE = "route_registry"
ROUTE_REGISTRY_COLUMNS = [
    "source",
    "source_route_id",
    "external_id",
    "name",
    "description",
    "private",
    "starred",
    "distance_m",
    "elevation_gain_m",
    "estimated_moving_time_s",
    "route_type",
    "sub_type",
    "created_at",
    "updated_at",
    "summary_polyline",
    "geometry_source",
    "geometry_points_json",
    "profile_points_json",
    "details_json",
    "summary_hash",
    "first_seen_at",
    "last_synced_at",
]
ROUTE_HASH_FIELDS = [
    "source",
    "source_route_id",
    "external_id",
    "name",
    "description",
    "private",
    "starred",
    "distance_m",
    "elevation_gain_m",
    "estimated_moving_time_s",
    "route_type",
    "sub_type",
    "created_at",
    "updated_at",
    "summary_polyline",
    "geometry_source",
    "geometry_points",
    "profile_points",
    "details_json",
]
VOLATILE_ROUTE_DETAILS_KEYS = {
    "gpx_enriched_at",
}


@dataclass(frozen=True)
class RouteSyncStats:
    inserted: int
    updated: int
    unchanged: int
    total_count: int


class GeoPackageRouteStore:
    """SQLite/GeoPackage-backed persistence for saved route catalog rows."""

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
                    external_id TEXT,
                    name TEXT,
                    description TEXT,
                    private INTEGER,
                    starred INTEGER,
                    distance_m REAL,
                    elevation_gain_m REAL,
                    estimated_moving_time_s INTEGER,
                    route_type INTEGER,
                    sub_type INTEGER,
                    created_at TEXT,
                    updated_at TEXT,
                    summary_polyline TEXT,
                    geometry_source TEXT,
                    geometry_points_json TEXT,
                    profile_points_json TEXT,
                    details_json TEXT,
                    summary_hash TEXT NOT NULL,
                    first_seen_at TEXT,
                    last_synced_at TEXT,
                    PRIMARY KEY (source, source_route_id)
                )
                """
            )
            for statement in (
                "CREATE INDEX IF NOT EXISTS idx_route_registry_name ON route_registry(name)",
                "CREATE INDEX IF NOT EXISTS idx_route_registry_updated_at ON route_registry(updated_at)",
                "CREATE INDEX IF NOT EXISTS idx_route_registry_distance_m ON route_registry(distance_m)",
                "CREATE INDEX IF NOT EXISTS idx_route_registry_last_synced_at ON route_registry(last_synced_at)",
            ):
                cursor.execute(statement)
            connection.commit()

    def upsert_routes(self, routes, sync_metadata=None):
        sync_metadata = sync_metadata or {}
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

            self._prune_missing_routes(cursor, routes, sync_metadata)
            total_count = cursor.execute("SELECT COUNT(*) FROM route_registry").fetchone()[0]
            connection.commit()

        return RouteSyncStats(inserted=inserted, updated=updated, unchanged=unchanged, total_count=total_count)

    def load_all_route_records(self):
        with self._connect() as connection:
            cursor = connection.cursor()
            rows = cursor.execute(
                "SELECT {columns} FROM route_registry ORDER BY updated_at DESC, source_route_id DESC".format(
                    columns=", ".join(ROUTE_REGISTRY_COLUMNS)
                )
            ).fetchall()
        return [self._row_to_record(row) for row in rows]

    def load_all_routes(self):
        routes = []
        for record in self.load_all_route_records():
            routes.append(
                SavedRoute(
                    source=record.get("source"),
                    source_route_id=record.get("source_route_id"),
                    external_id=record.get("external_id"),
                    name=record.get("name"),
                    description=record.get("description"),
                    private=self._bool_or_none(record.get("private")),
                    starred=self._bool_or_none(record.get("starred")),
                    distance_m=record.get("distance_m"),
                    elevation_gain_m=record.get("elevation_gain_m"),
                    estimated_moving_time_s=record.get("estimated_moving_time_s"),
                    route_type=record.get("route_type"),
                    sub_type=record.get("sub_type"),
                    created_at=record.get("created_at"),
                    updated_at=record.get("updated_at"),
                    summary_polyline=record.get("summary_polyline"),
                    geometry_source=record.get("geometry_source"),
                    geometry_points=record.get("geometry_points") or [],
                    profile_points=[self._profile_point_from_mapping(point) for point in record.get("profile_points") or []],
                    details_json=record.get("details_json") or {},
                )
            )
        return routes

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

    def _prune_missing_routes(self, cursor, routes, sync_metadata):
        if not sync_metadata.get("is_full_sync"):
            return

        provider = sync_metadata.get("provider") or self._infer_single_provider(routes)
        if provider is None:
            return

        incoming_ids = {
            str(source_route_id)
            for route in routes
            if self._route_value(route, "source") == provider
            for source_route_id in [self._route_value(route, "source_route_id")]
            if source_route_id is not None
        }

        if incoming_ids:
            cursor.execute("CREATE TEMP TABLE IF NOT EXISTS incoming_route_sync_ids (source_route_id TEXT PRIMARY KEY)")
            cursor.execute("DELETE FROM incoming_route_sync_ids")
            cursor.executemany(
                "INSERT INTO incoming_route_sync_ids (source_route_id) VALUES (?)",
                [(route_id,) for route_id in sorted(incoming_ids)],
            )
            cursor.execute(
                """
                DELETE FROM route_registry
                WHERE source = ?
                  AND NOT EXISTS (
                      SELECT 1
                      FROM incoming_route_sync_ids
                      WHERE incoming_route_sync_ids.source_route_id = route_registry.source_route_id
                  )
                """,
                [provider],
            )
            return

        cursor.execute("DELETE FROM route_registry WHERE source = ?", (provider,))

    def _infer_single_provider(self, routes):
        providers = {
            self._route_value(route, "source")
            for route in routes
            if self._route_value(route, "source")
        }
        if len(providers) == 1:
            return next(iter(providers))
        return None

    def _route_value(self, route, key):
        if isinstance(route, dict):
            return route.get(key)
        return getattr(route, key, None)

    def _prepare_registry_record(self, record, summary_hash, first_seen_at, last_synced_at):
        return {
            "source": record.get("source"),
            "source_route_id": record.get("source_route_id"),
            "external_id": record.get("external_id"),
            "name": record.get("name"),
            "description": record.get("description"),
            "private": self._int_or_none(record.get("private")),
            "starred": self._int_or_none(record.get("starred")),
            "distance_m": record.get("distance_m"),
            "elevation_gain_m": record.get("elevation_gain_m"),
            "estimated_moving_time_s": record.get("estimated_moving_time_s"),
            "route_type": record.get("route_type"),
            "sub_type": record.get("sub_type"),
            "created_at": record.get("created_at"),
            "updated_at": record.get("updated_at"),
            "summary_polyline": record.get("summary_polyline"),
            "geometry_source": record.get("geometry_source"),
            "geometry_points_json": json.dumps(record.get("geometry_points") or [], sort_keys=True),
            "profile_points_json": json.dumps(self._profile_points_as_mappings(record.get("profile_points") or []), sort_keys=True),
            "details_json": json.dumps(record.get("details_json") or {}, sort_keys=True),
            "summary_hash": summary_hash,
            "first_seen_at": first_seen_at,
            "last_synced_at": last_synced_at,
        }

    def _row_to_record(self, row):
        record = dict(zip(ROUTE_REGISTRY_COLUMNS, row))
        record["geometry_points"] = self._decode_json(record.pop("geometry_points_json"), [])
        record["profile_points"] = self._decode_json(record.pop("profile_points_json"), [])
        record["details_json"] = self._decode_json(record.get("details_json"), {})
        return record

    def _compute_summary_hash(self, record):
        hash_payload: dict[str, Any] = {}
        for field in ROUTE_HASH_FIELDS:
            if field == "details_json":
                hash_payload[field] = self._stable_details_json(record.get(field) or {})
            elif field == "geometry_points":
                hash_payload[field] = self._stable_geometry_points(record.get(field) or [])
            elif field == "profile_points":
                hash_payload[field] = self._stable_profile_points(record.get(field) or [])
            else:
                hash_payload[field] = record.get(field)
        encoded = json.dumps(hash_payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()

    def _stable_details_json(self, details_json):
        return {
            key: value
            for key, value in (details_json or {}).items()
            if key not in VOLATILE_ROUTE_DETAILS_KEYS
        }

    def _stable_geometry_points(self, points):
        stable = []
        for lat, lon in points:
            stable.append([round(float(lat), 7), round(float(lon), 7)])
        return stable

    def _stable_profile_points(self, points):
        stable = []
        for point in points:
            mapping = self._profile_point_as_mapping(point)
            stable.append(
                {
                    "point_index": int(mapping.get("point_index") or 0),
                    "lat": round(float(mapping.get("lat")), 7),
                    "lon": round(float(mapping.get("lon")), 7),
                    "distance_m": round(float(mapping.get("distance_m") or 0.0), 3),
                    "segment_index": int(mapping.get("segment_index") or 0),
                    "altitude_m": None if mapping.get("altitude_m") is None else round(float(mapping.get("altitude_m")), 3),
                }
            )
        return stable

    def _profile_points_as_mappings(self, points):
        return [self._profile_point_as_mapping(point) for point in points]

    def _profile_point_as_mapping(self, point):
        if hasattr(point, "__dataclass_fields__"):
            return asdict(point)
        return dict(point)

    def _profile_point_from_mapping(self, point):
        return RouteProfilePoint(
            point_index=int(point.get("point_index") or 0),
            lat=float(point.get("lat")),
            lon=float(point.get("lon")),
            distance_m=float(point.get("distance_m") or 0.0),
            segment_index=int(point.get("segment_index") or 0),
            altitude_m=None if point.get("altitude_m") is None else float(point.get("altitude_m")),
        )

    def _normalize_record(self, route):
        if hasattr(route, "to_record"):
            return route.to_record()
        return dict(route)

    def _decode_json(self, value, default):
        if not value:
            return default
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return default

    def _int_or_none(self, value):
        if value is None:
            return None
        return int(bool(value))

    def _bool_or_none(self, value):
        if value is None:
            return None
        return bool(value)

    def _connect(self):
        os.makedirs(os.path.dirname(self.db_path) or ".", exist_ok=True)
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection


__all__ = [
    "GeoPackageRouteStore",
    "ROUTE_REGISTRY_COLUMNS",
    "ROUTE_REGISTRY_TABLE",
    "RouteSyncStats",
]
