import hashlib
import json
import os
import sqlite3
import zlib
from dataclasses import dataclass
from datetime import UTC, datetime

from .activities.domain.models import Activity
from .activities.domain.activity_reconciliation import reconcile_activity_records


@dataclass(frozen=True)
class SyncStats:
    inserted: int
    updated: int
    unchanged: int
    total_count: int


@dataclass(frozen=True)
class ActivitySyncState:
    """Completed activity-sync metadata persisted in the GeoPackage."""

    provider: str
    last_incremental_sync_at: str | None = None
    last_full_sync_at: str | None = None
    last_before_epoch: int | None = None
    last_after_epoch: int | None = None
    last_success_status: str | None = None
    updated_at: str | None = None
    stored_activity_count: int = 0
    latest_activity_start_date: str | None = None

    @property
    def has_completed_sync(self) -> bool:
        return self.last_success_status == "ok" and self.updated_at is not None


@dataclass(frozen=True)
class DetailedRouteCoverage:
    """Stored detailed-route coverage for activity stream backfill status."""

    detailed_count: int = 0
    total_count: int = 0


SYNC_STATE_COLUMNS = [
    "provider",
    "last_incremental_sync_at",
    "last_full_sync_at",
    "last_before_epoch",
    "last_after_epoch",
    "last_success_status",
    "updated_at",
]


REGISTRY_TABLE = "activity_registry"
SYNC_STATE_TABLE = "sync_state"
DETAIL_PAYLOAD_TABLE = "activity_detail_payloads"
DETAIL_PAYLOAD_ENCODING = "json+zlib-v1"
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
START_DATE_COLUMN_INDEX = REGISTRY_COLUMNS.index("start_date")


