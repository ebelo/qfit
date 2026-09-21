"""Bounded, resumable Strava Bulk Data Export import workflow."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable

from ..domain.models import Activity
from ..domain.activity_reconciliation import reconcile_activity_records
from ...providers.infrastructure.strava_bulk_archive import (
    BulkArchivePreflight,
    StravaBulkArchiveError,
    StravaBulkArchiveReader,
)
from ...sync_repository import SyncStats


@dataclass(frozen=True)
class StravaBulkImportRequest:
    archive_path: str
    output_path: str
    batch_size: int = 25
    write_activity_points: bool = True
    point_stride: int = 5
    expected_archive_fingerprint: str | None = None


@dataclass(frozen=True)
class StravaBulkImportProgress:
    phase: str
    completed: int = 0
    total: int = 0
    elapsed_seconds: float = 0.0
    eta_seconds: float | None = None
    message: str = ""

    @property
    def percent(self) -> float:
        fixed = {
            "queued": 0.0,
            "validation": 1.0,
            "manifest_parsing": 3.0,
            "complete": 100.0,
        }
        if self.phase in fixed:
            return fixed[self.phase]
        if self.phase == "archive_integrity":
            if self.total <= 0:
                return 3.0
            ratio = min(max(self.completed / self.total, 0.0), 1.0)
            return 3.0 + 2.0 * ratio
        if self.total <= 0:
            return 0.0
        ratio = min(max(self.completed / self.total, 0.0), 1.0)
        if self.phase in ("activity_parsing", "reconciliation"):
            return 5.0 + 80.0 * ratio
        if self.phase == "derived_layers":
            return 85.0 + 15.0 * ratio
        return 100.0 * ratio


@dataclass(frozen=True)
class StravaBulkImportResult:
    preflight: BulkArchivePreflight
    inserted: int = 0
    updated: int = 0
    unchanged: int = 0
    summary_only: int = 0
    no_altitude: int = 0
    unsupported: int = 0
    conflicted: int = 0
    failed: int = 0
    no_gps: int = 0
    cancelled: bool = False
    total_stored: int = 0
    diagnostic_lines: tuple[str, ...] = ()
    layer_counts: dict[str, int] = field(default_factory=dict)

    @property
    def imported_count(self) -> int:
        return self.inserted + self.updated + self.unchanged

    def private_diagnostic_report(self) -> str:
        lines = [
            "qfit Strava bulk import report",
            f"activities={self.preflight.activity_count}",
            f"inserted={self.inserted}",
            f"updated={self.updated}",
            f"unchanged={self.unchanged}",
            f"summary_only={self.summary_only}",
            f"no_gps={self.no_gps}",
            f"no_altitude={self.no_altitude}",
            f"unsupported={self.unsupported}",
            f"conflicted={self.conflicted}",
            f"failed={self.failed}",
            f"cancelled={str(self.cancelled).lower()}",
        ]
        lines.extend(self.diagnostic_lines)
        return "\n".join(lines)


WriterFactory = Callable[..., object]
ProgressCallback = Callable[[StravaBulkImportProgress], None]
CancelCallback = Callable[[], bool]


class StravaBulkImportWorkflow:
    """Parse, reconcile, and persist one export without loading it all in memory."""

    def __init__(self, *, writer_factory: WriterFactory | None = None, reader_factory=None):
        self._writer_factory = writer_factory
        self._reader_factory = reader_factory or StravaBulkArchiveReader

    def preflight(
        self,
        archive_path: str,
        *,
        progress=None,
        cancelled=None,
    ) -> BulkArchivePreflight:
        return self._reader_factory(archive_path).preflight(
            progress=progress,
            cancelled=cancelled,
        )

    def run(
        self,
        request: StravaBulkImportRequest,
        *,
        cancelled: CancelCallback | None = None,
        progress: ProgressCallback | None = None,
    ) -> StravaBulkImportResult:
        if not request.archive_path:
            raise ValueError("archive_path is required")
        if not request.output_path:
            raise ValueError("output_path is required")
        batch_size = max(int(request.batch_size), 1)
        started = time.monotonic()
        reader = self._reader_factory(request.archive_path)
        preflight = reader.preflight(
            progress=lambda phase: self._report(
                progress,
                phase,
                message=_preflight_phase_message(phase),
            ),
            cancelled=cancelled,
        )
        if (
            request.expected_archive_fingerprint is not None
            and preflight.archive_fingerprint != request.expected_archive_fingerprint
        ):
            raise StravaBulkArchiveError(
                "The Strava archive changed after confirmation; validate it again"
            )
        if self._is_cancelled(cancelled):
            return StravaBulkImportResult(preflight=preflight, cancelled=True)

        writer = self._build_writer(request)
        activity_store = writer.prepare_activity_storage()
        counters = self._empty_counters()
        diagnostic_lines = []
        was_cancelled = self._consume_activity_results(
            reader,
            writer,
            activity_store,
            batch_size=batch_size,
            total=preflight.activity_count,
            started=started,
            cancelled=cancelled,
            progress=progress,
            counters=counters,
            diagnostics=diagnostic_lines,
        )
        if was_cancelled:
            return self._result(
                preflight,
                counters,
                activity_store,
                cancelled=True,
                diagnostics=diagnostic_lines,
            )

        self._report(
            progress,
            "derived_layers",
            completed=0,
            total=preflight.activity_count,
            elapsed_seconds=time.monotonic() - started,
            message="Rebuilding derived map and profile layers",
        )
        layers = self._rebuild_layers(
            writer,
            activity_store,
            batch_size=batch_size,
            started=started,
            progress=progress,
        )
        layer_counts = {
            name: layer.featureCount()
            for name, layer in layers.items()
            if hasattr(layer, "featureCount")
        }
        result = self._result(
            preflight,
            counters,
            activity_store,
            cancelled=False,
            diagnostics=diagnostic_lines,
            layer_counts=layer_counts,
        )
        self._report(
            progress,
            "complete",
            completed=preflight.activity_count,
            total=preflight.activity_count,
            elapsed_seconds=time.monotonic() - started,
            eta_seconds=0.0,
            message="Bulk import complete",
        )
        return result

    def _build_writer(self, request):
        if self._writer_factory is None:
            from ..infrastructure.geopackage.gpkg_writer import GeoPackageWriter

            factory = GeoPackageWriter
        else:
            factory = self._writer_factory
        return factory(
            output_path=request.output_path,
            write_activity_points=request.write_activity_points,
            point_stride=request.point_stride,
        )

    @staticmethod
    def _commit_batch(writer, activity_store, batch, counters):
        stats: SyncStats = writer.upsert_activity_batch(
            activity_store,
            batch,
            compress_detail_payloads=True,
        )
        counters["inserted"] += stats.inserted
        counters["updated"] += stats.updated
        counters["unchanged"] += stats.unchanged

    def _consume_activity_results(
        self,
        reader,
        writer,
        activity_store,
        *,
        batch_size,
        total,
        started,
        cancelled,
        progress,
        counters,
        diagnostics,
    ):
        batch = []
        integrity_started = time.monotonic()

        def on_integrity(completed, total):
            phase_elapsed = time.monotonic() - integrity_started
            rate = completed / phase_elapsed if phase_elapsed > 0 else 0.0
            eta = (total - completed) / rate if rate > 0 else None
            self._report(
                progress,
                "archive_integrity",
                completed=completed,
                total=total,
                elapsed_seconds=time.monotonic() - started,
                eta_seconds=eta,
                message=(
                    f"Verified {_format_byte_count(completed)} of "
                    f"{_format_byte_count(total)}"
                ),
            )

        def on_parsed(completed, total):
            elapsed = time.monotonic() - started
            rate = completed / elapsed if elapsed > 0 else 0.0
            remaining_work = (total - completed) + total * 0.2
            eta = remaining_work / rate if rate > 0 else None
            self._report(
                progress,
                "activity_parsing",
                completed=completed,
                total=total,
                elapsed_seconds=elapsed,
                eta_seconds=eta,
                message=f"Parsed {completed} of {total} activities",
            )

        results = reader.iter_activity_results(
            cancelled=cancelled,
            progress=on_parsed,
            integrity_progress=on_integrity,
        )
        for completed, parsed in enumerate(results, start=1):
            self._report(
                progress,
                "reconciliation",
                completed=completed,
                total=total,
                elapsed_seconds=time.monotonic() - started,
                message=f"Reconciling activity {completed}",
            )
            self._record_parsed_result(
                parsed,
                batch,
                counters,
                diagnostics,
            )
            if len(batch) >= batch_size:
                self._commit_batch(writer, activity_store, batch, counters)
                batch.clear()
        was_cancelled = self._is_cancelled(cancelled)
        if batch:
            self._commit_batch(writer, activity_store, batch, counters)
        return was_cancelled

    @staticmethod
    def _record_parsed_result(parsed, batch, counters, diagnostics):
        status = parsed.status
        if status in counters:
            counters[status] += 1
        if status == "detailed_no_altitude":
            counters["no_altitude"] += 1
        if parsed.diagnostic:
            diagnostics.append(
                f"row={parsed.row_number} activity_id={parsed.activity_id or '-'} "
                f"status={status} reason={parsed.diagnostic}"
            )
        if parsed.activity is None:
            return
        batch.append(parsed.activity)

    def _rebuild_layers(
        self,
        writer,
        activity_store,
        *,
        batch_size,
        started,
        progress,
    ):
        if not hasattr(writer, "rebuild_activity_layers_bounded"):
            return writer.rebuild_activity_layers(activity_store=activity_store)

        rebuild_started = time.monotonic()

        def on_rebuild(layer, completed, total, index, count):
            overall_completed = index * total + completed
            overall_total = count * total
            elapsed = time.monotonic() - rebuild_started
            rate = overall_completed / elapsed if elapsed > 0 else 0.0
            eta = (
                (overall_total - overall_completed) / rate
                if rate > 0
                else None
            )
            self._report(
                progress,
                "derived_layers",
                completed=overall_completed,
                total=overall_total,
                elapsed_seconds=time.monotonic() - started,
                eta_seconds=eta,
                message=f"Rebuilding {layer}: {completed} of {total}",
            )

        return writer.rebuild_activity_layers_bounded(
            activity_store=activity_store,
            batch_size=batch_size,
            progress=on_rebuild,
        )

    @staticmethod
    def _empty_counters():
        return {
            "inserted": 0,
            "updated": 0,
            "unchanged": 0,
            "summary_only": 0,
            "no_altitude": 0,
            "unsupported": 0,
            "conflicted": 0,
            "failed": 0,
            "no_gps": 0,
        }

    @staticmethod
    def _result(
        preflight,
        counters,
        activity_store,
        *,
        cancelled,
        diagnostics,
        layer_counts=None,
    ):
        count_loader = getattr(activity_store, "load_activity_count", None)
        total_stored = (
            count_loader()
            if count_loader is not None
            else len(activity_store.load_all_activity_records())
        )
        return StravaBulkImportResult(
            preflight=preflight,
            cancelled=cancelled,
            total_stored=total_stored,
            diagnostic_lines=tuple(diagnostics),
            layer_counts=layer_counts or {},
            **counters,
        )

    @staticmethod
    def _is_cancelled(cancelled):
        return bool(cancelled and cancelled())

    @staticmethod
    def _report(callback, phase, **kwargs):
        if callback is not None:
            callback(StravaBulkImportProgress(phase=phase, **kwargs))


def reconcile_bulk_activity(incoming: Activity, existing_record: dict | None) -> Activity:
    """Merge archive data by Strava ID while preserving local and richer data."""

    return Activity(
        **reconcile_activity_records(incoming.to_record(), existing_record)
    )


def _preflight_phase_message(phase):
    return {
        "validation": "Validating archive directory",
        "manifest_parsing": "Parsing activity manifest",
        "archive_integrity": "Checking referenced activity files",
    }.get(phase, "Validating archive")


def _format_byte_count(value):
    value = max(int(value), 0)
    if value < 1024:
        return f"{value} B"
    if value < 1024 * 1024:
        return f"{value / 1024:.1f} KiB"
    if value < 1024 * 1024 * 1024:
        return f"{value / (1024 * 1024):.1f} MiB"
    return f"{value / (1024 * 1024 * 1024):.1f} GiB"


__all__ = [
    "StravaBulkImportProgress",
    "StravaBulkImportRequest",
    "StravaBulkImportResult",
    "StravaBulkImportWorkflow",
    "reconcile_bulk_activity",
]
