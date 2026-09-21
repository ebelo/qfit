"""Secure reader and format adapters for Strava Bulk Data Export archives."""

from __future__ import annotations

import csv
import gzip
import hashlib
import io
import math
import posixpath
import re
import zipfile
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import PurePosixPath
from typing import Callable, Iterator
from xml.etree import ElementTree

from ...activities.domain.models import Activity
from .fit_runtime import load_fitdecode

MANIFEST_NAME = "activities.csv"
INGEST_SOURCE = "strava_bulk_export"
ACTIVITY_ID_FIELD = "Activity ID"
ACTIVITY_NAME_FIELD = "Activity Name"
ACTIVITY_TYPE_FIELD = "Activity Type"
ACTIVITY_DATE_FIELD = "Activity Date"
FILENAME_FIELD = "Filename"
MEMBER_SIZE_ERROR = "An archive member exceeds the safe expanded-size limit"
UNSAFE_MEMBER_PATH_ERROR = "The archive contains an unsafe member path"
SUPPORTED_ACTIVITY_SUFFIXES = (".fit.gz", ".tcx.gz", ".gpx.gz", ".fit", ".tcx", ".gpx")
ALLOWED_ZIP_COMPRESSION = {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}
MAIN_MANIFEST_FIELDS = {
    ACTIVITY_ID_FIELD,
    ACTIVITY_NAME_FIELD,
    ACTIVITY_TYPE_FIELD,
    ACTIVITY_DATE_FIELD,
    FILENAME_FIELD,
    "Distance",
    "Moving Time",
    "Elapsed Time",
    "Elevation Gain",
    "Average Speed",
    "Max Speed",
    "Average Heart Rate",
    "Max Heart Rate",
    "Average Watts",
    "Calories",
    "Relative Effort",
}


class StravaBulkArchiveError(RuntimeError):
    """Raised when an archive cannot be imported safely."""


class StravaBulkArchiveCancelled(RuntimeError):
    """Raised when archive validation is cancelled cooperatively."""


@dataclass(frozen=True)
class ArchiveLimits:
    max_members: int = 100_000
    max_activity_rows: int = 100_000
    max_member_bytes: int = 512 * 1024 * 1024
    max_total_bytes: int = 8 * 1024 * 1024 * 1024
    max_nested_bytes: int = 512 * 1024 * 1024
    max_xml_bytes: int = 16 * 1024 * 1024
    max_compression_ratio: float = 250.0


@dataclass(frozen=True)
class BulkArchiveEntry:
    row_number: int
    activity_id: str
    member_name: str | None
    row: dict[str, str]
    conflict_reason: str | None = None


@dataclass(frozen=True)
class BulkArchivePreflight:
    archive_fingerprint: str
    activity_count: int
    referenced_file_count: int
    summary_only_count: int
    conflict_count: int
    missing_file_count: int
    unsupported_file_count: int
    referenced_expanded_bytes: int = 0
    format_counts: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class ParsedActivityTrack:
    geometry_points: list[tuple[float, float]] = field(default_factory=list)
    stream_metrics: dict[str, list] = field(default_factory=dict)
    start_date: str | None = None
    sport_type: str | None = None

    @property
    def profile_available(self) -> bool:
        altitude = self.stream_metrics.get("altitude") or []
        distance = self.stream_metrics.get("distance") or []
        usable = sum(
            value_altitude is not None and value_distance is not None
            for value_distance, value_altitude in zip(distance, altitude)
        )
        return usable >= 2


@dataclass(frozen=True)
class BulkActivityImportResult:
    row_number: int
    activity_id: str
    status: str
    activity: Activity | None = None
    diagnostic: str | None = None


