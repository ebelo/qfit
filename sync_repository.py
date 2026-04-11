import hashlib
import json
import os
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime

from .activities.domain.models import Activity


@dataclass(frozen=True)
class SyncStats:
    inserted: int
    updated: int
    unchanged: int
    total_count: int


REGISTRY_TABLE = "activity_registry"
SYNC_STATE_TABLE = "sync_state"
REGISTRY_COLUMNS = [
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
    "geometry_source",
    "geometry_points_json",
    "details_json",
    "summary_hash",
    "first_seen_at",
    "last_synced_at",
]
HASH_FIELDS = [
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
    "geometry_source",
    "geometry_points",
    "details_json",
]
VOLATILE_DETAILS_KEYS = {
    "normalized_at",
    "stream_enriched_at",
    "stream_cache",
    "stream_error",
    "stream_point_count",
    "stream_skipped_reason",
}


class SyncRepository:
    def __init__(self, db_path):
        self.db_path = db_path

    def ensure_schema(self):
        with self._connect() as connection:
            cursor = connection.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS activity_registry (
                    source TEXT NOT NULL,
                    source_activity_id TEXT NOT NULL,
                    external_id TEXT,
                    name TEXT,
                    activity_type TEXT,
                    sport_type TEXT,
                    start_date TEXT,
                    start_date_local TEXT,
                    timezone TEXT,
                    distance_m REAL,
                    moving_time_s INTEGER,
                    elapsed_time_s INTEGER,
                    total_elevation_gain_m REAL,
                    average_speed_mps REAL,
                    max_speed_mps REAL,
                    average_heartrate REAL,
                    max_heartrate REAL,
                    average_watts REAL,
                    kilojoules REAL,
                    calories REAL,
                    suffer_score REAL,
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
                    PRIMARY KEY (source, source_activity_id)
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS sync_state (
                    provider TEXT PRIMARY KEY,
                    last_incremental_sync_at TEXT,
                    last_full_sync_at TEXT,
                    last_before_epoch INTEGER,
                    last_after_epoch INTEGER,
                    last_success_status TEXT,
                    last_rate_limit_snapshot TEXT,
                    last_sync_stats_json TEXT,
                    updated_at TEXT
                )
                """
            )
            for statement in (
                "CREATE INDEX IF NOT EXISTS idx_activity_registry_start_date ON activity_registry(start_date)",
                "CREATE INDEX IF NOT EXISTS idx_activity_registry_type ON activity_registry(activity_type)",
                "CREATE INDEX IF NOT EXISTS idx_activity_registry_source_start_date ON activity_registry(source, start_date)",
                "CREATE INDEX IF NOT EXISTS idx_activity_registry_start_date_local ON activity_registry(start_date_local)",
                "CREATE INDEX IF NOT EXISTS idx_activity_registry_sport_type ON activity_registry(sport_type)",
                "CREATE INDEX IF NOT EXISTS idx_activity_registry_distance_m ON activity_registry(distance_m)",
                "CREATE INDEX IF NOT EXISTS idx_activity_registry_last_synced_at ON activity_registry(last_synced_at)",
            ):
                cursor.execute(statement)
            connection.commit()

    def upsert_activities(self, activities, sync_metadata=None):
        sync_metadata = sync_metadata or {}
        now = datetime.now(UTC).isoformat()
        inserted = 0
        updated = 0
        unchanged = 0

        with self._connect() as connection:
            cursor = connection.cursor()
            for activity in activities:
                record = self._normalize_record(activity)
                summary_hash = self._compute_summary_hash(record)
                existing = cursor.execute(
                    "SELECT summary_hash, first_seen_at FROM activity_registry WHERE source = ? AND source_activity_id = ?",
                    (record.get("source"), record.get("source_activity_id")),
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

            self._prune_missing_activities(cursor, activities, sync_metadata)
            total_count = cursor.execute("SELECT COUNT(*) FROM activity_registry").fetchone()[0]
            self._update_sync_state(cursor, activities, sync_metadata, now, inserted, updated, unchanged, total_count)
            connection.commit()

        return SyncStats(
            inserted=inserted,
            updated=updated,
            unchanged=unchanged,
            total_count=total_count,
        )

    def _prune_missing_activities(self, cursor, activities, sync_metadata):
        if not sync_metadata.get("is_full_sync"):
            return

        provider = sync_metadata.get("provider") or (activities[0].source if activities else "strava")
        incoming_ids = {
            str(activity.source_activity_id if hasattr(activity, "source_activity_id") else activity.get("source_activity_id"))
            for activity in activities
            if (activity.source if hasattr(activity, "source") else activity.get("source")) == provider
            and (activity.source_activity_id if hasattr(activity, "source_activity_id") else activity.get("source_activity_id")) is not None
        }

        if incoming_ids:
            cursor.execute(
                "CREATE TEMP TABLE IF NOT EXISTS incoming_sync_ids (source_activity_id TEXT PRIMARY KEY)"
            )
            cursor.execute("DELETE FROM incoming_sync_ids")
            cursor.executemany(
                "INSERT INTO incoming_sync_ids (source_activity_id) VALUES (?)",
                [(activity_id,) for activity_id in sorted(incoming_ids)],
            )
            cursor.execute(
                """
                DELETE FROM activity_registry
                WHERE source = ?
                  AND NOT EXISTS (
                      SELECT 1
                      FROM incoming_sync_ids
                      WHERE incoming_sync_ids.source_activity_id = activity_registry.source_activity_id
                  )
                """,
                [provider],
            )
            return

        cursor.execute(
            "DELETE FROM activity_registry WHERE source = ?",
            (provider,),
        )

    def load_all_activity_records(self):
        with self._connect() as connection:
            cursor = connection.cursor()
            rows = cursor.execute(
                "SELECT {columns} FROM activity_registry ORDER BY start_date DESC, source_activity_id DESC".format(
                    columns=", ".join(REGISTRY_COLUMNS)
                )
            ).fetchall()
        return [self._row_to_record(row) for row in rows]

    def load_all_activities(self):
        activities = []
        for record in self.load_all_activity_records():
            activity_kwargs = {
                "source": record.get("source"),
                "source_activity_id": record.get("source_activity_id"),
                "external_id": record.get("external_id"),
                "name": record.get("name"),
                "activity_type": record.get("activity_type"),
                "sport_type": record.get("sport_type"),
                "start_date": record.get("start_date"),
                "start_date_local": record.get("start_date_local"),
                "timezone": record.get("timezone"),
                "distance_m": record.get("distance_m"),
                "moving_time_s": record.get("moving_time_s"),
                "elapsed_time_s": record.get("elapsed_time_s"),
                "total_elevation_gain_m": record.get("total_elevation_gain_m"),
                "average_speed_mps": record.get("average_speed_mps"),
                "max_speed_mps": record.get("max_speed_mps"),
                "average_heartrate": record.get("average_heartrate"),
                "max_heartrate": record.get("max_heartrate"),
                "average_watts": record.get("average_watts"),
                "kilojoules": record.get("kilojoules"),
                "calories": record.get("calories"),
                "suffer_score": record.get("suffer_score"),
                "start_lat": record.get("start_lat"),
                "start_lon": record.get("start_lon"),
                "end_lat": record.get("end_lat"),
                "end_lon": record.get("end_lon"),
                "summary_polyline": record.get("summary_polyline"),
                "geometry_source": record.get("geometry_source"),
                "geometry_points": record.get("geometry_points") or [],
                "details_json": record.get("details_json") or {},
            }
            activities.append(Activity(**activity_kwargs))
        return activities

    def _upsert_registry_row(self, cursor, record):
        placeholders = ", ".join("?" for _column in REGISTRY_COLUMNS)
        update_clause = ", ".join(
            "{column} = excluded.{column}".format(column=column)
            for column in REGISTRY_COLUMNS
            if column not in ("source", "source_activity_id", "first_seen_at")
        )
        cursor.execute(
            """
            INSERT INTO activity_registry ({columns})
            VALUES ({placeholders})
            ON CONFLICT(source, source_activity_id) DO UPDATE SET
                {update_clause}
            """.format(
                columns=", ".join(REGISTRY_COLUMNS),
                placeholders=placeholders,
                update_clause=update_clause,
            ),
            [record.get(column) for column in REGISTRY_COLUMNS],
        )

    def _update_sync_state(self, cursor, activities, sync_metadata, now, inserted, updated, unchanged, total_count):
        provider = sync_metadata.get("provider") or (activities[0].source if activities else "strava")
        fetched_count = int(sync_metadata.get("fetched_count", len(activities)))
        stream_stats = sync_metadata.get("stream_stats") or {}
        rate_limit = sync_metadata.get("rate_limit") or {}
        stats_payload = {
            "fetched_count": fetched_count,
            "inserted": inserted,
            "updated": updated,
            "unchanged": unchanged,
            "stored_total": total_count,
            "detailed_count": sync_metadata.get("detailed_count"),
            "stream_stats": stream_stats,
        }
        cursor.execute(
            """
            INSERT INTO sync_state (
                provider,
                last_incremental_sync_at,
                last_full_sync_at,
                last_before_epoch,
                last_after_epoch,
                last_success_status,
                last_rate_limit_snapshot,
                last_sync_stats_json,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(provider) DO UPDATE SET
                last_incremental_sync_at = excluded.last_incremental_sync_at,
                last_full_sync_at = CASE
                    WHEN excluded.last_full_sync_at IS NOT NULL THEN excluded.last_full_sync_at
                    ELSE sync_state.last_full_sync_at
                END,
                last_before_epoch = excluded.last_before_epoch,
                last_after_epoch = excluded.last_after_epoch,
                last_success_status = excluded.last_success_status,
                last_rate_limit_snapshot = excluded.last_rate_limit_snapshot,
                last_sync_stats_json = excluded.last_sync_stats_json,
                updated_at = excluded.updated_at
            """,
            (
                provider,
                now,
                now if sync_metadata.get("is_full_sync") else None,
                sync_metadata.get("before_epoch"),
                sync_metadata.get("after_epoch"),
                "ok",
                json.dumps(rate_limit, sort_keys=True),
                json.dumps(stats_payload, sort_keys=True),
                now,
            ),
        )

    def _prepare_registry_record(self, record, summary_hash, first_seen_at, last_synced_at):
        geometry_points = record.get("geometry_points") or []
        details_json = record.get("details_json") or {}
        return {
            "source": record.get("source"),
            "source_activity_id": record.get("source_activity_id"),
            "external_id": record.get("external_id"),
            "name": record.get("name"),
            "activity_type": record.get("activity_type"),
            "sport_type": record.get("sport_type"),
            "start_date": record.get("start_date"),
            "start_date_local": record.get("start_date_local"),
            "timezone": record.get("timezone"),
            "distance_m": record.get("distance_m"),
            "moving_time_s": record.get("moving_time_s"),
            "elapsed_time_s": record.get("elapsed_time_s"),
            "total_elevation_gain_m": record.get("total_elevation_gain_m"),
            "average_speed_mps": record.get("average_speed_mps"),
            "max_speed_mps": record.get("max_speed_mps"),
            "average_heartrate": record.get("average_heartrate"),
            "max_heartrate": record.get("max_heartrate"),
            "average_watts": record.get("average_watts"),
            "kilojoules": record.get("kilojoules"),
            "calories": record.get("calories"),
            "suffer_score": record.get("suffer_score"),
            "start_lat": record.get("start_lat"),
            "start_lon": record.get("start_lon"),
            "end_lat": record.get("end_lat"),
            "end_lon": record.get("end_lon"),
            "summary_polyline": record.get("summary_polyline"),
            "geometry_source": record.get("geometry_source"),
            "geometry_points_json": json.dumps(geometry_points, sort_keys=True),
            "details_json": json.dumps(details_json, sort_keys=True),
            "summary_hash": summary_hash,
            "first_seen_at": first_seen_at,
            "last_synced_at": last_synced_at,
        }

    def _row_to_record(self, row):
        record = dict(zip(REGISTRY_COLUMNS, row))
        record["geometry_points"] = self._decode_json(record.pop("geometry_points_json"), [])
        record["details_json"] = self._decode_json(record.get("details_json"), {})
        return record

    def _compute_summary_hash(self, record):
        hash_payload = {}
        for field in HASH_FIELDS:
            if field == "details_json":
                hash_payload[field] = self._stable_details_json(record.get(field) or {})
            elif field == "geometry_points":
                hash_payload[field] = [
                    [round(float(lat), 7), round(float(lon), 7)] for lat, lon in (record.get(field) or [])
                ]
            else:
                hash_payload[field] = record.get(field)
        encoded = json.dumps(hash_payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()

    def _stable_details_json(self, details_json):
        stable = {}
        for key, value in (details_json or {}).items():
            if key in VOLATILE_DETAILS_KEYS:
                continue
            stable[key] = value
        return stable

    def _decode_json(self, value, default):
        if not value:
            return default
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return default

    def _normalize_record(self, activity):
        if hasattr(activity, "to_record"):
            return activity.to_record()
        return dict(activity)

    def _connect(self):
        os.makedirs(os.path.dirname(self.db_path) or ".", exist_ok=True)
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection
