import unittest
from types import SimpleNamespace

from tests import _path  # noqa: F401
from qfit.provider import ProviderError
from qfit.strava_provider import StravaProvider
from qfit.sync_controller import SyncController


class BuildStravaProviderTests(unittest.TestCase):
    def test_build_strava_provider_returns_strava_provider(self):
        ctrl = SyncController()
        provider = ctrl.build_strava_provider("id", "secret", "token")
        self.assertIsInstance(provider, StravaProvider)

    def test_build_strava_provider_raises_without_credentials(self):
        ctrl = SyncController()
        with self.assertRaises(ProviderError):
            ctrl.build_strava_provider("", "", "token")

    def test_build_strava_provider_raises_without_refresh_token(self):
        ctrl = SyncController()
        with self.assertRaises(ProviderError):
            ctrl.build_strava_provider("id", "secret", "")

    def test_build_strava_provider_allows_missing_refresh_token_when_not_required(self):
        ctrl = SyncController()
        provider = ctrl.build_strava_provider("id", "secret", "", require_refresh_token=False)
        self.assertIsInstance(provider, StravaProvider)


class BuildSyncMetadataTests(unittest.TestCase):
    def test_metadata_fields(self):
        ctrl = SyncController()
        activity = SimpleNamespace(geometry_source="stream")
        provider = SimpleNamespace(
            source_name="strava",
            last_stream_enrichment_stats={"cached": 1},
            last_rate_limit={"short_remaining": 10},
        )
        meta = ctrl.build_sync_metadata([activity], provider)
        self.assertEqual(meta["provider"], "strava")
        self.assertEqual(meta["fetched_count"], 1)
        self.assertEqual(meta["detailed_count"], 1)
        self.assertTrue(meta["is_full_sync"])
        self.assertIn("today_str", meta)

    def test_detailed_count_excludes_non_stream(self):
        ctrl = SyncController()
        activities = [
            SimpleNamespace(geometry_source="stream"),
            SimpleNamespace(geometry_source="polyline"),
        ]
        provider = SimpleNamespace(
            source_name="strava",
            last_stream_enrichment_stats=None,
            last_rate_limit=None,
        )
        meta = ctrl.build_sync_metadata(activities, provider)
        self.assertEqual(meta["detailed_count"], 1)
        self.assertEqual(meta["fetched_count"], 2)

    def test_metadata_uses_provider_source_name(self):
        ctrl = SyncController()
        provider = SimpleNamespace(
            source_name="gpx",
            last_stream_enrichment_stats=None,
            last_rate_limit=None,
        )
        meta = ctrl.build_sync_metadata([], provider)
        self.assertEqual(meta["provider"], "gpx")


class FetchStatusTextTests(unittest.TestCase):
    def test_basic_status_text(self):
        ctrl = SyncController()
        provider = SimpleNamespace(
            source_name="strava",
            last_stream_enrichment_stats={"cached": 2, "downloaded": 3, "skipped_rate_limit": 0},
            last_rate_limit=None,
        )
        text = ctrl.fetch_status_text(provider, 10, 5)
        self.assertIn("10 activities", text)
        self.assertIn("detailed tracks: 5", text)
        self.assertIn("cached streams: 2", text)

    def test_status_text_includes_source_name(self):
        ctrl = SyncController()
        provider = SimpleNamespace(
            source_name="strava",
            last_stream_enrichment_stats={},
            last_rate_limit=None,
        )
        text = ctrl.fetch_status_text(provider, 3, 0)
        self.assertIn("strava", text)

    def test_rate_limit_note_included(self):
        ctrl = SyncController()
        provider = SimpleNamespace(
            source_name="strava",
            last_stream_enrichment_stats={},
            last_rate_limit={"short_remaining": 50, "long_remaining": 900},
        )
        text = ctrl.fetch_status_text(provider, 1, 0)
        self.assertIn("Remaining rate limit", text)
        self.assertIn("short=50", text)
        self.assertIn("long=900", text)

    def test_no_rate_limit(self):
        ctrl = SyncController()
        provider = SimpleNamespace(
            source_name="strava",
            last_stream_enrichment_stats=None,
            last_rate_limit=None,
        )
        text = ctrl.fetch_status_text(provider, 0, 0)
        self.assertNotIn("rate limit", text.lower().replace("rate-limit", ""))