class StravaBulkArchiveReader:
    """Validate and stream recorded activities from a Strava export ZIP."""

    def __init__(self, archive_path: str, *, limits: ArchiveLimits | None = None):
        self.archive_path = archive_path
        self.limits = limits or ArchiveLimits()
        self._preflight: BulkArchivePreflight | None = None
        self._entries: list[BulkArchiveEntry] | None = None

    def preflight(
        self,
        progress: Callable[[str], None] | None = None,
        cancelled: Callable[[], bool] | None = None,
    ) -> BulkArchivePreflight:
        _raise_if_cancelled(cancelled)
        if progress is not None:
            progress("validation")
        with self._open_archive() as archive:
            infos = self._validate_central_directory(archive)
            _raise_if_cancelled(cancelled)
            info_by_name = {_normalize_member_name(info.filename): info for info in infos}
            manifest_info = info_by_name.get(MANIFEST_NAME)
            if manifest_info is None:
                raise StravaBulkArchiveError("The Strava archive does not contain activities.csv")
            self._validate_imported_member(manifest_info)
            if progress is not None:
                progress("manifest_parsing")
            manifest_bytes = self._read_zip_member(
                archive,
                manifest_info,
                cancelled=cancelled,
            )
            entries = self._read_manifest(manifest_bytes, info_by_name)
            if progress is not None:
                progress("archive_integrity")
            member_hashes = self._validate_referenced_members(
                archive,
                entries,
                info_by_name,
                cancelled=cancelled,
                initial_expanded_bytes=manifest_info.file_size,
            )

        fingerprint = _archive_fingerprint(manifest_bytes, entries, member_hashes)
        formats = Counter(
            _activity_format(entry.member_name)
            for entry in entries
            if entry.member_name and _activity_format(entry.member_name)
        )
        preflight = BulkArchivePreflight(
            archive_fingerprint=fingerprint,
            activity_count=len(entries),
            referenced_file_count=sum(bool(entry.member_name) for entry in entries),
            summary_only_count=sum(not entry.member_name for entry in entries),
            conflict_count=sum(bool(entry.conflict_reason) for entry in entries),
            missing_file_count=sum(
                bool(entry.member_name and entry.member_name not in info_by_name)
                for entry in entries
            ),
            unsupported_file_count=sum(
                bool(entry.member_name and _activity_format(entry.member_name) is None)
                for entry in entries
            ),
            referenced_expanded_bytes=sum(
                info_by_name[entry.member_name].file_size
                for entry in entries
                if entry.member_name in info_by_name
            ),
            format_counts=dict(sorted(formats.items())),
        )
        self._preflight = preflight
        self._entries = entries
        return preflight

    def iter_activity_results(
        self,
        *,
        cancelled: Callable[[], bool] | None = None,
        progress: Callable[[int, int], None] | None = None,
        integrity_progress: Callable[[int, int], None] | None = None,
    ) -> Iterator[BulkActivityImportResult]:
        preflight = self._preflight or self.preflight()
        entries = self._entries or []
        with self._open_archive() as archive:
            infos = self._validate_central_directory(archive)
            info_by_name = {
                _normalize_member_name(info.filename): info
                for info in infos
            }
            manifest_info = info_by_name.get(MANIFEST_NAME)
            if manifest_info is None:
                raise StravaBulkArchiveError(
                    "The Strava archive changed after validation"
                )
            self._validate_imported_member(manifest_info)
            manifest_bytes = self._read_zip_member(
                archive,
                manifest_info,
                cancelled=cancelled,
            )
            member_hashes = self._hash_referenced_members(
                archive,
                entries,
                info_by_name,
                cancelled=cancelled,
                progress=integrity_progress,
                initial_expanded_bytes=manifest_info.file_size,
            )
            reopened_fingerprint = _archive_fingerprint(
                manifest_bytes,
                entries,
                member_hashes,
            )
            if reopened_fingerprint != preflight.archive_fingerprint:
                raise StravaBulkArchiveError(
                    "The Strava archive changed after validation"
                )
            for completed, entry in enumerate(entries, start=1):
                if cancelled is not None and cancelled():
                    return
                yield self._import_entry(
                    archive,
                    info_by_name,
                    preflight,
                    entry,
                    cancelled=cancelled,
                )
                if progress is not None:
                    progress(completed, len(entries))

    def _open_archive(self):
        try:
            return zipfile.ZipFile(self.archive_path)
        except (OSError, zipfile.BadZipFile) as exc:
            raise StravaBulkArchiveError("The selected file is not a readable ZIP archive") from exc

    def _validate_central_directory(self, archive: zipfile.ZipFile) -> list[zipfile.ZipInfo]:
        infos = archive.infolist()
        if len(infos) > self.limits.max_members:
            raise StravaBulkArchiveError("The archive contains too many members")
        normalized_names = set()
        for info in infos:
            self._validate_central_member(info, normalized_names)
        return infos

    def _validate_central_member(self, info, normalized_names):
        normalized = _normalize_member_name(info.filename)
        if normalized in normalized_names:
            raise StravaBulkArchiveError("The archive contains duplicate normalized member paths")
        normalized_names.add(normalized)

    def _validate_imported_member(self, info):
        if info.flag_bits & 0x1:
            raise StravaBulkArchiveError("Encrypted ZIP members are not supported")
        if not info.is_dir() and info.compress_type not in ALLOWED_ZIP_COMPRESSION:
            raise StravaBulkArchiveError("The archive uses an unsupported ZIP compression method")
        if info.file_size > self.limits.max_member_bytes:
            raise StravaBulkArchiveError(MEMBER_SIZE_ERROR)
        if (
            info.file_size > 1024 * 1024
            and info.compress_size > 0
            and info.file_size / info.compress_size > self.limits.max_compression_ratio
        ):
            raise StravaBulkArchiveError("The archive contains an unsafe compression ratio")

    def _read_manifest(
        self,
        manifest_bytes: bytes,
        info_by_name: dict[str, zipfile.ZipInfo],
    ) -> list[BulkArchiveEntry]:
        try:
            text = manifest_bytes.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise StravaBulkArchiveError("activities.csv is not valid UTF-8") from exc
        reader = csv.DictReader(io.StringIO(text, newline=""))
        headers = set(reader.fieldnames or [])
        required = {
            ACTIVITY_ID_FIELD,
            ACTIVITY_DATE_FIELD,
            ACTIVITY_NAME_FIELD,
            ACTIVITY_TYPE_FIELD,
            FILENAME_FIELD,
        }
        if not required.issubset(headers):
            raise StravaBulkArchiveError("activities.csv is missing required columns")

        entries, id_counts, filename_counts = self._collect_manifest_entries(reader)
        for index, entry in enumerate(entries):
            conflict = _manifest_conflict_reason(
                entry,
                id_counts,
                filename_counts,
                info_by_name,
            )
            if conflict:
                entries[index] = _entry_with_conflict(entry, conflict)
        return entries

    def _collect_manifest_entries(self, reader):
        id_counts = Counter()
        filename_counts = Counter()
        entries = []
        for row_number, row in enumerate(reader, start=2):
            if len(entries) >= self.limits.max_activity_rows:
                raise StravaBulkArchiveError("activities.csv contains too many activity rows")
            if None in row:
                raise StravaBulkArchiveError(
                    "activities.csv contains a row with more values than headers"
                )
            activity_id = (row.get(ACTIVITY_ID_FIELD) or "").strip()
            member_name = _manifest_member_name(row.get(FILENAME_FIELD))
            id_counts[activity_id] += 1
            if member_name:
                filename_counts[member_name] += 1
            entries.append(
                BulkArchiveEntry(
                    row_number=row_number,
                    activity_id=activity_id,
                    member_name=member_name,
                    row={key: value or "" for key, value in row.items()},
                )
            )
        return entries, id_counts, filename_counts

    def _validate_referenced_members(
        self,
        archive,
        entries,
        info_by_name,
        *,
        cancelled=None,
        initial_expanded_bytes=0,
    ):
        """Verify and hash allowlisted activity members before any write."""

        referenced = {
            entry.member_name
            for entry in entries
            if entry.member_name and entry.member_name in info_by_name
        }
        total_nested_bytes = 0
        total_expanded_bytes = initial_expanded_bytes
        if total_expanded_bytes > self.limits.max_total_bytes:
            raise StravaBulkArchiveError(
                "Referenced files exceed the safe total expanded-size limit"
            )
        member_hashes = {}
        try:
            for member_name in sorted(referenced):
                info = info_by_name[member_name]
                self._validate_imported_member(info)
                total_expanded_bytes += info.file_size
                if total_expanded_bytes > self.limits.max_total_bytes:
                    raise StravaBulkArchiveError(
                        "Referenced files exceed the safe total expanded-size limit"
                    )
                nested_bytes, member_hash = self._validate_referenced_member(
                    archive,
                    info,
                    cancelled=cancelled,
                )
                total_nested_bytes += nested_bytes
                member_hashes[member_name] = member_hash
                if total_nested_bytes > self.limits.max_total_bytes:
                    raise StravaBulkArchiveError(
                        "Nested activity files exceed the safe total expanded-size limit"
                    )
        except StravaBulkArchiveCancelled:
            raise
        except (OSError, EOFError, zipfile.BadZipFile) as exc:
            raise StravaBulkArchiveError(
                "The Strava archive contains a corrupt referenced activity member"
            ) from exc
        return member_hashes

    def _validate_referenced_member(self, archive, info, *, cancelled=None):
        expanded_bytes, member_hash = self._hash_zip_member(
            archive,
            info,
            cancelled=cancelled,
        )
        if expanded_bytes != info.file_size:
            raise zipfile.BadZipFile("referenced member size mismatch")
        if not info.filename.lower().endswith(".gz"):
            return 0, member_hash
        nested_bytes = self._validate_nested_gzip_size(
            archive,
            info,
            cancelled=cancelled,
        )
        return nested_bytes, member_hash

    def _hash_referenced_members(
        self,
        archive,
        entries,
        info_by_name,
        *,
        cancelled=None,
        progress=None,
        initial_expanded_bytes=0,
    ):
        referenced = {
            entry.member_name
            for entry in entries
            if entry.member_name and entry.member_name in info_by_name
        }
        member_hashes = {}
        total_bytes = sum(info_by_name[name].file_size for name in referenced)
        if initial_expanded_bytes + total_bytes > self.limits.max_total_bytes:
            raise StravaBulkArchiveError(
                "Referenced files exceed the safe total expanded-size limit"
            )
        completed_bytes = 0
        try:
            for member_name in sorted(referenced):
                info = info_by_name[member_name]
                self._validate_imported_member(info)
                expanded_bytes, member_hash = self._hash_zip_member(
                    archive,
                    info,
                    cancelled=cancelled,
                    progress=progress,
                    progress_offset=completed_bytes,
                    progress_total=total_bytes,
                )
                if expanded_bytes != info.file_size:
                    raise zipfile.BadZipFile("referenced member size mismatch")
                member_hashes[member_name] = member_hash
                completed_bytes += expanded_bytes
        except StravaBulkArchiveCancelled:
            raise
        except (OSError, EOFError, zipfile.BadZipFile) as exc:
            raise StravaBulkArchiveError(
                "The Strava archive contains a corrupt referenced activity member"
            ) from exc
        return member_hashes

    @staticmethod
    def _hash_zip_member(
        archive,
        info,
        *,
        cancelled=None,
        progress=None,
        progress_offset=0,
        progress_total=0,
    ):
        _raise_if_cancelled(cancelled)
        digest = hashlib.sha256()
        with archive.open(info) as handle:
            expanded_bytes = 0
            while True:
                _raise_if_cancelled(cancelled)
                chunk = handle.read(1024 * 1024)
                if not chunk:
                    break
                expanded_bytes += len(chunk)
                digest.update(chunk)
                if progress is not None:
                    progress(progress_offset + expanded_bytes, progress_total)
        return expanded_bytes, digest.hexdigest()

    def _validate_nested_gzip_size(self, archive, info, *, cancelled=None):
        expanded_bytes = 0
        try:
            with archive.open(info) as zip_handle, gzip.GzipFile(fileobj=zip_handle) as handle:
                while True:
                    _raise_if_cancelled(cancelled)
                    chunk = handle.read(1024 * 1024)
                    if not chunk:
                        return expanded_bytes
                    expanded_bytes += len(chunk)
                    if expanded_bytes > self.limits.max_nested_bytes:
                        raise StravaBulkArchiveError(
                            "A nested activity file exceeds the safe expanded-size limit"
                        )
        except StravaBulkArchiveError:
            raise
        except StravaBulkArchiveCancelled:
            raise
        except (OSError, EOFError):
            # A structurally invalid activity member is isolated and reported
            # during parsing; only excessive expansion makes the archive unsafe.
            return 0

    def _import_entry(
        self,
        archive,
        info_by_name,
        preflight,
        entry,
        *,
        cancelled=None,
    ):
        if entry.conflict_reason:
            return BulkActivityImportResult(
                row_number=entry.row_number,
                activity_id=entry.activity_id,
                status="conflicted",
                diagnostic=entry.conflict_reason,
            )

        track = ParsedActivityTrack()
        member_hash = None
        source_format = None
        parse_status = "summary_only"
        diagnostic = None
        if entry.member_name:
            source_format = _activity_format(entry.member_name)
            if source_format is None:
                parse_status = "unsupported"
                diagnostic = "unsupported_activity_format"
            else:
                try:
                    payload = self._read_activity_member(
                        archive,
                        info_by_name[entry.member_name],
                        compressed=entry.member_name.lower().endswith(".gz"),
                        cancelled=cancelled,
                    )
                    member_hash = hashlib.sha256(payload).hexdigest()
                    track = _parse_activity_payload(
                        payload,
                        source_format,
                        cancelled=cancelled,
                    )
                    parse_status = _track_status(track)
                except (OSError, ValueError, ElementTree.ParseError, EOFError, ImportError) as exc:
                    parse_status = "failed"
                    diagnostic = _safe_parser_diagnostic(exc)

        activity = _activity_from_manifest(
            entry,
            track,
            archive_fingerprint=preflight.archive_fingerprint,
            source_format=source_format,
            member_hash=member_hash,
            parse_status=parse_status,
        )
        return BulkActivityImportResult(
            row_number=entry.row_number,
            activity_id=entry.activity_id,
            status=parse_status,
            activity=activity,
            diagnostic=diagnostic,
        )

    def _read_zip_member(self, archive, info, *, cancelled=None):
        if info.file_size > self.limits.max_member_bytes:
            raise StravaBulkArchiveError(MEMBER_SIZE_ERROR)
        with archive.open(info) as handle:
            buffer = io.BytesIO()
            while True:
                _raise_if_cancelled(cancelled)
                chunk = handle.read(1024 * 1024)
                if not chunk:
                    return buffer.getvalue()
                buffer.write(chunk)
                if buffer.tell() > self.limits.max_member_bytes:
                    raise StravaBulkArchiveError(MEMBER_SIZE_ERROR)

    def _read_activity_member(self, archive, info, *, compressed, cancelled=None):
        source_format = _activity_format(info.filename)
        is_xml = source_format in {"gpx", "tcx"}
        expanded_limit = (
            self.limits.max_xml_bytes
            if is_xml
            else self.limits.max_nested_bytes
        )
        if not compressed and info.file_size > expanded_limit:
            raise ValueError("activity file exceeds the safe parser-size limit")
        if not compressed:
            return self._read_zip_member(archive, info, cancelled=cancelled)
        try:
            with archive.open(info) as zip_handle, gzip.GzipFile(
                fileobj=zip_handle
            ) as handle:
                buffer = io.BytesIO()
                while True:
                    _raise_if_cancelled(cancelled)
                    chunk = handle.read(1024 * 1024)
                    if not chunk:
                        expanded = buffer.getvalue()
                        break
                    buffer.write(chunk)
                    if buffer.tell() > expanded_limit:
                        raise ValueError(
                            "activity file exceeds the safe parser-size limit"
                        )
        except (OSError, EOFError) as exc:
            raise ValueError("invalid nested gzip activity file") from exc
        return expanded


