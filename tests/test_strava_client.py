import unittest
from unittest.mock import patch

from tests import _path  # noqa: F401
from qfit import strava_client as strava_client_module
from qfit.strava_client import StravaClient, StravaClientError

requests = strava_client_module.requests


class StravaClientTests(unittest.TestCase):
    def test_build_authorize_url_uses_defaults(self):
        client = StravaClient(client_id="123")
        url = client.build_authorize_url()

        self.assertIn("client_id=123", url)
        self.assertIn("response_type=code", url)
        self.assertIn("approval_prompt=force", url)
        self.assertIn("scope=read%2Cactivity%3Aread_all", url)

    def test_normalize_activity_maps_core_fields(self):
        client = StravaClient()
        activity = client.normalize_activity(
            {
                "id": 42,
                "name": "Morning Ride",
                "type": "Ride",
                "sport_type": "GravelRide",
                "start_date": "2026-03-20T06:00:00Z",
                "start_date_local": "2026-03-20T07:00:00Z",
                "timezone": "(GMT+01:00) Europe/Zurich",
                "distance": 12345.6,
                "moving_time": 3600,
                "elapsed_time": 3900,
                "total_elevation_gain": 321.0,
                "average_speed": 3.4,
                "max_speed": 9.9,
                "start_latlng": [46.5, 6.6],
                "end_latlng": [46.6, 6.7],
                "map": {"summary_polyline": "abc"},
                "private_note": "keep me in details",
            }
        )

        self.assertEqual(activity.source, "strava")
        self.assertEqual(activity.source_activity_id, "42")
        self.assertEqual(activity.activity_type, "Ride")
        self.assertEqual(activity.sport_type, "GravelRide")
        self.assertEqual(activity.start_lat, 46.5)
        self.assertEqual(activity.end_lon, 6.7)
        self.assertEqual(activity.summary_polyline, "abc")
        self.assertEqual(activity.geometry_source, "summary_polyline")
        self.assertEqual(activity.details_json["private_note"], "keep me in details")
        self.assertIn("normalized_at", activity.details_json)

    def test_extract_stream_bundle_supports_dict_and_list_payloads(self):
        client = StravaClient()

        self.assertEqual(
            client._extract_stream_bundle(
                {
                    "latlng": {"data": [[46.5, 6.6], [46.6, 6.7]]},
                    "time": {"data": [0, 10]},
                }
            ),
            {"latlng": [[46.5, 6.6], [46.6, 6.7]], "time": [0, 10]},
        )
        self.assertEqual(
            client._extract_stream_bundle(
                [
                    {"type": "latlng", "data": [[46.5, 6.6], [46.6, 6.7]]},
                    {"type": "time", "data": [0, 10]},
                ]
            ),
            {"latlng": [[46.5, 6.6], [46.6, 6.7]], "time": [0, 10]},
        )

    def test_apply_stream_bundle_updates_activity(self):
        client = StravaClient()
        activity = client.normalize_activity({"id": 42, "name": "Run"})

        result = client._apply_stream_bundle_to_activity(
            activity,
            {"latlng": [[46.5, 6.6], [46.6, 6.7]], "time": [0, 10]},
        )

        self.assertTrue(result)
        self.assertEqual(activity.geometry_source, "stream")
        self.assertEqual(activity.geometry_points, [(46.5, 6.6), (46.6, 6.7)])
        self.assertEqual(activity.details_json["stream_point_count"], 2)
        self.assertEqual(activity.details_json["stream_metrics"], {"time": [0, 10]})
        self.assertEqual(activity.details_json["stream_metric_keys"], ["time"])

    def test_enrich_activities_uses_cache_before_network(self):
        client = StravaClient()
        activity = client.normalize_activity({"id": 42, "name": "Run"})

        with patch.object(client, "_load_cached_stream_bundle", return_value={"latlng": [[46.5, 6.6]]}), patch.object(
            client, "fetch_activity_stream_bundle"
        ) as fetch_mock:
            client.enrich_activities_with_streams([activity])

        fetch_mock.assert_not_called()
        self.assertEqual(client.last_stream_enrichment_stats["cached"], 1)
        self.assertEqual(activity.details_json["stream_cache"], "hit")

    def test_parse_rate_limit_pair_and_remaining(self):
        client = StravaClient()
        self.assertEqual(client._parse_rate_limit_pair("200, 2000"), (200, 2000))
        self.assertEqual(client._parse_rate_limit_pair("bad"), (None, None))
        self.assertEqual(client._remaining(200, 50), 150)
        self.assertIsNone(client._remaining(None, 50))

    def test_build_request_headers_disables_connection_reuse(self):
        client = StravaClient()

        headers = client._build_request_headers(token="abc", content_type="application/x-www-form-urlencoded")

        self.assertEqual(headers["Connection"], "close")
        self.assertEqual(headers["Authorization"], "Bearer abc")
        self.assertEqual(headers["Content-Type"], "application/x-www-form-urlencoded")
        self.assertIn("qfit/", headers["User-Agent"])

    def test_fetch_activities_paginates_until_last_page(self):
        """max_pages=0 should fetch all pages, stopping when a short page is received."""
        client = StravaClient(client_id="123", client_secret="abc", refresh_token="tok")

        # Simulate: page 1 → full (200), page 2 → partial (3) → done
        page_responses = [
            [{"id": i, "name": f"Activity {i}"} for i in range(200)],
            [{"id": 300, "name": "Last activity"}, {"id": 301, "name": "Also last"}, {"id": 302, "name": "End"}],
        ]
        call_count = [0]

        def fake_request_json(request, operation=None, **kwargs):
            idx = call_count[0]
            call_count[0] += 1
            if idx == 0:
                # access token refresh
                return {"access_token": "fake_token"}
            return page_responses[idx - 1]

        client._request_json = fake_request_json

        activities = client.fetch_activities(per_page=200, max_pages=0)
        self.assertEqual(len(activities), 203)

    def test_fetch_activities_full_sync_uses_before_cursor(self):
        client = StravaClient(client_id="123", client_secret="abc", refresh_token="tok")
        seen_urls = []
        call_count = [0]

        def fake_request_json(request, operation=None, **kwargs):
            idx = call_count[0]
            call_count[0] += 1
            if idx == 0:
                return {"access_token": "fake_token"}

            seen_urls.append(request)
            if idx == 1:
                return [
                    {"id": 1, "name": "A1", "start_date": "2026-03-30T08:00:00Z"},
                    {"id": 2, "name": "A2", "start_date": "2026-03-29T08:00:00Z"},
                ]
            return [{"id": 3, "name": "A3", "start_date": "2026-03-28T08:00:00Z"}]

        client._request_json = fake_request_json

        with patch("qfit.strava_client.time.sleep"):
            activities = client.fetch_activities(per_page=2, max_pages=0)

        self.assertEqual(len(activities), 3)
        self.assertIn("page=1&per_page=2", seen_urls[0])
        self.assertIn("page=1&per_page=2&before=1774771199", seen_urls[1])

    def test_fetch_activities_full_sync_reduces_page_size_after_transient_failure(self):
        client = StravaClient(client_id="123", client_secret="abc", refresh_token="tok")
        seen_urls = []
        call_count = [0]

        def fake_request_json(request, operation=None, **kwargs):
            idx = call_count[0]
            call_count[0] += 1
            if idx == 0:
                return {"access_token": "fake_token"}

            seen_urls.append(request)
            if idx == 1:
                raise StravaClientError("Fetching Strava activities page 1 failed after 3 attempts due to a transient network error")
            return [{"id": 1, "name": "A1", "start_date": "2026-03-30T08:00:00Z"}]

        client._request_json = fake_request_json

        with patch("qfit.strava_client.time.sleep"):
            activities = client.fetch_activities(per_page=50, max_pages=0)

        self.assertEqual(len(activities), 1)
        self.assertIn("per_page=50", seen_urls[0])
        self.assertIn("per_page=25", seen_urls[1])

    def test_fetch_activities_respects_max_pages_limit(self):
        """max_pages=1 should stop after the first page even if it is full."""
        client = StravaClient(client_id="123", client_secret="abc", refresh_token="tok")

        call_count = [0]

        def fake_request_json(request, operation=None, **kwargs):
            idx = call_count[0]
            call_count[0] += 1
            if idx == 0:
                return {"access_token": "fake_token"}
            # Return a full page every time
            return [{"id": i, "name": f"Activity {i}"} for i in range(50)]

        client._request_json = fake_request_json

        activities = client.fetch_activities(per_page=50, max_pages=1)
        self.assertEqual(len(activities), 50)
        # Only 2 calls: token refresh + 1 page
        self.assertEqual(call_count[0], 2)

    def test_fetch_activities_paces_between_full_pages(self):
        client = StravaClient(client_id="123", client_secret="abc", refresh_token="tok")
        call_count = [0]

        def fake_request_json(request, operation=None, **kwargs):
            idx = call_count[0]
            call_count[0] += 1
            if idx == 0:
                return {"access_token": "fake_token"}
            if idx == 1:
                return [{"id": i, "name": f"Activity {i}"} for i in range(2)]
            return [{"id": 3, "name": "Last activity"}]

        client._request_json = fake_request_json

        with patch("qfit.strava_client.time.sleep") as sleep_mock:
            activities = client.fetch_activities(per_page=2, max_pages=0)

        self.assertEqual(len(activities), 3)
        sleep_mock.assert_any_call(client.PAGE_REQUEST_DELAY_SECONDS)

    def test_request_json_retries_transient_connection_reset(self):
        client = StravaClient()
        calls = []

        class _FakeResponse:
            headers = {}

            def raise_for_status(self):
                return None

            def json(self):
                return {"ok": True}

        def fake_request(method, url, data=None, headers=None, timeout=60):
            calls.append(timeout)
            if len(calls) < 3:
                raise requests.ConnectionError(ConnectionResetError(10054, "forcibly closed by remote host"))
            return _FakeResponse()

        with patch.object(client.session, "request", side_effect=fake_request), patch(
            "qfit.strava_client.time.sleep"
        ) as sleep_mock:
            payload = client._request_json("https://example.test", operation="Fetching Strava activities page 1")

        self.assertEqual(payload, {"ok": True})
        self.assertEqual(len(calls), 3)
        self.assertEqual(sleep_mock.call_count, 2)

    def test_request_json_reports_operation_after_retry_exhaustion(self):
        client = StravaClient()

        with patch.object(
            client.session,
            "request",
            side_effect=requests.ConnectionError(ConnectionResetError(10054, "forcibly closed by remote host")),
        ), patch("qfit.strava_client.time.sleep"):
            with self.assertRaisesRegex(
                StravaClientError,
                "Refreshing Strava access token failed after 3 attempts due to a transient network error",
            ):
                client._request_json("https://example.test", operation="Refreshing Strava access token")

    def test_request_json_reports_non_retryable_network_error_with_operation(self):
        client = StravaClient()

        with patch.object(client.session, "request", side_effect=requests.ConnectionError("certificate verify failed")), patch(
            "qfit.strava_client.time.sleep"
        ) as sleep_mock:
            with self.assertRaisesRegex(
                StravaClientError,
                "Fetching Strava detailed stream for activity 42 failed due to a network error",
            ):
                client._request_json("https://example.test", operation="Fetching Strava detailed stream for activity 42")

        sleep_mock.assert_not_called()

    def test_request_json_uses_configured_session(self):
        client = StravaClient()

        class _FakeResponse:
            headers = {"X-RateLimit-Limit": "200,2000", "X-RateLimit-Usage": "1,10"}

            def raise_for_status(self):
                return None

            def json(self):
                return {"ok": True}

        with patch.object(client.session, "request", return_value=_FakeResponse()) as request_mock:
            payload = client._request_json(
                "https://example.test",
                method="POST",
                data=b"abc",
                headers={"X-Test": "1"},
                operation="Example request",
            )

        self.assertEqual(payload, {"ok": True})
        request_mock.assert_called_once_with(
            method="POST",
            url="https://example.test",
            data=b"abc",
            headers={"X-Test": "1"},
            timeout=60,
        )

    def test_retry_delay_seconds_uses_exponential_backoff(self):
        client = StravaClient()

        self.assertEqual(client._retry_delay_seconds(1), 1.0)
        self.assertEqual(client._retry_delay_seconds(2), 2.0)
        self.assertEqual(client._retry_delay_seconds(3), 4.0)

    def test_next_activities_before_uses_oldest_activity_start(self):
        client = StravaClient()
        activities = [
            client.normalize_activity({"id": 1, "name": "A1", "start_date": "2026-03-30T08:00:00Z"}),
            client.normalize_activity({"id": 2, "name": "A2", "start_date": "2026-03-29T08:00:00Z"}),
        ]

        self.assertEqual(client._next_activities_before(activities), 1774771199)

    def test_reduced_activity_page_size_only_for_full_sync_transient_errors(self):
        client = StravaClient()

        self.assertEqual(
            client._reduced_activity_page_size(
                50,
                StravaClientError("failed after 3 attempts due to a transient network error"),
                max_pages=0,
            ),
            25,
        )
        self.assertIsNone(
            client._reduced_activity_page_size(
                50,
                StravaClientError("some other error"),
                max_pages=0,
            )
        )
        self.assertIsNone(
            client._reduced_activity_page_size(
                50,
                StravaClientError("failed after 3 attempts due to a transient network error"),
                max_pages=2,
            )
        )

    def test_rate_limit_retry_guidance_for_short_window(self):
        client = StravaClient()
        message = client._rate_limit_retry_guidance({"short_remaining": 0, "long_remaining": 800})
        self.assertIn("15 minutes", message)

    def test_rate_limit_retry_guidance_for_daily_limit(self):
        client = StravaClient()
        message = client._rate_limit_retry_guidance({"short_remaining": 0, "long_remaining": 0})
        self.assertIn("daily quota", message)

    def test_rate_limit_pause_notice_uses_remaining_quota(self):
        client = StravaClient()
        client.last_rate_limit = {"short_remaining": 2, "long_remaining": 40}

        message = client._rate_limit_pause_notice()

        self.assertIn("Stopped early", message)
        self.assertIn("short=2", message)
        self.assertIn("long=40", message)

    def test_should_pause_full_sync_for_rate_limit(self):
        client = StravaClient()
        client.last_rate_limit = {"short_remaining": 3, "long_remaining": 100}
        self.assertTrue(client._should_pause_full_sync_for_rate_limit())

    def test_fetch_activities_stops_early_when_rate_limit_headroom_is_low(self):
        client = StravaClient(client_id="123", client_secret="abc", refresh_token="tok")
        call_count = [0]

        def fake_request_json(request, operation=None, **kwargs):
            idx = call_count[0]
            call_count[0] += 1
            if idx == 0:
                return {"access_token": "fake_token"}
            client.last_rate_limit = {"short_remaining": 3, "long_remaining": 200}
            return [{"id": i, "name": f"Activity {i}", "start_date": "2026-03-30T08:00:00Z"} for i in range(2)]

        client._request_json = fake_request_json

        with patch("qfit.strava_client.time.sleep"):
            activities = client.fetch_activities(per_page=2, max_pages=0)

        self.assertEqual(len(activities), 2)
        self.assertIn("Stopped early", client.last_fetch_notice)

    def test_request_json_reports_rate_limit_error(self):
        client = StravaClient()

        class _FakeResponse:
            status_code = 429
            text = '{"message":"Rate Limit Exceeded"}'
            headers = {"X-RateLimit-Limit": "100,1000", "X-RateLimit-Usage": "100,62"}
            url = "https://example.test"

        response = _FakeResponse()
        http_error = requests.HTTPError(response=response)

        with patch.object(client.session, "request", side_effect=http_error):
            with self.assertRaisesRegex(StravaClientError, "Strava rate limit"):
                client._request_json("https://example.test", operation="Fetching Strava activities page 62")


if __name__ == "__main__":
    unittest.main()
