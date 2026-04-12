import unittest

from tests import _path  # noqa: F401

from qfit.configuration.infrastructure.credential_store import InMemoryCredentialStore
from qfit.configuration.application.settings_service import SettingsService
from qfit.configuration.application.ui_settings_binding import UIFieldBinding, load_bindings, save_bindings


class FakeQSettings:
    """Minimal dict-backed stand-in for QSettings."""

    def __init__(self, data=None):
        self._data = data or {}

    def value(self, key, default=None):
        return self._data.get(key, default)

    def setValue(self, key, value):
        self._data[key] = value

    def remove(self, key):
        self._data.pop(key, None)


class TextWidget:
    """Minimal mock for QLineEdit-style widgets."""

    def __init__(self, value=""):
        self._value = value

    def text(self):
        return self._value

    def setText(self, value):
        self._value = value


def _settings(data=None):
    return SettingsService(
        qsettings=FakeQSettings(data or {}),
        credential_store=InMemoryCredentialStore(),
    )


class TestUIFieldBindingLoadSave(unittest.TestCase):

    def test_load_sets_widget_from_settings(self):
        w = TextWidget()
        b = UIFieldBinding("my_key", "default_val", lambda: w.text(), w.setText)
        s = _settings({"qfit/my_key": "stored_val"})
        load_bindings([b], s)
        self.assertEqual(w.text(), "stored_val")

    def test_load_uses_default_when_key_missing(self):
        w = TextWidget()
        b = UIFieldBinding("my_key", "default_val", lambda: w.text(), w.setText)
        s = _settings()
        load_bindings([b], s)
        self.assertEqual(w.text(), "default_val")

    def test_save_persists_widget_value(self):
        w = TextWidget("hello")
        b = UIFieldBinding("my_key", "", lambda: w.text().strip(), w.setText)
        s = _settings()
        save_bindings([b], s)
        self.assertEqual(s.get("my_key"), "hello")

    def test_save_strips_whitespace_via_getter(self):
        w = TextWidget("  trimmed  ")
        b = UIFieldBinding("my_key", "", lambda: w.text().strip(), w.setText)
        s = _settings()
        save_bindings([b], s)
        self.assertEqual(s.get("my_key"), "trimmed")

    def test_roundtrip_load_then_save(self):
        w = TextWidget()
        b = UIFieldBinding("my_key", "", lambda: w.text().strip(), w.setText)
        s = _settings({"qfit/my_key": "roundtrip"})
        load_bindings([b], s)
        s2 = _settings()
        save_bindings([b], s2)
        self.assertEqual(s2.get("my_key"), "roundtrip")

    def test_multiple_bindings_load_independently(self):
        w1 = TextWidget()
        w2 = TextWidget()
        bindings = [
            UIFieldBinding("key1", "d1", lambda: w1.text(), w1.setText),
            UIFieldBinding("key2", "d2", lambda: w2.text(), w2.setText),
        ]
        s = _settings({"qfit/key1": "v1"})
        load_bindings(bindings, s)
        self.assertEqual(w1.text(), "v1")
        self.assertEqual(w2.text(), "d2")

    def test_multiple_bindings_save_independently(self):
        w1 = TextWidget("a")
        w2 = TextWidget("b")
        bindings = [
            UIFieldBinding("key1", "", lambda: w1.text(), w1.setText),
            UIFieldBinding("key2", "", lambda: w2.text(), w2.setText),
        ]
        s = _settings()
        save_bindings(bindings, s)
        self.assertEqual(s.get("key1"), "a")
        self.assertEqual(s.get("key2"), "b")

class TestConfigDialogBindings(unittest.TestCase):
    """Verify the binding table covers the expected config dialog keys."""

    EXPECTED_KEYS = {
        "client_id",
        "client_secret",
        "redirect_uri",
        "refresh_token",
        "mapbox_access_token",
    }

    def _make_dialog_bindings(self):
        """Build a minimal stand-in for the QfitConfigDialog binding table."""
        from qfit.providers.infrastructure.strava_client import StravaClient

        client_id = TextWidget()
        client_secret = TextWidget()
        redirect_uri = TextWidget()
        refresh_token = TextWidget()
        mapbox_token = TextWidget()

        return [
            UIFieldBinding("client_id", "", lambda w=client_id: w.text().strip(), client_id.setText),
            UIFieldBinding("client_secret", "", lambda w=client_secret: w.text().strip(), client_secret.setText),
            UIFieldBinding("redirect_uri", StravaClient.DEFAULT_REDIRECT_URI, lambda w=redirect_uri: w.text().strip(), redirect_uri.setText),
            UIFieldBinding("refresh_token", "", lambda w=refresh_token: w.text().strip(), refresh_token.setText),
            UIFieldBinding("mapbox_access_token", "", lambda w=mapbox_token: w.text().strip(), mapbox_token.setText),
        ]

    def test_all_expected_keys_covered(self):
        bindings = self._make_dialog_bindings()
        actual_keys = {b.key for b in bindings}
        self.assertEqual(actual_keys, self.EXPECTED_KEYS)

    def test_defaults_round_trip(self):
        # SettingsService intentionally skips empty strings (treats them as
        # "not set"), so only non-empty defaults are meaningful to assert.
        bindings = self._make_dialog_bindings()
        s = _settings()
        load_bindings(bindings, s)
        save_bindings(bindings, s)
        from qfit.providers.infrastructure.strava_client import StravaClient
        self.assertEqual(s.get("redirect_uri"), StravaClient.DEFAULT_REDIRECT_URI)

    def test_stored_values_survive_roundtrip(self):
        bindings = self._make_dialog_bindings()
        stored = {
            "qfit/client_id": "myid",
            "qfit/redirect_uri": "http://example.com/cb",
            "qfit/mapbox_access_token": "pk.abc123",
        }
        s = _settings(stored)
        load_bindings(bindings, s)
        s2 = _settings()
        save_bindings(bindings, s2)
        self.assertEqual(s2.get("client_id"), "myid")
        self.assertEqual(s2.get("redirect_uri"), "http://example.com/cb")
        self.assertEqual(s2.get("mapbox_access_token"), "pk.abc123")


if __name__ == "__main__":
    unittest.main()