def _normalize_member_name(raw_name: str) -> str:
    candidate = str(raw_name or "").replace("\\", "/")
    if not candidate or candidate.startswith("/") or re.match(r"^[A-Za-z]:", candidate):
        raise StravaBulkArchiveError(UNSAFE_MEMBER_PATH_ERROR)
    if ".." in PurePosixPath(candidate).parts:
        raise StravaBulkArchiveError(UNSAFE_MEMBER_PATH_ERROR)
    normalized = posixpath.normpath(candidate)
    parts = PurePosixPath(normalized).parts
    if normalized in ("", ".") or ".." in parts:
        raise StravaBulkArchiveError(UNSAFE_MEMBER_PATH_ERROR)
    return normalized


def _raise_if_cancelled(cancelled):
    if cancelled is not None and cancelled():
        raise StravaBulkArchiveCancelled("Strava bulk archive validation cancelled")


def _manifest_member_name(value: str | None) -> str | None:
    if not value or not value.strip():
        return None
    return _normalize_member_name(value.strip())


def _manifest_conflict_reason(entry, id_counts, filename_counts, info_by_name):
    if not entry.activity_id:
        return "missing_activity_id"
    if id_counts[entry.activity_id] > 1:
        return "duplicate_activity_id"
    if entry.member_name and filename_counts[entry.member_name] > 1:
        return "duplicate_activity_filename"
    if entry.member_name and entry.member_name not in info_by_name:
        return "missing_activity_file"
    return None