class ActivityDetailPayloadError(RuntimeError):
    """Raised when compressed activity detail cannot be trusted or decoded."""


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
    "bulk_imported_at",
    "detail_payload",
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
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS activity_detail_payloads (
                    source TEXT NOT NULL,
                    source_activity_id TEXT NOT NULL,
                    encoding TEXT NOT NULL,
                    payload_sha256 TEXT NOT NULL,
                    payload_zlib BLOB NOT NULL,
                    point_count INTEGER NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (source, source_activity_id)
                )
                """
            )
            for statement in (
                "CREATE INDEX IF NOT EXISTS idx_activity_registry_start_date ON activity_registry(start_date)",
                "CREATE INDEX IF NOT EXISTS idx_activity_registry_type ON activity_registry(activity_type)",
                (
                    "CREATE INDEX IF NOT EXISTS idx_activity_registry_source_start_date "
                    "ON activity_registry(source, start_date)"
                ),
                (
                    "CREATE INDEX IF NOT EXISTS idx_activity_registry_start_date_local "
                    "ON activity_registry(start_date_local)"
                ),
                "CREATE INDEX IF NOT EXISTS idx_activity_registry_sport_type ON activity_registry(sport_type)",
                "CREATE INDEX IF NOT EXISTS idx_activity_registry_distance_m ON activity_registry(distance_m)",
                "CREATE INDEX IF NOT EXISTS idx_activity_registry_last_synced_at ON activity_registry(last_synced_at)",
            ):
                cursor.execute(statement)
            connection.commit()

    def upsert_activities(
        self,
        activities,
        sync_metadata=None,
        *,
        compress_detail_payloads=False,
        reconcile_existing=True,
    ):
        sync_metadata = sync_metadata or {}
        now = datetime.now(UTC).isoformat()
        counts = {"inserted": 0, "updated": 0, "unchanged": 0}

        with self._connect() as connection:
            cursor = connection.cursor()
            for activity in activities:
                outcome = self._upsert_activity(
                    cursor,
                    activity,
                    now,
                    compress_detail_payloads=compress_detail_payloads,
                    reconcile_existing=reconcile_existing,
                )
                counts[outcome] += 1

            self._prune_missing_activities(cursor, activities, sync_metadata)
            self._prune_orphaned_detail_payloads(cursor)
            total_count = cursor.execute("SELECT COUNT(*) FROM activity_registry").fetchone()[0]
            if not sync_metadata.get("suppress_sync_state"):
                self._update_sync_state(
                    cursor,
                    activities,
                    sync_metadata,
                    now,
                    counts["inserted"],
                    counts["updated"],
                    counts["unchanged"],
                    total_count,
                )
            connection.commit()

        return SyncStats(
            inserted=counts["inserted"],
            updated=counts["updated"],
            unchanged=counts["unchanged"],
            total_count=total_count,
        )

    def _upsert_activity(
        self,
        cursor,
        activity,
        now,
        *,
        compress_detail_payloads,
        reconcile_existing,
    ):
        record = self._normalize_record(activity)
        existing_row = cursor.execute(
            "SELECT {columns} FROM activity_registry "
            "WHERE source = ? AND source_activity_id = ?".format(
                columns=", ".join(REGISTRY_COLUMNS)
            ),
            (record.get("source"), record.get("source_activity_id")),
        ).fetchone()
        recover_detail_payload = False
        if existing_row is not None and reconcile_existing:
            record, recover_detail_payload = self._reconcile_existing_activity(
                cursor,
                record,
                existing_row,
                compress_detail_payloads=compress_detail_payloads,
            )
        summary_hash = self._compute_summary_hash(record)
        if (
            existing_row is not None
            and existing_row["summary_hash"] == summary_hash
            and not recover_detail_payload
        ):
            return "unchanged"

        first_seen_at = (
            now
            if existing_row is None
            else (existing_row["first_seen_at"] or now)
        )
        registry_record = self._prepare_registry_record(
            record,
            summary_hash,
            first_seen_at,
            now,
        )
        existing_payload_storage = bool(
            (record.get("details_json") or {}).get("detail_payload")
        )
        if compress_detail_payloads or existing_payload_storage:
            registry_record, payload_record = self._extract_detail_payload(
                registry_record,
                record,
                now,
            )
            self._upsert_detail_payload(cursor, payload_record)
        else:
            self._delete_detail_payload(cursor, record)
        self._upsert_registry_row(cursor, registry_record)
        return "inserted" if existing_row is None else "updated"

    def _reconcile_existing_activity(
        self,
        cursor,
        record,
        existing_row,
        *,
        compress_detail_payloads,
    ):
        key = (record.get("source"), str(record.get("source_activity_id")))
        recover_detail_payload = False
        try:
            payloads = self._load_detail_payloads(cursor.connection, keys=[key])
        except ActivityDetailPayloadError:
            incoming_details = record.get("details_json") or {}
            incoming_has_detail = bool(
                record.get("geometry_points")
                or incoming_details.get("stream_metrics")
            )
            if not compress_detail_payloads or not incoming_has_detail:
                raise
            payloads = {}
            recover_detail_payload = True
        existing_record = self._row_to_record(existing_row, payloads=payloads)
        return (
            reconcile_activity_records(record, existing_record),
            recover_detail_payload,
        )

    def _prune_missing_activities(self, cursor, activities, sync_metadata):
        if not sync_metadata.get("is_full_sync"):
            return

        provider = sync_metadata.get("provider") or (activities[0].source if activities else "strava")

        def activity_field(activity, field_name):
            return getattr(activity, field_name) if hasattr(activity, field_name) else activity.get(field_name)

        incoming_ids = {
            str(activity_field(activity, "source_activity_id"))
            for activity in activities
            if activity_field(activity, "source") == provider
            and activity_field(activity, "source_activity_id") is not None
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
            payloads = self._load_detail_payloads(connection)
        return [self._row_to_record(row, payloads=payloads) for row in rows]

    def iter_activity_record_batches(self, batch_size=25):
        """Yield hydrated registry rows in bounded batches."""

        batch_size = max(int(batch_size), 1)
        cursor_key = None
        record_index = 0
        while True:
            with self._connect() as connection:
                rows = self._load_activity_batch(
                    connection,
                    batch_size,
                    cursor_key,
                )
                if not rows:
                    return
                keys = [(row[0], row[1]) for row in rows]
                payloads = self._load_detail_payloads(connection, keys=keys)
            records = []
            for row in rows:
                record_index += 1
                record = self._row_to_record(row, payloads=payloads)
                record["_activity_fk"] = record_index
                records.append(record)
            yield records
            last = rows[-1]
            cursor_key = (
                last[START_DATE_COLUMN_INDEX] or "",
                last[0],
                last[1],
            )

    @staticmethod
    def _load_activity_batch(connection, batch_size, cursor_key):
        columns = ", ".join(REGISTRY_COLUMNS)
        order = (
            "ORDER BY COALESCE(start_date, '') DESC, source DESC, "
            "source_activity_id DESC LIMIT ?"
        )
        if cursor_key is None:
            return connection.execute(
                f"SELECT {columns} FROM activity_registry {order}",
                (batch_size,),
            ).fetchall()
        start_date, source, source_activity_id = cursor_key
        return connection.execute(
            f"SELECT {columns} FROM activity_registry "
            "WHERE COALESCE(start_date, '') < ? "
            "OR (COALESCE(start_date, '') = ? AND source < ?) "
            "OR (COALESCE(start_date, '') = ? AND source = ? "
            "AND source_activity_id < ?) "
            f"{order}",
            (
                start_date,
                start_date,
                source,
                start_date,
                source,
                source_activity_id,
                batch_size,
            ),
        ).fetchall()

    def load_activity_record(self, source, source_activity_id):
        """Load one canonical record, hydrating any compressed point payload."""

        with self._connect() as connection:
            row = connection.execute(
                "SELECT {columns} FROM activity_registry WHERE source = ? AND source_activity_id = ?".format(
                    columns=", ".join(REGISTRY_COLUMNS)
                ),
                (source, str(source_activity_id)),
            ).fetchone()
            if row is None:
                return None
            payloads = self._load_detail_payloads(
                connection,
                keys=[(source, str(source_activity_id))],
            )
        return self._row_to_record(row, payloads=payloads)

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

    def load_activity_count(self, provider=None):
        """Return the number of canonical activities without hydrating payloads."""

        with self._connect() as connection:
            if provider is None:
                query = "SELECT COUNT(*) FROM activity_registry"
                return int(connection.execute(query).fetchone()[0])
            return int(
                connection.execute(
                    "SELECT COUNT(*) FROM activity_registry WHERE source = ?",
                    (provider,),
                ).fetchone()[0]
            )

    def load_activity_sync_state(self, provider="strava") -> ActivitySyncState | None:
        """Return the latest completed sync metadata for *provider*, if present."""

        if not self._database_exists():
            return None
        try:
            with self._connect() as connection:
                state_row = connection.execute(
                    """
                    SELECT {columns}
                    FROM sync_state
                    WHERE provider = ?
                    """.format(columns=", ".join(SYNC_STATE_COLUMNS)),
                    (provider,),
                ).fetchone()
                if state_row is None:
                    return None
                activity_row = connection.execute(
                    """
                    SELECT COUNT(*) AS stored_activity_count, MAX(start_date) AS latest_activity_start_date
                    FROM activity_registry
                    WHERE source = ?
                    """,
                    (provider,),
                ).fetchone()
        except sqlite3.OperationalError as exc:
            if _is_missing_sync_schema_error(exc):
                return None
            raise

        return ActivitySyncState(
            **dict(zip(SYNC_STATE_COLUMNS, state_row)),
            stored_activity_count=int(activity_row["stored_activity_count"]),
            latest_activity_start_date=activity_row["latest_activity_start_date"],
        )

    def load_detailed_route_coverage(self, provider="strava") -> DetailedRouteCoverage:
        """Return stored detailed activity-route coverage for *provider*."""

        if not self._database_exists():
            return DetailedRouteCoverage()
        try:
            with self._connect() as connection:
                row = connection.execute(
                    """
                    SELECT
                        COUNT(*) AS total_count,
                        SUM(
                            CASE
                                WHEN geometry_source = 'stream' THEN 1
                                ELSE 0
                            END
                        ) AS detailed_count
                    FROM activity_registry
                    WHERE source = ?
                    """,
                    (provider,),
                ).fetchone()
        except sqlite3.OperationalError as exc:
            if _is_missing_sync_schema_error(exc):
                return DetailedRouteCoverage()
            raise

        return DetailedRouteCoverage(
            detailed_count=int(row["detailed_count"] or 0),
            total_count=int(row["total_count"] or 0),
        )

    def has_completed_activity_sync(self, provider="strava") -> bool:
        state = self.load_activity_sync_state(provider=provider)
        return bool(state and state.has_completed_sync)

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

    def _row_to_record(self, row, *, payloads=None):
        record = dict(zip(REGISTRY_COLUMNS, row))
        record["geometry_points"] = self._decode_json(record.pop("geometry_points_json"), [])
        record["details_json"] = self._decode_json(record.get("details_json"), {})
        payload = (payloads or {}).get((record["source"], record["source_activity_id"]))
        if payload is not None:
            record["geometry_points"] = payload.get("geometry_points") or []
            stream_metrics = payload.get("stream_metrics") or {}
            if stream_metrics:
                record["details_json"]["stream_metrics"] = stream_metrics
        return record

    def _extract_detail_payload(self, registry_record, source_record, now):
        geometry_points = source_record.get("geometry_points") or []
        details = dict(source_record.get("details_json") or {})
        stream_metrics = details.pop("stream_metrics", None) or {}
        if not geometry_points and not stream_metrics:
            return registry_record, None
        payload = {
            "geometry_points": geometry_points,
            "stream_metrics": stream_metrics,
        }
        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        payload_sha256 = hashlib.sha256(encoded).hexdigest()
        details["detail_payload"] = {
            "encoding": DETAIL_PAYLOAD_ENCODING,
            "sha256": payload_sha256,
            "point_count": len(geometry_points),
        }
        registry_record = dict(registry_record)
        registry_record["geometry_points_json"] = "[]"
        registry_record["details_json"] = json.dumps(details, sort_keys=True)
        return registry_record, {
            "source": source_record.get("source"),
            "source_activity_id": str(source_record.get("source_activity_id")),
            "encoding": DETAIL_PAYLOAD_ENCODING,
            "payload_sha256": payload_sha256,
            "payload_zlib": zlib.compress(encoded, level=6),
            "point_count": len(geometry_points),
            "updated_at": now,
        }

    def _upsert_detail_payload(self, cursor, record):
        if record is None:
            return
        cursor.execute(
            """
            INSERT INTO activity_detail_payloads (
                source, source_activity_id, encoding, payload_sha256,
                payload_zlib, point_count, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(source, source_activity_id) DO UPDATE SET
                encoding = excluded.encoding,
                payload_sha256 = excluded.payload_sha256,
                payload_zlib = excluded.payload_zlib,
                point_count = excluded.point_count,
                updated_at = excluded.updated_at
            """,
            (
                record["source"],
                record["source_activity_id"],
                record["encoding"],
                record["payload_sha256"],
                record["payload_zlib"],
                record["point_count"],
                record["updated_at"],
            ),
        )

    def _delete_detail_payload(self, cursor, record):
        cursor.execute(
            "DELETE FROM activity_detail_payloads WHERE source = ? AND source_activity_id = ?",
            (record.get("source"), str(record.get("source_activity_id"))),
        )

    def _prune_orphaned_detail_payloads(self, cursor):
        cursor.execute(
            """
            DELETE FROM activity_detail_payloads
            WHERE NOT EXISTS (
                SELECT 1 FROM activity_registry
                WHERE activity_registry.source = activity_detail_payloads.source
                  AND activity_registry.source_activity_id = activity_detail_payloads.source_activity_id
            )
            """
        )

    def _load_detail_payloads(self, connection, *, keys=None):
        query = (
            "SELECT source, source_activity_id, encoding, payload_sha256, payload_zlib "
            "FROM activity_detail_payloads"
        )
        params = []
        if keys:
            clauses = []
            for source, source_activity_id in keys:
                clauses.append("(source = ? AND source_activity_id = ?)")
                params.extend((source, source_activity_id))
            query += " WHERE " + " OR ".join(clauses)
        try:
            rows = connection.execute(query, params).fetchall()
        except sqlite3.OperationalError as exc:
            if f"no such table: {DETAIL_PAYLOAD_TABLE}" in str(exc).lower():
                return {}
            raise
        payloads = {}
        for row in rows:
            key = (row["source"], row["source_activity_id"])
            payloads[key] = self._decode_detail_payload(row)
        return payloads

    @staticmethod
    def _decode_detail_payload(row):
        if row["encoding"] != DETAIL_PAYLOAD_ENCODING:
            raise ActivityDetailPayloadError(
                "The GeoPackage contains an unsupported activity detail payload."
            )
        try:
            encoded = zlib.decompress(row["payload_zlib"])
            if hashlib.sha256(encoded).hexdigest() != row["payload_sha256"]:
                raise ActivityDetailPayloadError(
                    "A stored activity detail payload failed its integrity check."
                )
            decoded = json.loads(encoded.decode("utf-8"))
        except ActivityDetailPayloadError:
            raise
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, zlib.error) as exc:
            raise ActivityDetailPayloadError(
                "A stored activity detail payload is corrupt and cannot be decoded."
            ) from exc
        if not isinstance(decoded, dict):
            raise ActivityDetailPayloadError(
                "A stored activity detail payload has an invalid structure."
            )
        return decoded

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

    def _database_exists(self):
        return self.db_path == ":memory:" or os.path.exists(self.db_path)


def _is_missing_sync_schema_error(exc):
    message = str(exc).lower()
    return any(
        f"no such table: {table}" in message
        for table in (SYNC_STATE_TABLE, REGISTRY_TABLE, DETAIL_PAYLOAD_TABLE)
    )
