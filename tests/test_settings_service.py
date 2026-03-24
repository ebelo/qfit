import unittest
from unittest.mock import MagicMock

from tests import _path  # noqa: F401
from qfit.settings_service import SettingsService


class FakeQSettings:
    """Minimal dict-backed stand-in for QSettings."""

    def __init__(self, data=None):
        self._data = data or {}

    def value(self, key, default=None):
        return self._data.get(key, default)

    def setValue(self, key, value):
        self._data[key] = value


class SettingsServiceGetTests(unittest.TestCase):
    def test_get_returns_current_prefix_value(self):
        qs = FakeQSettings({"qfit/client_id": "abc"})
        svc = SettingsService(qsettings=qs)
        self.assertEqual(svc.get("client_id"), "abc")

    def test_get_falls_back_to_legacy_prefix(self):
        qs = FakeQSettings({"QFIT/client_id": "legacy_val"})
        svc = SettingsService(qsettings=qs)
        self.assertEqual(svc.get("client_id"), "legacy_val")

    def test_get_prefers_current_over_legacy(self):
        qs = FakeQSettings({"qfit/key": "new", "QFIT/key": "old"})
        svc = SettingsService(qsettings=qs)
        self.assertEqual(svc.get("key"), "new")

    def test_get_returns_default_when_missing(self):
        qs = FakeQSettings({})
        svc = SettingsService(qsettings=qs)
        self.assertEqual(svc.get("missing", "fallback"), "fallback")

    def test_get_skips_empty_string_values(self):
        qs = FakeQSettings({"qfit/key": "", "QFIT/key": "legacy"})
        svc = SettingsService(qsettings=qs)
        self.assertEqual(svc.get("key", "default"), "legacy")

    def test_get_returns_default_when_both_empty(self):
        qs = FakeQSettings({"qfit/key": "", "QFIT/key": ""})
        svc = SettingsService(qsettings=qs)
        self.assertEqual(svc.get("key", "default"), "default")


class SettingsServiceGetBoolTests(unittest.TestCase):
    def test_get_bool_true_string(self):
        qs = FakeQSettings({"qfit/flag": "true"})
        svc = SettingsService(qsettings=qs)
        self.assertTrue(svc.get_bool("flag"))

    def test_get_bool_false_string(self):
        qs = FakeQSettings({"qfit/flag": "false"})
        svc = SettingsService(qsettings=qs)
        self.assertFalse(svc.get_bool("flag"))

    def test_get_bool_native_bool(self):
        qs = FakeQSettings({"qfit/flag": True})
        svc = SettingsService(qsettings=qs)
        self.assertTrue(svc.get_bool("flag"))

    def test_get_bool_one_string(self):
        qs = FakeQSettings({"qfit/flag": "1"})
        svc = SettingsService(qsettings=qs)
        self.assertTrue(svc.get_bool("flag"))

    def test_get_bool_default(self):
        qs = FakeQSettings({})
        svc = SettingsService(qsettings=qs)
        self.assertFalse(svc.get_bool("flag"))
        self.assertTrue(svc.get_bool("flag", default=True))

    def test_get_bool_integer_value(self):
        qs = FakeQSettings({"qfit/flag": 1})
        svc = SettingsService(qsettings=qs)
        self.assertTrue(svc.get_bool("flag"))


class SettingsServiceSetTests(unittest.TestCase):
    def test_set_stores_under_current_prefix(self):
        qs = FakeQSettings()
        svc = SettingsService(qsettings=qs)
        svc.set("client_id", "new_val")
        self.assertEqual(qs._data["qfit/client_id"], "new_val")

    def test_set_value_is_retrievable(self):
        qs = FakeQSettings()
        svc = SettingsService(qsettings=qs)
        svc.set("per_page", 50)
        self.assertEqual(svc.get("per_page"), 50)

    def test_custom_prefixes(self):
        qs = FakeQSettings({"custom/key": "val", "OLD/key": "old_val"})
        svc = SettingsService(prefix="custom", legacy_prefix="OLD", qsettings=qs)
        self.assertEqual(svc.get("key"), "val")
        svc.set("key2", "v2")
        self.assertEqual(qs._data["custom/key2"], "v2")