def _entry_with_conflict(entry, conflict):
    return BulkArchiveEntry(
        row_number=entry.row_number,
        activity_id=entry.activity_id,
        member_name=entry.member_name,
        row=entry.row,
        conflict_reason=conflict,
    )


def _activity_format(member_name: str | None) -> str | None:
    lowered = (member_name or "").lower()
    for suffix in SUPPORTED_ACTIVITY_SUFFIXES:
        if lowered.endswith(suffix):
            return suffix.removeprefix(".").removesuffix(".gz")
    return None


def _archive_fingerprint(manifest_bytes, entries, member_hashes):
    digest = hashlib.sha256(manifest_bytes)
    for entry in entries:
        if not entry.member_name:
            continue
        digest.update(entry.member_name.encode("utf-8"))
        member_hash = member_hashes.get(entry.member_name)
        digest.update((member_hash or "missing").encode("ascii"))
    return digest.hexdigest()


def _parse_activity_payload(
    payload: bytes,
    source_format: str,
    *,
    cancelled=None,
) -> ParsedActivityTrack:
    if source_format == "fit":
        return _parse_fit(payload, cancelled=cancelled)
    if source_format == "tcx":
        return _parse_tcx(payload, cancelled=cancelled)
    if source_format == "gpx":
        return _parse_gpx(payload, cancelled=cancelled)
    raise ValueError("unsupported activity format")


