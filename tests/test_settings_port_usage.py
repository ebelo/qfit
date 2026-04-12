import unittest

from tests import _path  # noqa: F401

from qfit.configuration.application.config_status import mapbox_status_text, strava_status_text
from qfit.ui_settings_binding import UIFieldBinding, load_bindings, save_bindings


class FakeSettingsPort:
    def __init__(self, data=None):
        self._data = dict(data or {})

    def get(self, key, default=None):
        return self._data.get(key, default)

    def get_bool(self, key, default=False):
        value = self._data.get(key, default)
        if isinstance(value, str):
            return value.lower() in ("1", "true", "yes", "on")
        return bool(value)

    def set(self, key, value):
        self._data[key] = value


class TextWidget:
    def __init__(self, value=""):
        self._value = value

    def text(self):
        return self._value

    def setText(self, value):
        self._value = value


class SettingsPortUsageTests(unittest.TestCase):
    def test_config_status_helpers_only_need_settings_port(self):
        settings = FakeSettingsPort(
            {
                "client_id": "id123",
                "client_secret": "sec456",
                "refresh_token": "tok789",
                "mapbox_access_token": "pk.test",
            }
        )

        self.assertEqual(strava_status_text(settings), "Connected (refresh token saved)")
        self.assertEqual(mapbox_status_text(settings), "Access token saved")

    def test_ui_settings_bindings_work_with_port_contract(self):
        widget = TextWidget("  hello  ")
        binding = UIFieldBinding("greeting", "default", lambda: widget.text().strip(), widget.setText)
        settings = FakeSettingsPort()

        save_bindings([binding], settings)
        self.assertEqual(settings.get("greeting"), "hello")

        widget.setText("")
        load_bindings([binding], settings)
        self.assertEqual(widget.text(), "hello")


if __name__ == "__main__":
    unittest.main()
