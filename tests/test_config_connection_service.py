import unittest
from urllib.error import HTTPError, URLError

from tests import _path  # noqa: F401

from qfit.config_connection_service import validate_mapbox_connection, validate_strava_connection


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
        class FakeClient:
            def __init__(self, **kwargs):
                self.kwargs = kwargs

            def refresh_access_token(self):
                return {"access_token": "ok"}

        result = validate_strava_connection("id", "secret", "tok", client_factory=FakeClient)
        self.assertTrue(result.ok)
        self.assertEqual(result.message, "Strava connection OK")

    def test_reports_client_errors(self):
        class FakeClient:
            def __init__(self, **kwargs):
                self.kwargs = kwargs

            def refresh_access_token(self):
                raise RuntimeError("bad token")

        result = validate_strava_connection("id", "secret", "tok", client_factory=FakeClient)
        self.assertFalse(result.ok)
        self.assertEqual(result.message, "Strava connection failed: bad token")


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