def _parse_fit(payload: bytes, *, cancelled=None) -> ParsedActivityTrack:
    fitdecode = load_fitdecode()
    points = []
    metric_rows = []
    first_timestamp = None
    start_date = None
    sport_type = None
    try:
        with fitdecode.FitReader(
            io.BytesIO(payload),
            check_crc=fitdecode.CrcCheck.WARN,
        ) as reader:
            for frame in reader:
                _raise_if_cancelled(cancelled)
                if not isinstance(frame, fitdecode.FitDataMessage):
                    continue
                frame_fields = {
                    item.name: item.value
                    for item in frame.fields
                    if item.value is not None
                }
                if frame.name == "session":
                    start_date = start_date or _iso_utc(frame_fields.get("start_time"))
                    sport_type = (
                        frame_fields.get("sub_sport")
                        or frame_fields.get("sport")
                        or sport_type
                    )
                    continue
                if frame.name != "record":
                    continue
                lat = _fit_coordinate(frame_fields.get("position_lat"))
                lon = _fit_coordinate(frame_fields.get("position_long"))
                if not _valid_coordinate(lat, lon):
                    continue
                timestamp = frame_fields.get("timestamp")
                first_timestamp = first_timestamp or timestamp
                points.append((lat, lon))
                metric_rows.append(
                    {
                        "time": _seconds_between(first_timestamp, timestamp),
                        "distance": _float_or_none(frame_fields.get("distance")),
                        "altitude": _float_or_none(
                            frame_fields.get(
                                "enhanced_altitude",
                                frame_fields.get("altitude"),
                            )
                        ),
                        "heartrate": _float_or_none(frame_fields.get("heart_rate")),
                        "cadence": _float_or_none(frame_fields.get("cadence")),
                        "watts": _float_or_none(frame_fields.get("power")),
                        "velocity_smooth": _float_or_none(
                            frame_fields.get(
                                "enhanced_speed",
                                frame_fields.get("speed"),
                            )
                        ),
                        "temp": _float_or_none(frame_fields.get("temperature")),
                        "grade_smooth": _float_or_none(frame_fields.get("grade")),
                    }
                )
    except fitdecode.FitError as exc:
        raise ValueError("invalid FIT activity file") from exc
    return _finalize_track(
        points,
        metric_rows,
        start_date=start_date or _iso_utc(first_timestamp),
        sport_type=str(sport_type) if sport_type else None,
    )


