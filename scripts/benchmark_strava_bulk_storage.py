#!/usr/bin/env python3
"""Compare legacy JSON and compressed-detail storage with synthetic activities."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
import tracemalloc
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_PARENT = REPOSITORY_ROOT.parent
if str(REPOSITORY_PARENT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_PARENT))

from qfit.activities.domain.models import Activity  # noqa: E402
from qfit.sync_repository import SyncRepository  # noqa: E402


def _activity(activity_index, point_count):
    points = [
        (46.0 + activity_index * 0.00001 + index * 0.000001, 7.0 + index * 0.000001)
        for index in range(point_count)
    ]
    return Activity(
        source="strava",
        source_activity_id=str(activity_index),
        name=f"Synthetic {activity_index}",
        activity_type="Ride",
        distance_m=float(point_count * 10),
        geometry_source="stream",
        geometry_points=points,
        details_json={
            "stream_metrics": {
                "distance": [float(index * 10) for index in range(point_count)],
                "altitude": [500.0 + index % 50 for index in range(point_count)],
                "heartrate": [120 + index % 30 for index in range(point_count)],
            }
        },
    )


def _run_case(path, *, activities, points, batch_size, compressed):
    repository = SyncRepository(str(path))
    repository.ensure_schema()
    tracemalloc.start()
    started = time.perf_counter()
    for first in range(0, activities, batch_size):
        batch = [
            _activity(index, points)
            for index in range(first, min(first + batch_size, activities))
        ]
        repository.upsert_activities(
            batch,
            sync_metadata={"suppress_sync_state": True},
            compress_detail_payloads=compressed,
        )
    write_seconds = time.perf_counter() - started
    _current, peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    reopen_started = time.perf_counter()
    reopened = SyncRepository(str(path)).load_all_activity_records()
    reopen_seconds = time.perf_counter() - reopen_started
    return {
        "write_seconds": round(write_seconds, 3),
        "peak_memory_mib": round(peak_bytes / 1024 / 1024, 2),
        "database_mib": round(path.stat().st_size / 1024 / 1024, 2),
        "reopen_seconds": round(reopen_seconds, 3),
        "reopened_activities": len(reopened),
    }


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--activities", type=int, default=3000)
    parser.add_argument("--points", type=int, default=500)
    parser.add_argument("--batch-size", type=int, default=25)
    args = parser.parse_args(argv)
    with tempfile.TemporaryDirectory(prefix="qfit-bulk-benchmark-") as temp_dir:
        root = Path(temp_dir)
        result = {
            "configuration": vars(args),
            "legacy_json": _run_case(
                root / "legacy.sqlite",
                activities=args.activities,
                points=args.points,
                batch_size=args.batch_size,
                compressed=False,
            ),
            "compressed_payload": _run_case(
                root / "compressed.sqlite",
                activities=args.activities,
                points=args.points,
                batch_size=args.batch_size,
                compressed=True,
            ),
        }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
