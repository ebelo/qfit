import unittest
from urllib.error import HTTPError, URLError

from tests import _path  # noqa: F401

from qfit.configuration.application.config_connection_service import (
    build_mapbox_connection_test_request,
    build_strava_connection_test_request,
    validate_mapbox_connection,
    validate_mapbox_connection_request,
    validate_strava_connection,
    validate_strava_connection_request,
)


class TestConnectionRequestBuilders(unittest.TestCase):
    def test_build_strava_connection_test_request(self):
        request = build_strava_connection_test_request(" id ", " secret ", " tok ")

        self.assertEqual(request.client_id, " id ")
        self.assertEqual(request.client_secret, " secret ")
        self.assertEqual(request.refresh_token, " tok ")

    def test_build_mapbox_connection_test_request(self):
        request = build_mapbox_connection_test_request(" pk.test ")

        self.assertEqual(request.access_token, " pk.test ")
        self.assertEqual(request.default_preset_name, "Outdoor")


class TestStravaConnectionValidation(unittest.TestCase):
    def test_requires_client_credentials(self):
        result = validate_strava_connection("", "", "tok")
        self.assertFalse(result.ok)
        self.assertEqual(result.message, "Enter a Strava client ID and client secret first.")

    def test_requires_refresh_token(self):
        result = validate_strava_connection("id", "secret", "")
        self.assertFalse(result.ok)
        self.assertEqual(result.message, "Enter a Strava refresh token first.")

    def test_reports_success_when_refresh_works(self):
        captured = {}

        class FakeClient:
            def __init__(self, **kwargs):
                self.kwargs = kwargs
                captured["client"] = self
                self.fetch_calls = []

            def refresh_access_token(self):
                return {"access_token": "ok"}

            def fetch_activities(self, *, per_page, max_pages):
                self.fetch_calls.append((per_page, max_pages))
                return []

        result = validate_strava_connection("id", "secret", "tok", client_factory=FakeClient)
        self.assertTrue(result.ok)
        self.assertEqual(result.message, "Strava activity access OK")
        self.assertEqual(captured["client"].fetch_calls, [(1, 1)])

    def test_request_variant_reports_success_when_refresh_works(self):
        captured = {}

        class FakeClient:
            def __init__(self, **kwargs):
                self.kwargs = kwargs
                captured["client"] = self
                self.fetch_calls = []

            def refresh_access_token(self):
                return {"access_token": "ok"}

            def fetch_activities(self, *, per_page, max_pages):
                self.fetch_calls.append((per_page, max_pages))
                return []

        request = build_strava_connection_test_request("id", "secret", "tok")
        result = validate_strava_connection_request(request, client_factory=FakeClient)

        self.assertTrue(result.ok)
        self.assertEqual(result.message, "Strava activity access OK")
        self.assertEqual(captured["client"].fetch_calls, [(1, 1)])

    def test_reports_client_errors(self):
        class FakeClient:
            def __init__(self, **kwargs):
                self.kwargs = kwargs

            def refresh_access_token(self):
                raise RuntimeError("bad token")

            def fetch_activities(self, *, per_page, max_pages):
                raise AssertionError("should not fetch after refresh failure")

        result = validate_strava_connection("id", "secret", "tok", client_factory=FakeClient)
        self.assertFalse(result.ok)
        self.assertEqual(result.message, "Strava connection failed: bad token")

    def test_reports_missing_activity_scope(self):
        class FakeClient:
            def __init__(self, **kwargs):
                self.kwargs = kwargs

            def refresh_access_token(self):
                return {"access_token": "ok"}

            def fetch_activities(self, *, per_page, max_pages):
                raise RuntimeError(
                    'Strava API error 401: {"message":"Authorization Error","errors":[{"resource":"Activity","field":"activity.read_permission","code":"missing"}]}'
                )

        result = validate_strava_connection("id", "secret", "tok", client_factory=FakeClient)
        self.assertFalse(result.ok)
        self.assertIn("activity-read permission is missing", result.message)
        self.assertIn("activity:read_all", result.message)


class TestMapboxConnectionValidation(unittest.TestCase):
    def test_requires_access_token(self):
        result = validate_mapbox_connection("")
        self.assertFalse(result.ok)
        self.assertEqual(result.message, "Enter a Mapbox access token first.")

    def test_reports_success(self):
        def fetch_style_definition(token, owner, style_id):
            self.assertEqual(token, "pk.test")
            self.assertEqual(owner, "mapbox")
            self.assertEqual(style_id, "outdoors-v12")
            return {"name": "Mapbox Outdoors"}

        result = validate_mapbox_connection("pk.test", fetch_style_definition=fetch_style_definition)
        self.assertTrue(result.ok)
        self.assertEqual(result.message, "Mapbox connection OK (Mapbox Outdoors)")

    def test_request_variant_reports_success(self):
        def fetch_style_definition(token, owner, style_id):
            self.assertEqual(token, "pk.test")
            self.assertEqual(owner, "mapbox")
            self.assertEqual(style_id, "outdoors-v12")
            return {"name": "Mapbox Outdoors"}

        request = build_mapbox_connection_test_request("pk.test")
        result = validate_mapbox_connection_request(request, fetch_style_definition=fetch_style_definition)

        self.assertTrue(result.ok)
        self.assertEqual(result.message, "Mapbox connection OK (Mapbox Outdoors)")

    def test_reports_http_errors(self):
        def fetch_style_definition(token, owner, style_id):
            raise HTTPError("https://api.mapbox.com", 401, "Unauthorized", hdrs=None, fp=None)

        result = validate_mapbox_connection("pk.test", fetch_style_definition=fetch_style_definition)
        self.assertFalse(result.ok)
        self.assertIn("Mapbox connection failed:", result.message)
        self.assertIn("Unauthorized", result.message)

    def test_reports_url_errors(self):
        def fetch_style_definition(token, owner, style_id):
            raise URLError("offline")

        result = validate_mapbox_connection("pk.test", fetch_style_definition=fetch_style_definition)
        self.assertFalse(result.ok)
        self.assertIn("Mapbox connection failed:", result.message)
        self.assertIn("offline", result.message)


if __name__ == "__main__":
    unittest.main()
