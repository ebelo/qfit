import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from tests import _path  # noqa: F401
from qfit.provider import ProviderError
from qfit.strava_provider import StravaProvider
from qfit.sync_controller import (
    BuildFetchTaskRequest,
    BuildStravaProviderRequest,
    ExchangeStravaCodeRequest,
    StravaAuthorizeRequest,
    SyncController,
)


class BuildStravaProviderTests(unittest.TestCase):
    def test_build_provider_request_returns_structured_request(self):
        ctrl = SyncController()
        request = ctrl.build_provider_request("id", "secret", "token", cache="cache")

        self.assertIsInstance(request, BuildStravaProviderRequest)
        self.assertEqual(request.provider_name, "strava")
        self.assertEqual(request.client_id, "id")
        self.assertEqual(request.client_secret, "secret")
        self.assertEqual(request.refresh_token, "token")

    def test_build_strava_provider_request_preserves_positional_argument_order(self):
        request = BuildStravaProviderRequest(
            "id",
            "secret",
            "token",
            "cache-object",
            False,
        )

        self.assertEqual(request.client_id, "id")
        self.assertEqual(request.client_secret, "secret")
        self.assertEqual(request.refresh_token, "token")
        self.assertEqual(request.cache, "cache-object")
        self.assertFalse(request.require_refresh_token)
        self.assertEqual(request.provider_name, "strava")

    def test_build_strava_provider_returns_strava_provider(self):
        ctrl = SyncController()
        provider = ctrl.build_strava_provider("id", "secret", "token")
        self.assertIsInstance(provider, StravaProvider)

    def test_build_strava_provider_accepts_request_object(self):
        ctrl = SyncController()
        request = ctrl.build_provider_request("id", "secret", "token")

        provider = ctrl.build_strava_provider(request)

        self.assertIsInstance(provider, StravaProvider)

    def test_build_strava_provider_delegates_to_provider_registry(self):
        provider_registry = MagicMock()
        provider_registry.build_provider.return_value = "provider"
        ctrl = SyncController(provider_registry=provider_registry)
        request = ctrl.build_provider_request("id", "secret", "token")

        provider = ctrl.build_strava_provider(request)

        provider_registry.build_provider.assert_called_once_with(request)
        self.assertEqual(provider, "provider")

    def test_build_strava_provider_raises_without_credentials(self):
        ctrl = SyncController()
        with self.assertRaisesRegex(
            ProviderError,
            "Configuration and enter your Strava client ID and client secret first",
        ):
            ctrl.build_strava_provider("", "", "token")

    def test_build_strava_provider_raises_without_refresh_token(self):
        ctrl = SyncController()
        with self.assertRaisesRegex(
            ProviderError,
            "Configuration and enter a Strava refresh token first",
        ):
            ctrl.build_strava_provider("id", "secret", "")

    def test_build_strava_provider_allows_missing_refresh_token_when_not_required(self):
        ctrl = SyncController()
        provider = ctrl.build_strava_provider("id", "secret", "", require_refresh_token=False)
        self.assertIsInstance(provider, StravaProvider)


class BuildFetchTaskTests(unittest.TestCase):
    def test_build_fetch_task_request_returns_structured_request(self):
        ctrl = SyncController()

        request = ctrl.build_fetch_task_request(
            client_id="id",
            client_secret="secret",
            refresh_token="token",
            cache="cache",
            per_page=123,
            max_pages=4,
            use_detailed_streams=True,
            max_detailed_activities=9,
            detailed_route_strategy="Recent fetch only",
            on_finished="callback",
        )

        self.assertIsInstance(request, BuildFetchTaskRequest)
        self.assertEqual(request.client_id, "id")
        self.assertEqual(request.per_page, 123)
        self.assertTrue(request.use_detailed_streams)
        self.assertEqual(request.detailed_route_strategy, "Recent fetch only")

    def test_build_fetch_task_request_preserves_legacy_positional_callback_slot(self):
        ctrl = SyncController()
        callback = object()

        request = ctrl.build_fetch_task_request(
            "id",
            "secret",
            "token",
            "cache",
            123,
            4,
            True,
            9,
            callback,
        )

        self.assertIs(request.on_finished, callback)
        self.assertEqual(request.detailed_route_strategy, "Missing routes only")

    def test_build_fetch_task_validates_provider_and_constructs_fetch_task(self):
        ctrl = SyncController()
        provider = MagicMock(name="provider")

        with (
            patch.object(ctrl, "build_strava_provider", return_value=provider) as build_provider,
            patch("qfit.activities.application.sync_controller.FetchTask") as fetch_task_class,
        ):
            task = ctrl.build_fetch_task(
                client_id="id",
                client_secret="secret",
                refresh_token="token",
                cache="cache",
                per_page=50,
                max_pages=2,
                use_detailed_streams=True,
                max_detailed_activities=7,
                detailed_route_strategy="Recent fetch only",
                on_finished="callback",
            )

        build_provider.assert_called_once()
        fetch_task_class.assert_called_once_with(
            provider=provider,
            per_page=50,
            max_pages=2,
            before=None,
            after=None,
            use_detailed_streams=True,
            max_detailed_activities=7,
            detailed_route_strategy="Recent fetch only",
            on_finished="callback",
        )
        self.assertIs(task, fetch_task_class.return_value)

    def test_build_fetch_task_supports_legacy_kwargs_without_strategy(self):
        ctrl = SyncController()
        provider = MagicMock(name="provider")

        with (
            patch.object(ctrl, "build_strava_provider", return_value=provider),
            patch("qfit.activities.application.sync_controller.FetchTask") as fetch_task_class,
        ):
            ctrl.build_fetch_task(
                client_id="id",
                client_secret="secret",
                refresh_token="token",
                cache="cache",
                per_page=50,
                max_pages=2,
                use_detailed_streams=True,
                max_detailed_activities=7,
                on_finished="callback",
            )

        fetch_task_class.assert_called_once_with(
            provider=provider,
            per_page=50,
            max_pages=2,
            before=None,
            after=None,
            use_detailed_streams=True,
            max_detailed_activities=7,
            detailed_route_strategy="Missing routes only",
            on_finished="callback",
        )


