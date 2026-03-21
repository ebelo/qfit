from datetime import UTC, datetime
import unittest

from tests import _path  # noqa: F401
from QFIT.time_utils import add_seconds_iso, format_iso_datetime, parse_iso_datetime


class TimeUtilsTests(unittest.TestCase):
    def test_parse_iso_datetime_handles_z_suffix(self):
        parsed = parse_iso_datetime("2026-03-20T12:30:00Z")
        self.assertEqual(parsed, datetime(2026, 3, 20, 12, 30, 0, tzinfo=UTC))

    def test_parse_iso_datetime_accepts_datetime_input(self):
        value = datetime(2026, 3, 20, 12, 30, 0, tzinfo=UTC)
        self.assertIs(parse_iso_datetime(value), value)

    def test_parse_iso_datetime_rejects_blank_or_invalid_values(self):
        self.assertIsNone(parse_iso_datetime(""))
        self.assertIsNone(parse_iso_datetime("not-a-date"))
        self.assertIsNone(parse_iso_datetime(None))

    def test_format_iso_datetime_rewrites_utc_offset_as_z(self):
        value = datetime(2026, 3, 20, 12, 30, 0, tzinfo=UTC)
        self.assertEqual(format_iso_datetime(value), "2026-03-20T12:30:00Z")

    def test_add_seconds_iso_returns_shifted_timestamp(self):
        self.assertEqual(
            add_seconds_iso("2026-03-20T12:30:00Z", 90),
            "2026-03-20T12:31:30Z",
        )

    def test_add_seconds_iso_rejects_invalid_inputs(self):
        self.assertIsNone(add_seconds_iso(None, 10))
        self.assertIsNone(add_seconds_iso("2026-03-20T12:30:00Z", None))
        self.assertIsNone(add_seconds_iso("not-a-date", 10))
        self.assertIsNone(add_seconds_iso("2026-03-20T12:30:00Z", "abc"))


if __name__ == "__main__":
    unittest.main()