def _parse_tcx(payload: bytes, *, cancelled=None) -> ParsedActivityTrack:
    root = _safe_xml_root(payload, cancelled=cancelled)
    points = []
    metric_rows = []
    first_timestamp = None
    sport_type = None
    segment_starts = set()
    for element in root.iter():
        _raise_if_cancelled(cancelled)
        if _local_name(element.tag) == "Activity" and sport_type is None:
            sport_type = element.attrib.get("Sport")

    def append_point(element):
        nonlocal first_timestamp
        _raise_if_cancelled(cancelled)
        values = {_local_name(item.tag): item for item in element.iter()}
        position = values.get("Position")
        if position is None:
            return
        coordinates = {_local_name(item.tag): item for item in position.iter()}
        lat = _element_float(coordinates.get("LatitudeDegrees"))
        lon = _element_float(coordinates.get("LongitudeDegrees"))
        if not _valid_coordinate(lat, lon):
            return
        timestamp = _element_datetime(values.get("Time"))
        first_timestamp = first_timestamp or timestamp
        points.append((lat, lon))
        metric_rows.append(
            {
                "time": _seconds_between(first_timestamp, timestamp),
                "distance": _element_float(values.get("DistanceMeters")),
                "altitude": _element_float(values.get("AltitudeMeters")),
                "heartrate": _nested_element_float(values.get("HeartRateBpm"), "Value"),
                "cadence": _element_float(values.get("Cadence")),
                "watts": _first_named_float(element, ("Watts", "Power")),
                "velocity_smooth": _first_named_float(element, ("Speed",)),
            }
        )

    for candidates in _tcx_point_groups(root, cancelled=cancelled):
        segment_start = len(points)
        for candidate in candidates:
            append_point(candidate)
        if len(points) > segment_start:
            segment_starts.add(segment_start)
    return _finalize_track(
        points,
        metric_rows,
        start_date=_iso_utc(first_timestamp),
        sport_type=sport_type,
        segment_starts=segment_starts,
    )


def _tcx_point_groups(root, *, cancelled=None):
    tracks = _xml_elements_named(
        root.iter(),
        {"Track"},
        cancelled=cancelled,
    )
    if not tracks:
        candidates = _xml_elements_named(
            root.iter(),
            {"Trackpoint"},
            cancelled=cancelled,
        )
        return [candidates] if candidates else []
    return [
        _xml_elements_named(track, {"Trackpoint"}, cancelled=cancelled)
        for track in tracks
    ]


def _parse_gpx(payload: bytes, *, cancelled=None) -> ParsedActivityTrack:
    root = _safe_xml_root(payload, cancelled=cancelled)
    points = []
    metric_rows = []
    first_timestamp = None
    segment_starts = set()

    def append_point(element):
        nonlocal first_timestamp
        _raise_if_cancelled(cancelled)
        lat = _float_or_none(element.attrib.get("lat"))
        lon = _float_or_none(element.attrib.get("lon"))
        if not _valid_coordinate(lat, lon):
            return
        children = {_local_name(item.tag): item for item in element.iter()}
        timestamp = _element_datetime(children.get("time"))
        first_timestamp = first_timestamp or timestamp
        points.append((lat, lon))
        metric_rows.append(
            {
                "time": _seconds_between(first_timestamp, timestamp),
                "distance": None,
                "altitude": _element_float(children.get("ele")),
                "heartrate": _element_float(children.get("hr")),
                "cadence": _element_float(children.get("cad")),
                "watts": _first_named_float(element, ("power", "Power", "watts", "Watts")),
                "velocity_smooth": _first_named_float(element, ("speed", "Speed")),
                "temp": _first_named_float(element, ("atemp", "temp", "Temperature")),
            }
        )

    for candidates in _gpx_point_groups(root, cancelled=cancelled):
        segment_starts.add(len(points))
        for candidate in candidates:
            append_point(candidate)
    return _finalize_track(
        points,
        metric_rows,
        start_date=_iso_utc(first_timestamp),
        segment_starts=segment_starts,
    )