class StravaAuthorizationWorkflowTests(unittest.TestCase):
    def test_build_authorize_request_returns_dataclass(self):
        ctrl = SyncController()

        request = ctrl.build_authorize_request(
            client_id="id",
            client_secret="secret",
            refresh_token="token",
            cache="cache",
            redirect_uri="https://example.com/callback",
        )

        self.assertIsInstance(request, StravaAuthorizeRequest)
        self.assertEqual(request.redirect_uri, "https://example.com/callback")

    def test_build_authorize_url_uses_validated_provider(self):
        ctrl = SyncController()
        provider = MagicMock(name="provider")
        provider.build_authorize_url.return_value = "https://strava.test/auth"

        with patch.object(ctrl, "build_strava_provider", return_value=provider):
            url = ctrl.build_authorize_url(
                client_id="id",
                client_secret="secret",
                refresh_token="",
                cache="cache",
                redirect_uri="https://example.com/callback",
            )

        provider.build_authorize_url.assert_called_once_with(
            redirect_uri="https://example.com/callback"
        )
        self.assertEqual(url, "https://strava.test/auth")

    def test_build_exchange_code_request_returns_dataclass(self):
        ctrl = SyncController()

        request = ctrl.build_exchange_code_request(
            client_id="id",
            client_secret="secret",
            refresh_token="",
            cache="cache",
            authorization_code="abc123",
            redirect_uri="https://example.com/callback",
        )

        self.assertIsInstance(request, ExchangeStravaCodeRequest)
        self.assertEqual(request.authorization_code, "abc123")

    def test_exchange_code_for_tokens_returns_payload(self):
        ctrl = SyncController()
        provider = MagicMock(name="provider")
        payload = {"refresh_token": "rtok", "athlete": {"firstname": "Ada"}}
        provider.exchange_code_for_tokens.return_value = payload

        with patch.object(ctrl, "build_strava_provider", return_value=provider):
            result = ctrl.exchange_code_for_tokens(
                client_id="id",
                client_secret="secret",
                refresh_token="",
                cache="cache",
                authorization_code="abc123",
                redirect_uri="https://example.com/callback",
            )

        provider.exchange_code_for_tokens.assert_called_once_with(
            authorization_code="abc123",
            redirect_uri="https://example.com/callback",
        )
        self.assertEqual(result, payload)

    def test_exchange_code_for_tokens_requires_refresh_token_in_payload(self):
        ctrl = SyncController()
        provider = MagicMock(name="provider")
        provider.exchange_code_for_tokens.return_value = {"athlete": {"firstname": "Ada"}}

        with (
            patch.object(ctrl, "build_strava_provider", return_value=provider),
            self.assertRaisesRegex(ProviderError, "no refresh token"),
        ):
            ctrl.exchange_code_for_tokens(
                client_id="id",
                client_secret="secret",
                refresh_token="",
                cache="cache",
                authorization_code="abc123",
                redirect_uri="https://example.com/callback",
            )


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
            last_stream_enrichment_stats={
                "already_detailed": 6,
                "cached": 2,
                "downloaded": 3,
                "skipped_rate_limit": 0,
                "missing_before": 4,
                "remaining_missing": 1,
                "empty": 1,
                "errors": 0,
            },
            last_rate_limit=None,
            last_fetch_notice=None,
        )
        text = ctrl.fetch_status_text(provider, 10, 5)
        self.assertIn("10 activities", text)
        self.assertIn("detailed tracks: 5", text)
        self.assertIn("cached streams: 2", text)
        self.assertIn("already detailed before run: 6", text)
        self.assertIn("missing detailed routes before run: 4", text)
        self.assertIn("remaining missing: 1", text)
        self.assertIn("empty detailed-route responses: 1", text)
        self.assertIn("errors: 0", text)

    def test_status_text_includes_source_name(self):
        ctrl = SyncController()
        provider = SimpleNamespace(
            source_name="strava",
            last_stream_enrichment_stats={},
            last_rate_limit=None,
            last_fetch_notice=None,
        )
        text = ctrl.fetch_status_text(provider, 3, 0)
        self.assertIn("strava", text)

    def test_rate_limit_note_included(self):
        ctrl = SyncController()
        provider = SimpleNamespace(
            source_name="strava",
            last_stream_enrichment_stats={},
            last_rate_limit={"short_remaining": 50, "long_remaining": 900},
            last_fetch_notice=None,
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
            last_fetch_notice=None,
        )
        text = ctrl.fetch_status_text(provider, 0, 0)
        self.assertNotIn("rate limit", text.lower().replace("rate-limit", ""))

    def test_fetch_notice_included(self):
        ctrl = SyncController()
        provider = SimpleNamespace(
            source_name="strava",
            last_stream_enrichment_stats={},
            last_rate_limit={"short_remaining": 3, "long_remaining": 80},
            last_fetch_notice="Stopped early to avoid hitting the Strava rate limit.",
        )
        text = ctrl.fetch_status_text(provider, 40, 0)
        self.assertIn("Stopped early to avoid hitting the Strava rate limit", text)
