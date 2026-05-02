"""Tests for StravaProvider and the ActivityProvider protocol."""

import unittest
from unittest.mock import MagicMock

from tests import _path  # noqa: F401
from qfit.providers.domain import ActivityProvider, ProviderError
from qfit.providers.infrastructure import StravaClient, StravaProvider


class TestStravaProviderProtocol(unittest.TestCase):
    """StravaProvider must satisfy the ActivityProvider protocol."""

    def test_strava_provider_satisfies_activity_provider(self):
        provider = StravaProvider(client_id="id", client_secret="secret", refresh_token="token")
        self.assertIsInstance(provider, ActivityProvider)

    def test_source_name_is_strava(self):
        provider = StravaProvider()
        self.assertEqual(provider.source_name, "strava")

    def test_default_redirect_uri_matches_strava_client(self):
        self.assertEqual(StravaProvider.DEFAULT_REDIRECT_URI, StravaClient.DEFAULT_REDIRECT_URI)


class TestStravaProviderFetchActivities(unittest.TestCase):
    """fetch_activities delegates to StravaClient and translates errors."""

    def _make_provider(self):
        provider = StravaProvider(client_id="id", client_secret="secret", refresh_token="token")
        provider._client = MagicMock()
        return provider

    def test_fetch_activities_delegates_to_client(self):
        provider = self._make_provider()
        provider._client.fetch_activities.return_value = []
        result = provider.fetch_activities(per_page=50, max_pages=2)
        provider._client.fetch_activities.assert_called_once_with(
            per_page=50,
            max_pages=2,
            before=None,
            after=None,
            use_detailed_streams=False,
            max_detailed_activities=None,
            detailed_route_strategy="Missing routes only",
        )
        self.assertEqual(result, [])

    def test_fetch_activities_translates_strava_client_error(self):
        from qfit.providers.infrastructure.strava_client import StravaClientError
        provider = self._make_provider()
        provider._client.fetch_activities.side_effect = StravaClientError("API error")
        with self.assertRaises(ProviderError) as ctx:
            provider.fetch_activities()
        self.assertIn("API error", str(ctx.exception))

    def test_fetch_activities_error_preserves_cause(self):
        from qfit.providers.infrastructure.strava_client import StravaClientError
        provider = self._make_provider()
        original = StravaClientError("original")
        provider._client.fetch_activities.side_effect = original
        try:
            provider.fetch_activities()
        except ProviderError as exc:
            self.assertIs(exc.__cause__, original)


class TestStravaProviderFetchRoutes(unittest.TestCase):
    """Route fetch helpers delegate to StravaClient and translate errors."""

    def _make_provider(self):
        provider = StravaProvider(client_id="id", client_secret="secret", refresh_token="token")
        provider._client = MagicMock()
        return provider

    def test_fetch_routes_delegates_to_client(self):
        provider = self._make_provider()
        provider._client.fetch_routes.return_value = []

        result = provider.fetch_routes(athlete_id=123, per_page=50, max_pages=2)

        provider._client.fetch_routes.assert_called_once_with(
            athlete_id=123,
            per_page=50,
            max_pages=2,
        )
        self.assertEqual(result, [])

    def test_fetch_routes_translates_strava_client_error(self):
        from qfit.providers.infrastructure.strava_client import StravaClientError

        provider = self._make_provider()
        provider._client.fetch_routes.side_effect = StravaClientError("route API error")

        with self.assertRaises(ProviderError) as ctx:
            provider.fetch_routes()

        self.assertIn("route API error", str(ctx.exception))

    def test_fetch_route_detail_delegates_to_client(self):
        provider = self._make_provider()
        provider._client.fetch_route_detail.return_value = object()

        result = provider.fetch_route_detail(42, use_gpx_geometry=True)

        provider._client.fetch_route_detail.assert_called_once_with(42, use_gpx_geometry=True)
        self.assertIs(result, provider._client.fetch_route_detail.return_value)

    def test_fetch_route_detail_translates_strava_client_error(self):
        from qfit.providers.infrastructure.strava_client import StravaClientError

        provider = self._make_provider()
        provider._client.fetch_route_detail.side_effect = StravaClientError("bad route")

        with self.assertRaises(ProviderError) as ctx:
            provider.fetch_route_detail(42)

        self.assertIn("bad route", str(ctx.exception))


class TestStravaProviderProperties(unittest.TestCase):
    """last_stream_enrichment_stats and last_rate_limit proxy to the client."""

    def _make_provider(self):
        provider = StravaProvider()
        provider._client = MagicMock()
        return provider

    def test_last_stream_enrichment_stats_proxied(self):
        provider = self._make_provider()
        provider._client.last_stream_enrichment_stats = {"cached": 3}
        self.assertEqual(provider.last_stream_enrichment_stats, {"cached": 3})

    def test_last_rate_limit_proxied(self):
        provider = self._make_provider()
        provider._client.last_rate_limit = {"short_remaining": 100}
        self.assertEqual(provider.last_rate_limit, {"short_remaining": 100})

    def test_last_fetch_notice_proxied(self):
        provider = self._make_provider()
        provider._client.last_fetch_notice = "Stopped early"
        self.assertEqual(provider.last_fetch_notice, "Stopped early")


class TestStravaProviderCredentials(unittest.TestCase):
    def test_has_client_credentials_delegates(self):
        provider = StravaProvider(client_id="id", client_secret="secret")
        self.assertTrue(provider.has_client_credentials())

    def test_has_client_credentials_false_when_empty(self):
        provider = StravaProvider()
        self.assertFalse(provider.has_client_credentials())

    def test_has_refresh_token_true(self):
        provider = StravaProvider(refresh_token="tok")
        self.assertTrue(provider.has_refresh_token())

    def test_has_refresh_token_false_when_empty(self):
        provider = StravaProvider()
        self.assertFalse(provider.has_refresh_token())


class TestStravaProviderAuthMethods(unittest.TestCase):
    """build_authorize_url and exchange_code_for_tokens translate errors."""

    def _make_provider(self):
        provider = StravaProvider(client_id="id", client_secret="secret")
        provider._client = MagicMock()
        return provider

    def test_build_authorize_url_delegates(self):
        provider = self._make_provider()
        provider._client.build_authorize_url.return_value = "https://example.com/auth"
        url = provider.build_authorize_url(redirect_uri="http://localhost/cb")
        self.assertEqual(url, "https://example.com/auth")
        provider._client.build_authorize_url.assert_called_once_with(redirect_uri="http://localhost/cb")

    def test_build_authorize_url_translates_error(self):
        from qfit.providers.infrastructure.strava_client import StravaClientError
        provider = self._make_provider()
        provider._client.build_authorize_url.side_effect = StravaClientError("no client id")
        with self.assertRaises(ProviderError):
            provider.build_authorize_url()

    def test_exchange_code_for_tokens_delegates(self):
        provider = self._make_provider()
        provider._client.exchange_code_for_tokens.return_value = {"access_token": "abc"}
        payload = provider.exchange_code_for_tokens(authorization_code="code123")
        self.assertEqual(payload["access_token"], "abc")

    def test_exchange_code_for_tokens_translates_error(self):
        from qfit.providers.infrastructure.strava_client import StravaClientError
        provider = self._make_provider()
        provider._client.exchange_code_for_tokens.side_effect = StravaClientError("bad code")
        with self.assertRaises(ProviderError):
            provider.exchange_code_for_tokens(authorization_code="bad")


if __name__ == "__main__":
    unittest.main()