def _gpx_point_groups(root, *, cancelled=None):
    containers = _xml_elements_named(
        root.iter(),
        {"trkseg", "rte"},
        cancelled=cancelled,
    )
    if not containers:
        candidates = _xml_elements_named(
            root.iter(),
            {"trkpt", "rtept"},
            cancelled=cancelled,
        )
        return [candidates] if candidates else []
    groups = []
    for container in containers:
        _raise_if_cancelled(cancelled)
        point_name = "trkpt" if _local_name(container.tag) == "trkseg" else "rtept"
        candidates = _xml_elements_named(
            container,
            {point_name},
            cancelled=cancelled,
        )
        if candidates:
            groups.append(candidates)
    return groups


def _xml_elements_named(elements, names, *, cancelled=None):
    matches = []
    for element in elements:
        _raise_if_cancelled(cancelled)
        if _local_name(element.tag) in names:
            matches.append(element)
    return matches


def _safe_xml_root(payload: bytes, *, cancelled=None):
    stripped = payload.lstrip()
    parser = ElementTree.XMLParser(target=_RejectDtdTreeBuilder())
    for offset in range(0, len(stripped), 1024 * 1024):
        _raise_if_cancelled(cancelled)
        chunk = stripped[offset : offset + 1024 * 1024]
        parser.feed(chunk)
    _raise_if_cancelled(cancelled)
    return parser.close()


class _RejectDtdTreeBuilder(ElementTree.TreeBuilder):
    def doctype(self, name, pubid, system):
        del name, pubid, system
        raise ValueError("XML document type declarations are not supported")


def _finalize_track(
    points,
    metric_rows,
    *,
    start_date=None,
    sport_type=None,
    segment_starts=None,
):
    if not points:
        return ParsedActivityTrack(start_date=start_date, sport_type=sport_type)
    distances = _filled_distances(
        points,
        [row.get("distance") for row in metric_rows],
        segment_starts=segment_starts,
    )
    keys = (
        "time",
        "distance",
        "altitude",
        "heartrate",
        "cadence",
        "watts",
        "velocity_smooth",
        "temp",
        "grade_smooth",
        "moving",
    )
    metrics = {}
    for key in keys:
        values = distances if key == "distance" else [row.get(key) for row in metric_rows]
        if any(value is not None for value in values):
            metrics[key] = values
    return ParsedActivityTrack(
        geometry_points=points,
        stream_metrics=metrics,
        start_date=start_date,
        sport_type=sport_type,
    )


def _filled_distances(points, values, *, segment_starts=None):
    segment_starts = set(segment_starts or ())
    distances = []
    for index, point in enumerate(points):
        provided = _float_or_none(values[index]) if index < len(values) else None
        if index == 0:
            distances.append(max(provided or 0.0, 0.0))
            continue
        segment = 0.0 if index in segment_starts else _haversine_m(points[index - 1], point)
        minimum = distances[-1] + segment
        distances.append(provided if provided is not None and provided >= distances[-1] else minimum)
    return distances


def _haversine_m(start, end):
    lat1, lon1 = map(math.radians, start)
    lat2, lon2 = map(math.radians, end)
    delta_lat = lat2 - lat1
    delta_lon = lon2 - lon1
    value = (
        math.sin(delta_lat / 2.0) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(delta_lon / 2.0) ** 2
    )
    return 6_371_008.8 * 2.0 * math.atan2(math.sqrt(value), math.sqrt(max(0.0, 1.0 - value)))


def _valid_coordinate(lat, lon):
    return (
        lat is not None
        and lon is not None
        and -90.0 <= lat <= 90.0
        and -180.0 <= lon <= 180.0
    )


