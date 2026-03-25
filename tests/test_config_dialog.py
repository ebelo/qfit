import unittest

from tests import _path  # noqa: F401

from qfit.config_status import mapbox_status_text, strava_status_text
from qfit.settings_service import SettingsService


class FakeQSettings:
    """In-memory QSettings replacement for unit tests."""

    def __init__(self, data=None):
        self._data = data or {}

    def value(self, key, default=None):
        return self._data.get(key, default)

    def setValue(self, key, value):
        self._data[key] = value


class TestStravaStatusText(unittest.TestCase):
    def _settings(self, data=None):
        return SettingsService(qsettings=FakeQSettings(data or {}))

    def test_not_configured(self):
        self.assertEqual(strava_status_text(self._settings()), "Not configured")

    def test_credentials_only(self):
        s = self._settings({
            "qfit/client_id": "id123",
            "qfit/client_secret": "sec456",
        })
        self.assertEqual(strava_status_text(s), "App credentials set — authorization needed")

    def test_connected(self):
        s = self._settings({
            "qfit/client_id": "id123",
            "qfit/client_secret": "sec456",
            "qfit/refresh_token": "tok789",
        })
        self.assertEqual(strava_status_text(s), "Connected (refresh token saved)")

    def test_token_without_credentials_still_connected(self):
        s = self._settings({"qfit/refresh_token": "tok789"})
        self.assertEqual(strava_status_text(s), "Connected (refresh token saved)")


class TestMapboxStatusText(unittest.TestCase):
    def _settings(self, data=None):
        return SettingsService(qsettings=FakeQSettings(data or {}))

    def test_not_configured(self):
        self.assertEqual(mapbox_status_text(self._settings()), "Not configured")

    def test_configured(self):
        s = self._settings({"qfit/mapbox_access_token": "pk.abc123"})
        self.assertEqual(mapbox_status_text(s), "Access token saved")


if __name__ == "__main__":
    unittest.main()
