from __future__ import annotations

import csv
import gzip
import io
import tempfile
import unittest
import zipfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from qfit.providers.infrastructure.strava_bulk_archive import (
    ArchiveLimits,
    StravaBulkArchiveCancelled,
    StravaBulkArchiveError,
    StravaBulkArchiveReader,
)


MANIFEST_FIELDS = [
    "Activity ID",
    "Activity Date",
    "Activity Name",
    "Activity Type",
    "Filename",
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
]


def _manifest(rows):
    handle = io.StringIO(newline="")
    writer = csv.DictWriter(handle, fieldnames=MANIFEST_FIELDS)
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return handle.getvalue().encode("utf-8")


def _row(activity_id="activity-1", filename="activities/arbitrary-name.gpx", **overrides):
    row = {
        "Activity ID": activity_id,
        "Activity Date": "Sep 21, 2026, 7:30:00 AM",
        "Activity Name": "Morning activity",
        "Activity Type": "Run",
        "Filename": filename,
        "Distance": "1500.5",
        "Moving Time": "600",
        "Elapsed Time": "650",
        "Elevation Gain": "42.5",
        "Average Speed": "2.5",
        "Max Speed": "4.2",
        "Average Heart Rate": "140",
        "Max Heart Rate": "170",
        "Average Watts": "220",
        "Calories": "350",
        "Relative Effort": "45",
    }
    row.update(overrides)
    return row


def _gpx(*, elevation=True, include_distance=False):
    points = []
    for index, (lat, lon, altitude) in enumerate(
        ((46.0, 7.0, 500.0), (46.001, 7.002, 510.0), (46.002, 7.004, 505.0))
    ):
        elevation_xml = f"<ele>{altitude}</ele>" if elevation else ""
        distance_xml = f"<extensions><distance>{index * 100}</distance></extensions>" if include_distance else ""
        points.append(
            f'<trkpt lat="{lat}" lon="{lon}">{elevation_xml}'
            f"<time>2026-09-21T05:{30 + index:02d}:00Z</time>{distance_xml}</trkpt>"
        )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<gpx xmlns="http://www.topografix.com/GPX/1/1"><trk><trkseg>'
        + "".join(points)
        + "</trkseg></trk></gpx>"
    ).encode("utf-8")


def _segmented_gpx():
    return b"""<?xml version="1.0" encoding="UTF-8"?>
<gpx xmlns="http://www.topografix.com/GPX/1/1">
  <trk><trkseg>
    <trkpt lat="46.0" lon="7.0"><ele>500</ele><extensions><hr>120</hr></extensions></trkpt>
    <trkpt lat="46.001" lon="7.001"><ele>505</ele></trkpt>
  </trkseg><trkseg>
    <trkpt lat="48.0" lon="9.0"><ele>600</ele></trkpt>
    <trkpt lat="48.001" lon="9.001"><ele>605</ele></trkpt>
  </trkseg></trk>
</gpx>"""


def _tcx_with_leading_whitespace():
    return b"""          <?xml version='1.0' encoding='UTF-8'?>
<TrainingCenterDatabase xmlns='http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2'>
  <Activities><Activity Sport='Biking'><Lap><Track>
    <Trackpoint><Time>2026-09-21T05:30:00Z</Time><Position><LatitudeDegrees>46.0</LatitudeDegrees><LongitudeDegrees>7.0</LongitudeDegrees></Position><AltitudeMeters>500</AltitudeMeters><DistanceMeters>0</DistanceMeters></Trackpoint>
    <Trackpoint><Time>2026-09-21T05:31:00Z</Time><Position><LatitudeDegrees>46.001</LatitudeDegrees><LongitudeDegrees>7.002</LongitudeDegrees></Position><AltitudeMeters>510</AltitudeMeters><DistanceMeters>200</DistanceMeters></Trackpoint>
  </Track></Lap></Activity></Activities>
</TrainingCenterDatabase>"""


class StravaBulkArchiveReaderTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.archive_path = Path(self.temp_dir.name) / "export.zip"

    def tearDown(self):
        self.temp_dir.cleanup()

    def _write_archive(self, rows, members=None):
        members = members or {}
        with zipfile.ZipFile(self.archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("activities.csv", _manifest(rows))
            for name, payload in members.items():
                archive.writestr(name, payload)
        return StravaBulkArchiveReader(str(self.archive_path))

    def test_preflight_and_gpx_import_map_manifest_and_profile(self):
        reader = self._write_archive(
            [_row()],
            {"activities/arbitrary-name.gpx": _gpx()},
        )

        preflight = reader.preflight()
        result = list(reader.iter_activity_results())[0]

        self.assertEqual(preflight.activity_count, 1)
        self.assertEqual(preflight.format_counts, {"gpx": 1})
        self.assertEqual(result.status, "detailed_profile")
        self.assertEqual(result.activity.source_activity_id, "activity-1")
        self.assertEqual(result.activity.distance_m, 1500.5)
        self.assertEqual(result.activity.total_elevation_gain_m, 42.5)
        self.assertEqual(result.activity.geometry_source, "stream")
        self.assertEqual(len(result.activity.geometry_points), 3)
        metrics = result.activity.details_json["stream_metrics"]
        self.assertEqual(metrics["altitude"], [500.0, 510.0, 505.0])
        self.assertEqual(metrics["distance"][0], 0.0)
        self.assertGreater(metrics["distance"][-1], metrics["distance"][1])
        self.assertEqual(result.activity.details_json["ingest_source"], "strava_bulk_export")
        self.assertNotIn(str(self.archive_path), str(result.activity.details_json))

    def test_whitespace_prefixed_tcx_gzip_is_supported(self):
        filename = "activities/not-the-activity-id.tcx.gz"
        reader = self._write_archive(
            [_row(filename=filename)],
            {filename: gzip.compress(_tcx_with_leading_whitespace())},
        )

        result = list(reader.iter_activity_results())[0]

        self.assertEqual(result.status, "detailed_profile")
        self.assertEqual(result.activity.sport_type, "Biking")
        self.assertEqual(result.activity.details_json["stream_metrics"]["distance"], [0.0, 200.0])

    def test_summary_only_row_imports_without_geometry(self):
        reader = self._write_archive([_row(filename="", **{"Activity Type": "Rowing"})])

        preflight = reader.preflight()
        result = list(reader.iter_activity_results())[0]

        self.assertEqual(preflight.summary_only_count, 1)
        self.assertEqual(result.status, "summary_only")
        self.assertEqual(result.activity.activity_type, "Rowing")
        self.assertEqual(result.activity.geometry_points, [])

    def test_gps_without_altitude_does_not_claim_profile(self):
        reader = self._write_archive(
            [_row()],
            {"activities/arbitrary-name.gpx": _gpx(elevation=False)},
        )

        result = list(reader.iter_activity_results())[0]

        self.assertEqual(result.status, "detailed_no_altitude")
        self.assertNotIn("altitude", result.activity.details_json["stream_metrics"])

    def test_original_without_coordinates_is_classified_no_gps(self):
        reader = self._write_archive(
            [_row()],
            {"activities/arbitrary-name.gpx": b"<gpx><trk/></gpx>"},
        )

        result = list(reader.iter_activity_results())[0]

        self.assertEqual(result.status, "no_gps")
        self.assertEqual(result.activity.geometry_points, [])

    def test_unsupported_original_imports_summary_and_is_counted(self):
        filename = "activities/original.json"
        reader = self._write_archive(
            [_row(filename=filename)],
            {filename: b"{}"},
        )

        preflight = reader.preflight()
        result = list(reader.iter_activity_results())[0]

        self.assertEqual(preflight.unsupported_file_count, 1)
        self.assertEqual(result.status, "unsupported")
        self.assertIsNotNone(result.activity)

    def test_gpx_segments_do_not_add_distance_across_segment_gap(self):
        reader = self._write_archive(
            [_row()],
            {"activities/arbitrary-name.gpx": _segmented_gpx()},
        )

        result = list(reader.iter_activity_results())[0]
        metrics = result.activity.details_json["stream_metrics"]

        self.assertEqual(len(result.activity.geometry_points), 4)
        self.assertLess(metrics["distance"][-1], 1000.0)
        self.assertEqual(metrics["heartrate"], [120.0, None, None, None])

    def test_partial_metrics_remain_index_aligned(self):
        reader = self._write_archive(
            [_row()],
            {"activities/arbitrary-name.gpx": _segmented_gpx()},
        )

        metrics = list(reader.iter_activity_results())[0].activity.details_json[
            "stream_metrics"
        ]

        lengths = {len(values) for values in metrics.values()}
        self.assertEqual(lengths, {4})

    def test_missing_member_is_reported_as_conflict_without_database_record(self):
        reader = self._write_archive([_row()])

        preflight = reader.preflight()
        result = list(reader.iter_activity_results())[0]

        self.assertEqual(preflight.missing_file_count, 1)
        self.assertEqual(result.status, "conflicted")
        self.assertEqual(result.diagnostic, "missing_activity_file")
        self.assertIsNone(result.activity)

    def test_duplicate_activity_ids_are_conflicted(self):
        reader = self._write_archive(
            [
                _row(filename="activities/one.gpx"),
                _row(filename="activities/two.gpx"),
            ],
            {"activities/one.gpx": _gpx(), "activities/two.gpx": _gpx()},
        )

        results = list(reader.iter_activity_results())

        self.assertEqual([result.status for result in results], ["conflicted", "conflicted"])
        self.assertTrue(all(result.diagnostic == "duplicate_activity_id" for result in results))

    def test_duplicate_activity_filenames_are_conflicted(self):
        reader = self._write_archive(
            [_row("one"), _row("two")],
            {"activities/arbitrary-name.gpx": _gpx()},
        )

        results = list(reader.iter_activity_results())

        self.assertEqual([result.status for result in results], ["conflicted", "conflicted"])
        self.assertTrue(
            all(result.diagnostic == "duplicate_activity_filename" for result in results)
        )

    def test_unreferenced_sensitive_member_is_not_read(self):
        reader = self._write_archive(
            [_row()],
            {
                "activities/arbitrary-name.gpx": _gpx(),
                "profile.csv": b"private account data",
            },
        )

        with patch.object(
            zipfile.ZipFile,
            "open",
            autospec=True,
            wraps=zipfile.ZipFile.open,
        ) as archive_open:
            reader.preflight()

        opened_names = {
            getattr(call.args[1], "filename", call.args[1])
            for call in archive_open.call_args_list
        }
        self.assertNotIn("profile.csv", opened_names)

    def test_unreferenced_large_media_does_not_consume_import_limits(self):
        reader = self._write_archive(
            [_row()],
            {
                "activities/arbitrary-name.gpx": _gpx(),
                "media/large-video.mp4": b"x" * 8192,
            },
        )
        reader.limits = ArchiveLimits(
            max_member_bytes=2048,
            max_total_bytes=4096,
        )

        preflight = reader.preflight()
        result = list(reader.iter_activity_results())[0]

        self.assertEqual(preflight.activity_count, 1)
        self.assertEqual(result.status, "detailed_profile")

    def test_unsafe_archive_path_is_rejected_before_import(self):
        with zipfile.ZipFile(self.archive_path, "w") as archive:
            archive.writestr("activities.csv", _manifest([_row()]))
            archive.writestr("../outside.gpx", _gpx())

        reader = StravaBulkArchiveReader(str(self.archive_path))
        with self.assertRaisesRegex(StravaBulkArchiveError, "unsafe member path"):
            reader.preflight()

    def test_normalizing_traversal_path_is_still_rejected(self):
        with zipfile.ZipFile(self.archive_path, "w") as archive:
            archive.writestr("activities.csv", _manifest([_row()]))
            archive.writestr("activities/../outside.gpx", _gpx())

        reader = StravaBulkArchiveReader(str(self.archive_path))
        with self.assertRaisesRegex(StravaBulkArchiveError, "unsafe member path"):
            reader.preflight()

    def test_member_count_and_size_limits_are_enforced(self):
        reader = self._write_archive(
            [_row()],
            {"activities/arbitrary-name.gpx": _gpx()},
        )
        reader.limits = ArchiveLimits(max_members=1)
        with self.assertRaisesRegex(StravaBulkArchiveError, "too many members"):
            reader.preflight()

        reader.limits = ArchiveLimits(max_member_bytes=32)
        with self.assertRaisesRegex(StravaBulkArchiveError, "expanded-size limit"):
            reader.preflight()

        reader.limits = ArchiveLimits(max_total_bytes=64)
        with self.assertRaisesRegex(StravaBulkArchiveError, "total expanded-size"):
            reader.preflight()

    def test_manifest_activity_row_limit_is_enforced_while_streaming(self):
        reader = self._write_archive(
            [_row("one", ""), _row("two", "")],
            {},
        )
        reader.limits = ArchiveLimits(max_activity_rows=1)

        with self.assertRaisesRegex(StravaBulkArchiveError, "too many activity rows"):
            reader.preflight()

    def test_manifest_byte_limit_is_enforced_before_decoding(self):
        manifest = _manifest([_row(filename="")])
        reader = self._write_archive([_row(filename="")], {})
        reader.limits = ArchiveLimits(max_manifest_bytes=len(manifest) - 1)

        with self.assertRaisesRegex(StravaBulkArchiveError, "activities.csv exceeds"):
            reader.preflight()

    def test_manifest_row_with_surplus_fields_is_rejected(self):
        manifest = (
            "Activity ID,Activity Date,Activity Name,Activity Type,Filename,Extra\n"
            "1,2026-09-21,Synthetic,Run,,allowed,surplus\n"
        )
        with zipfile.ZipFile(self.archive_path, "w") as archive:
            archive.writestr("activities.csv", manifest)
        reader = StravaBulkArchiveReader(str(self.archive_path))

        with self.assertRaisesRegex(StravaBulkArchiveError, "more values than headers"):
            reader.preflight()

    def test_archive_replacement_after_preflight_is_rejected(self):
        reader = self._write_archive(
            [_row("one", "")],
            {},
        )
        reader.preflight()
        with zipfile.ZipFile(self.archive_path, "w") as archive:
            archive.writestr("activities.csv", _manifest([_row("two", "")]))

        with self.assertRaisesRegex(StravaBulkArchiveError, "changed after validation"):
            list(reader.iter_activity_results())

    def test_activity_member_replacement_after_preflight_is_rejected(self):
        original = _gpx()
        replacement = original.replace(b'lat="46.0"', b'lat="47.0"')
        self.assertEqual(len(original), len(replacement))
        reader = self._write_archive(
            [_row()],
            {"activities/arbitrary-name.gpx": original},
        )
        reader.preflight()
        with zipfile.ZipFile(
            self.archive_path,
            "w",
            compression=zipfile.ZIP_DEFLATED,
        ) as archive:
            archive.writestr("activities.csv", _manifest([_row()]))
            archive.writestr("activities/arbitrary-name.gpx", replacement)

        with self.assertRaisesRegex(StravaBulkArchiveError, "changed after validation"):
            list(reader.iter_activity_results())

    def test_reopened_archive_hashing_reports_byte_progress(self):
        payload = _gpx()
        reader = self._write_archive(
            [_row()],
            {"activities/arbitrary-name.gpx": payload},
        )
        reader.preflight()
        updates = []

        list(
            reader.iter_activity_results(
                integrity_progress=lambda completed, total: updates.append(
                    (completed, total)
                )
            )
        )

        self.assertTrue(updates)
        self.assertEqual(updates[-1], (len(payload), len(payload)))
        self.assertEqual(updates, sorted(updates))

    def test_activity_member_read_honors_cancellation_between_chunks(self):
        large_comment = b"<!--" + b"x" * (3 * 1024 * 1024) + b"-->"
        reader = self._write_archive(
            [_row()],
            {"activities/arbitrary-name.gpx": large_comment + b"<gpx/>"},
        )
        reader.limits = ArchiveLimits(max_compression_ratio=10_000.0)
        reader.preflight()
        calls = 0

        def cancelled():
            nonlocal calls
            calls += 1
            return calls >= 4

        with self.assertRaises(StravaBulkArchiveCancelled):
            list(reader.iter_activity_results(cancelled=cancelled))

    def test_duplicate_normalized_zip_paths_are_rejected(self):
        with zipfile.ZipFile(self.archive_path, "w") as archive:
            archive.writestr("activities.csv", _manifest([_row(filename="")]))
            archive.writestr("activities//same.gpx", _gpx())
            archive.writestr("activities/same.gpx", _gpx())

        reader = StravaBulkArchiveReader(str(self.archive_path))
        with self.assertRaisesRegex(StravaBulkArchiveError, "duplicate normalized"):
            reader.preflight()

    def test_unsupported_zip_compression_is_rejected(self):
        with zipfile.ZipFile(self.archive_path, "w", compression=zipfile.ZIP_BZIP2) as archive:
            archive.writestr("activities.csv", _manifest([_row(filename="")]))

        reader = StravaBulkArchiveReader(str(self.archive_path))
        with self.assertRaisesRegex(StravaBulkArchiveError, "compression method"):
            reader.preflight()

    def test_dangerous_zip_compression_ratio_is_rejected(self):
        with zipfile.ZipFile(self.archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            filename = "activities/large.gpx"
            archive.writestr("activities.csv", _manifest([_row(filename=filename)]))
            archive.writestr(filename, b"0" * (2 * 1024 * 1024))

        reader = StravaBulkArchiveReader(str(self.archive_path))
        with self.assertRaisesRegex(StravaBulkArchiveError, "compression ratio"):
            reader.preflight()

    def test_encrypted_flag_is_rejected_before_member_read(self):
        with zipfile.ZipFile(self.archive_path, "w", compression=zipfile.ZIP_STORED) as archive:
            archive.writestr("activities.csv", _manifest([_row(filename="")]))
        payload = bytearray(self.archive_path.read_bytes())
        central_offset = payload.index(b"PK\x01\x02")
        local_flags = int.from_bytes(payload[6:8], "little") | 0x1
        central_flags = int.from_bytes(payload[central_offset + 8:central_offset + 10], "little") | 0x1
        payload[6:8] = local_flags.to_bytes(2, "little")
        payload[central_offset + 8:central_offset + 10] = central_flags.to_bytes(2, "little")
        self.archive_path.write_bytes(payload)

        reader = StravaBulkArchiveReader(str(self.archive_path))
        with self.assertRaisesRegex(StravaBulkArchiveError, "Encrypted"):
            reader.preflight()

    def test_corrupt_referenced_member_is_isolated_and_summary_is_imported(self):
        marker = b"UNIQUE-SYNTHETIC-PAYLOAD"
        with zipfile.ZipFile(self.archive_path, "w", compression=zipfile.ZIP_STORED) as archive:
            archive.writestr(
                "activities.csv",
                _manifest(
                    [
                        _row("corrupt", "activities/corrupt.gpx"),
                        _row("valid", "activities/valid.gpx"),
                    ]
                ),
            )
            archive.writestr("activities/corrupt.gpx", marker)
            archive.writestr("activities/valid.gpx", _gpx())
        payload = bytearray(self.archive_path.read_bytes())
        offset = payload.index(marker)
        payload[offset] ^= 0x01
        self.archive_path.write_bytes(payload)

        reader = StravaBulkArchiveReader(str(self.archive_path))
        preflight = reader.preflight()
        results = list(reader.iter_activity_results())

        self.assertEqual(preflight.activity_count, 2)
        self.assertEqual([result.activity_id for result in results], ["corrupt", "valid"])
        self.assertEqual([result.status for result in results], ["failed", "detailed_profile"])
        self.assertEqual(results[0].diagnostic, "invalid_activity_file")
        self.assertIsNotNone(results[0].activity)
        self.assertEqual(results[0].activity.name, "Morning activity")

    def test_xml_document_type_is_rejected_per_activity(self):
        payload = b'<!DOCTYPE gpx [<!ENTITY x "unsafe">]><gpx></gpx>'
        reader = self._write_archive(
            [_row()],
            {"activities/arbitrary-name.gpx": payload},
        )

        result = list(reader.iter_activity_results())[0]

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.diagnostic, "invalid_activity_file")
        self.assertIsNotNone(result.activity)

    def test_xml_document_type_after_long_comment_is_rejected_per_activity(self):
        payload = (
            b"<!--" + b"x" * 5000 + b"-->"
            b'<!DOCTYPE gpx [<!ENTITY x "unsafe">]><gpx>&x;</gpx>'
        )
        reader = self._write_archive(
            [_row()],
            {"activities/arbitrary-name.gpx": payload},
        )

        result = list(reader.iter_activity_results())[0]

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.diagnostic, "invalid_activity_file")

    def test_utf16_xml_document_type_is_rejected_per_activity(self):
        payload = (
            '<?xml version="1.0" encoding="UTF-16"?>'
            '<!DOCTYPE gpx [<!ENTITY x "unsafe">]><gpx>&x;</gpx>'
        ).encode("utf-16")
        reader = self._write_archive(
            [_row()],
            {"activities/arbitrary-name.gpx": payload},
        )

        result = list(reader.iter_activity_results())[0]

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.diagnostic, "invalid_activity_file")

    def test_xml_parser_size_limit_isolated_to_oversized_activity(self):
        payload = _gpx()
        reader = self._write_archive(
            [_row()],
            {"activities/arbitrary-name.gpx": payload},
        )
        reader.limits = ArchiveLimits(max_xml_bytes=len(payload) - 1)

        result = list(reader.iter_activity_results())[0]

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.diagnostic, "invalid_activity_file")

    def test_compressed_xml_parser_size_limit_isolated_to_oversized_activity(self):
        payload = _gpx()
        filename = "activities/arbitrary-name.gpx.gz"
        reader = self._write_archive(
            [_row(filename=filename)],
            {filename: gzip.compress(payload)},
        )
        reader.limits = ArchiveLimits(max_xml_bytes=len(payload) - 1)

        result = list(reader.iter_activity_results())[0]

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.diagnostic, "invalid_activity_file")

    def test_fit_parser_size_limit_isolated_to_oversized_activity(self):
        filename = "activities/arbitrary-name.fit"
        payload = b"not-a-fit-file"
        reader = self._write_archive(
            [_row(filename=filename)],
            {filename: payload},
        )
        reader.limits = ArchiveLimits(max_fit_bytes=len(payload) - 1)

        result = list(reader.iter_activity_results())[0]

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.diagnostic, "invalid_activity_file")

    def test_tcx_track_boundaries_do_not_add_inter_track_distance(self):
        payload = b"""<?xml version='1.0' encoding='UTF-8'?>
<TrainingCenterDatabase>
  <Activities><Activity Sport='Biking'><Lap>
    <Track>
      <Trackpoint><Position><LatitudeDegrees>46.0</LatitudeDegrees><LongitudeDegrees>7.0</LongitudeDegrees></Position></Trackpoint>
      <Trackpoint><Position><LatitudeDegrees>46.001</LatitudeDegrees><LongitudeDegrees>7.001</LongitudeDegrees></Position></Trackpoint>
    </Track>
    <Track>
      <Trackpoint><Position><LatitudeDegrees>48.0</LatitudeDegrees><LongitudeDegrees>9.0</LongitudeDegrees></Position></Trackpoint>
      <Trackpoint><Position><LatitudeDegrees>48.001</LatitudeDegrees><LongitudeDegrees>9.001</LongitudeDegrees></Position></Trackpoint>
    </Track>
  </Lap></Activity></Activities>
</TrainingCenterDatabase>"""
        filename = "activities/segmented.tcx"
        reader = self._write_archive(
            [_row(filename=filename)],
            {filename: payload},
        )

        result = list(reader.iter_activity_results())[0]

        distances = result.activity.details_json["stream_metrics"]["distance"]
        self.assertLess(distances[-1], 1000.0)
        self.assertEqual(len(distances), 4)

    def test_nested_gzip_limit_is_enforced_per_activity(self):
        filename = "activities/large.gpx.gz"
        reader = self._write_archive(
            [_row(filename=filename)],
            {filename: gzip.compress(b"x" * 4096)},
        )
        reader.limits = ArchiveLimits(max_nested_bytes=1024)

        with self.assertRaisesRegex(
            StravaBulkArchiveError,
            "nested activity file exceeds",
        ):
            reader.preflight()

    def test_nested_gzip_total_limit_is_enforced_across_members(self):
        first = "activities/first.gpx.gz"
        second = "activities/second.gpx.gz"
        reader = self._write_archive(
            [_row("one", first), _row("two", second)],
            {
                first: gzip.compress(b"x" * 800),
                second: gzip.compress(b"y" * 800),
            },
        )
        reader.limits = ArchiveLimits(
            max_nested_bytes=1024,
            max_total_bytes=1200,
        )

        with self.assertRaisesRegex(
            StravaBulkArchiveError,
            "Nested activity files exceed",
        ):
            reader.preflight()

    def test_preflight_cancellation_interrupts_member_streaming(self):
        filename = "activities/large.gpx"
        with zipfile.ZipFile(
            self.archive_path,
            "w",
            compression=zipfile.ZIP_STORED,
        ) as archive:
            archive.writestr("activities.csv", _manifest([_row(filename=filename)]))
            archive.writestr(filename, b"x" * (2 * 1024 * 1024))
        reader = StravaBulkArchiveReader(str(self.archive_path))
        checks = 0

        def cancelled():
            nonlocal checks
            checks += 1
            return checks >= 5

        with self.assertRaises(StravaBulkArchiveCancelled):
            reader.preflight(cancelled=cancelled)

    def test_progress_and_cancellation_stop_between_activity_members(self):
        reader = self._write_archive(
            [_row("one", "activities/one.gpx"), _row("two", "activities/two.gpx")],
            {"activities/one.gpx": _gpx(), "activities/two.gpx": _gpx()},
        )
        progress = []

        results = list(
            reader.iter_activity_results(
                cancelled=lambda: bool(progress),
                progress=lambda completed, total: progress.append((completed, total)),
            )
        )

        self.assertEqual(len(results), 1)
        self.assertEqual(progress, [(1, 2)])


