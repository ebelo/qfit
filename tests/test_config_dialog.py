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

    def test_configured_token_only(self):
        s = self._settings({"qfit/mapbox_access_token": "pk.abc123"})
        self.assertEqual(mapbox_status_text(s), "Access token saved")

    def test_configured_with_style(self):
        s = self._settings({
            "qfit/mapbox_access_token": "pk.abc123",
            "qfit/mapbox_style_owner": "myuser",
            "qfit/mapbox_style_id": "winter-v1",
        })
        self.assertEqual(
            mapbox_status_text(s),
            "Access token saved · style myuser/winter-v1",
        )

    def test_style_without_token_still_not_configured(self):
        s = self._settings({
            "qfit/mapbox_style_owner": "myuser",
            "qfit/mapbox_style_id": "winter-v1",
        })
        self.assertEqual(mapbox_status_text(s), "Not configured")


class TestConfigDialogSavePersists(unittest.TestCase):
    """Test that _save round-trips values through SettingsService."""

    def _settings(self, data=None):
        return SettingsService(qsettings=FakeQSettings(data or {}))

    def test_save_strava_credentials(self):
        s = self._settings()
        s.set("client_id", "new_id")
        s.set("client_secret", "new_secret")
        s.set("redirect_uri", "http://localhost/cb")
        s.set("refresh_token", "new_token")

        self.assertEqual(s.get("client_id"), "new_id")
        self.assertEqual(s.get("client_secret"), "new_secret")
        self.assertEqual(s.get("redirect_uri"), "http://localhost/cb")
        self.assertEqual(s.get("refresh_token"), "new_token")

    def test_save_mapbox_settings(self):
        s = self._settings()
        s.set("mapbox_access_token", "pk.xyz")
        s.set("mapbox_style_owner", "alice")
        s.set("mapbox_style_id", "dark-v2")
        s.set("tile_mode", "Vector")

        self.assertEqual(s.get("mapbox_access_token"), "pk.xyz")
        self.assertEqual(s.get("mapbox_style_owner"), "alice")
        self.assertEqual(s.get("mapbox_style_id"), "dark-v2")
        self.assertEqual(s.get("tile_mode"), "Vector")

    def test_status_updates_after_save(self):
        s = self._settings()
        self.assertEqual(strava_status_text(s), "Not configured")
        self.assertEqual(mapbox_status_text(s), "Not configured")

        s.set("client_id", "id")
        s.set("client_secret", "sec")
        self.assertEqual(strava_status_text(s), "App credentials set — authorization needed")

        s.set("refresh_token", "tok")
        self.assertEqual(strava_status_text(s), "Connected (refresh token saved)")

        s.set("mapbox_access_token", "pk.test")
        self.assertEqual(mapbox_status_text(s), "Access token saved")

        s.set("mapbox_style_owner", "owner")
        s.set("mapbox_style_id", "style")
        self.assertEqual(mapbox_status_text(s), "Access token saved · style owner/style")


if __name__ == "__main__":
    unittest.main()
