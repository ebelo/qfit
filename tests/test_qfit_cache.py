import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests import _path  # noqa: F401
from QFIT.qfit_cache import QfitCache


class QfitCacheTests(unittest.TestCase):
    def test_save_and_load_stream_bundle_round_trip(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = QfitCache(base_path=tmpdir)
            saved_path = cache.save_stream_bundle("strava", "123", {"latlng": [[1.0, 2.0]], "time": [0, 1]})

            self.assertTrue(Path(saved_path).exists())
            self.assertEqual(
                cache.load_stream_bundle("strava", "123"),
                {"latlng": [[1.0, 2.0]], "time": [0, 1]},
            )

    def test_load_stream_bundle_respects_max_age(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = QfitCache(base_path=tmpdir)
            cache.save_stream_bundle("strava", "123", {"latlng": [[1.0, 2.0]]})

            with patch("QFIT.qfit_cache.time.time", return_value=10_000_000_000):
                self.assertIsNone(cache.load_stream_bundle("strava", "123", max_age_seconds=1))

    def test_load_stream_bundle_supports_legacy_point_only_cache(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = QfitCache(base_path=tmpdir)
            cache_file = Path(tmpdir) / "strava" / "streams" / "123.json"
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            cache_file.write_text(json.dumps({"points": [[46.5, 6.6], [46.6, 6.7]]}), encoding="utf-8")

            self.assertEqual(
                cache.load_stream_bundle("strava", "123"),
                {"latlng": [[46.5, 6.6], [46.6, 6.7]]},
            )
            self.assertEqual(
                cache.load_stream_points("strava", "123"),
                [(46.5, 6.6), (46.6, 6.7)],
            )

    def test_save_stream_points_wraps_latlng_stream(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = QfitCache(base_path=tmpdir)
            cache.save_stream_points("strava", "123", [(46.5, 6.6), (46.6, 6.7)])

            self.assertEqual(
                cache.load_stream_bundle("strava", "123"),
                {"latlng": [[46.5, 6.6], [46.6, 6.7]]},
            )


if __name__ == "__main__":
    unittest.main()