class FitAdapterTests(unittest.TestCase):
    def test_fit_records_are_normalized_and_aligned(self):
        message_type = type("FakeFitDataMessage", (), {})
        start = datetime(2026, 9, 21, 5, 30, tzinfo=UTC)

        def message(name, **values):
            value = message_type()
            value.name = name
            value.fields = [SimpleNamespace(name=key, value=item) for key, item in values.items()]
            return value

        frames = [
            message("session", start_time=start, sport="running", sub_sport="trail"),
            message(
                "record",
                position_lat=int(46.0 * (2**31) / 180.0),
                position_long=int(7.0 * (2**31) / 180.0),
                timestamp=start,
                distance=0.0,
                enhanced_altitude=500.0,
                heart_rate=140,
            ),
            message(
                "record",
                position_lat=int(46.001 * (2**31) / 180.0),
                position_long=int(7.002 * (2**31) / 180.0),
                timestamp=start + timedelta(seconds=60),
                enhanced_altitude=510.0,
            ),
        ]

        class FakeReader:
            def __init__(self, *_args, **_kwargs):
                pass

            def __enter__(self):
                return iter(frames)

            def __exit__(self, *_args):
                return False

        fake_fitdecode = SimpleNamespace(
            FitReader=FakeReader,
            FitDataMessage=message_type,
            CrcCheck=SimpleNamespace(WARN="warn"),
            FitError=Exception,
        )
        filename = "activities/random.fit"
        with tempfile.TemporaryDirectory() as temp_dir:
            archive_path = Path(temp_dir) / "export.zip"
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("activities.csv", _manifest([_row(filename=filename)]))
                archive.writestr(filename, b"synthetic-fit")
            reader = StravaBulkArchiveReader(str(archive_path))
            with patch(
                "qfit.providers.infrastructure.strava_bulk_archive.load_fitdecode",
                return_value=fake_fitdecode,
            ):
                result = list(reader.iter_activity_results())[0]

        self.assertEqual(result.status, "detailed_profile")
        self.assertEqual(result.activity.sport_type, "trail")
        self.assertAlmostEqual(result.activity.geometry_points[0][0], 46.0, places=5)
        metrics = result.activity.details_json["stream_metrics"]
        self.assertEqual(metrics["time"], [0, 60])
        self.assertEqual(metrics["altitude"], [500.0, 510.0])
        self.assertEqual(metrics["heartrate"], [140.0, None])
        self.assertEqual(len(metrics["distance"]), 2)


if __name__ == "__main__":
    unittest.main()