def _activity_from_manifest(
    entry,
    track,
    *,
    archive_fingerprint,
    source_format,
    member_hash,
    parse_status,
):
    row = entry.row
    points = track.geometry_points
    details = {
        "ingest_source": INGEST_SOURCE,
        "ingest_sources": [INGEST_SOURCE],
        "bulk_import": {
            "schema_version": 1,
            "archive_fingerprint": archive_fingerprint,
            "member_identity": entry.member_name,
            "member_sha256": member_hash,
            "parse_status": parse_status,
            "source_format": source_format,
        },
        "bulk_imported_at": datetime.now(UTC).isoformat(),
        "bulk_summary": {
            "schema_version": 1,
            "values": _extra_manifest_values(row),
        },
    }
    if track.stream_metrics:
        details["stream_metrics"] = track.stream_metrics
        details["stream_metric_keys"] = sorted(track.stream_metrics)
        details["stream_point_count"] = len(points)
    if points:
        details["geometry_ingest_source"] = INGEST_SOURCE
    return Activity(
        source="strava",
        source_activity_id=entry.activity_id,
        name=_none_if_blank(row.get(ACTIVITY_NAME_FIELD)),
        activity_type=_none_if_blank(row.get(ACTIVITY_TYPE_FIELD)),
        sport_type=track.sport_type or _none_if_blank(row.get(ACTIVITY_TYPE_FIELD)),
        start_date=track.start_date,
        start_date_local=_manifest_date(row.get(ACTIVITY_DATE_FIELD)),
        distance_m=_float_or_none(row.get("Distance")),
        moving_time_s=_int_or_none(row.get("Moving Time")),
        elapsed_time_s=_int_or_none(row.get("Elapsed Time")),
        total_elevation_gain_m=_float_or_none(row.get("Elevation Gain")),
        average_speed_mps=_float_or_none(row.get("Average Speed")),
        max_speed_mps=_float_or_none(row.get("Max Speed")),
        average_heartrate=_float_or_none(row.get("Average Heart Rate")),
        max_heartrate=_float_or_none(row.get("Max Heart Rate")),
        average_watts=_float_or_none(row.get("Average Watts")),
        calories=_float_or_none(row.get("Calories")),
        suffer_score=_float_or_none(row.get("Relative Effort")),
        start_lat=points[0][0] if points else None,
        start_lon=points[0][1] if points else None,
        end_lat=points[-1][0] if points else None,
        end_lon=points[-1][1] if points else None,
        geometry_source="stream" if points else None,
        geometry_points=points,
        details_json=details,
    )


def _track_status(track):
    if not track.geometry_points:
        return "no_gps"
    if track.profile_available:
        return "detailed_profile"
    return "detailed_no_altitude"


def _extra_manifest_values(row):
    return {
        key: value
        for key, value in row.items()
        if key not in MAIN_MANIFEST_FIELDS and value not in (None, "")
    }


def _manifest_date(value):
    text = (value or "").strip()
    if not text:
        return None
    for pattern in ("%b %d, %Y, %I:%M:%S %p", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(text, pattern).isoformat()
        except ValueError:
            continue
    return text


def _fit_coordinate(value):
    numeric = _float_or_none(value)
    if numeric is None:
        return None
    return numeric * 180.0 / float(2**31)


def _seconds_between(start, end):
    if start is None or end is None:
        return None
    try:
        return max(int(round((end - start).total_seconds())), 0)
    except (AttributeError, TypeError, ValueError):
        return None


def _iso_utc(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
    text = str(value).strip()
    return text or None


def _local_name(tag):
    return str(tag).rsplit("}", 1)[-1]


def _element_float(element):
    return _float_or_none(element.text if element is not None else None)


def _nested_element_float(element, name):
    if element is None:
        return None
    for child in element.iter():
        if _local_name(child.tag) == name:
            return _element_float(child)
    return None


def _first_named_float(element, names):
    for child in element.iter():
        if _local_name(child.tag) in names:
            value = _element_float(child)
            if value is not None:
                return value
    return None


def _element_datetime(element):
    if element is None or not element.text:
        return None
    try:
        return datetime.fromisoformat(element.text.strip().replace("Z", "+00:00"))
    except ValueError:
        return None


def _float_or_none(value):
    if value is None or str(value).strip() == "":
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    return numeric if math.isfinite(numeric) else None


def _int_or_none(value):
    numeric = _float_or_none(value)
    return int(round(numeric)) if numeric is not None else None


def _none_if_blank(value):
    text = str(value or "").strip()
    return text or None


def _safe_parser_diagnostic(exc):
    if isinstance(exc, ImportError):
        return "fit_runtime_unavailable"
    if isinstance(exc, ElementTree.ParseError):
        return "invalid_xml_activity_file"
    if isinstance(exc, (EOFError, gzip.BadGzipFile)):
        return "invalid_compressed_activity_file"
    return "invalid_activity_file"


__all__ = [
    "ArchiveLimits",
    "BulkActivityImportResult",
    "BulkArchivePreflight",
    "ParsedActivityTrack",
    "StravaBulkArchiveError",
    "StravaBulkArchiveReader",
]
