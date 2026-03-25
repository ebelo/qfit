import unittest
from unittest.mock import MagicMock

from tests import _path  # noqa: F401
from qfit.credential_store import InMemoryCredentialStore, NullCredentialStore
from qfit.settings_service import SettingsService


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


# ---------------------------------------------------------------------------
# Credential-store routing (issue #126)
# ---------------------------------------------------------------------------


class SettingsServiceCredentialRoutingTests(unittest.TestCase):
    """Sensitive keys must be routed through the credential store."""

    def _svc(self, qs_data=None, cred_data=None):
        qs = FakeQSettings(qs_data or {})
        cred = InMemoryCredentialStore(cred_data or {})
        return SettingsService(qsettings=qs, credential_store=cred), qs, cred

    # -- get ------------------------------------------------------------------

    def test_get_sensitive_reads_from_cred_store(self):
        svc, _, cred = self._svc(cred_data={"client_secret": "from_keyring"})
        self.assertEqual(svc.get("client_secret"), "from_keyring")

    def test_get_sensitive_falls_back_to_qsettings(self):
        """Legacy: secret in QSettings, nothing in cred store → still readable."""
        svc, _, _ = self._svc(qs_data={"qfit/client_secret": "plain"})
        self.assertEqual(svc.get("client_secret"), "plain")

    def test_get_sensitive_prefers_cred_store_over_qsettings(self):
        svc, _, _ = self._svc(
            qs_data={"qfit/refresh_token": "plaintext"},
            cred_data={"refresh_token": "from_keyring"},
        )
        self.assertEqual(svc.get("refresh_token"), "from_keyring")

    def test_get_non_sensitive_uses_qsettings(self):
        svc, _, cred = self._svc(qs_data={"qfit/client_id": "app123"})
        # Non-sensitive key must NOT go to the credential store
        cred.set("client_id", "WRONG")
        self.assertEqual(svc.get("client_id"), "app123")

    # -- set ------------------------------------------------------------------

    def test_set_sensitive_writes_to_cred_store(self):
        svc, qs, cred = self._svc()
        svc.set("client_secret", "newsecret")
        self.assertEqual(cred.get("client_secret"), "newsecret")

    def test_set_sensitive_does_not_write_to_qsettings(self):
        svc, qs, _ = self._svc()
        svc.set("refresh_token", "tok")
        self.assertNotIn("qfit/refresh_token", qs._data)

    def test_set_sensitive_removes_plaintext_from_qsettings(self):
        """Writing a secret must purge any pre-existing plaintext QSettings entry."""
        svc, qs, _ = self._svc(qs_data={"qfit/client_secret": "old_plain"})
        svc.set("client_secret", "newval")
        self.assertNotIn("qfit/client_secret", qs._data)

    def test_set_non_sensitive_writes_to_qsettings(self):
        svc, qs, _ = self._svc()
        svc.set("client_id", "appid")
        self.assertEqual(qs._data.get("qfit/client_id"), "appid")

    # -- NullCredentialStore (no keyring available) ---------------------------

    def test_set_sensitive_falls_back_to_qsettings_when_no_keyring(self):
        qs = FakeQSettings()
        svc = SettingsService(qsettings=qs, credential_store=NullCredentialStore())
        svc.set("mapbox_access_token", "pk.test")
        self.assertEqual(qs._data.get("qfit/mapbox_access_token"), "pk.test")

    def test_get_sensitive_reads_qsettings_when_no_keyring(self):
        qs = FakeQSettings({"qfit/mapbox_access_token": "pk.test"})
        svc = SettingsService(qsettings=qs, credential_store=NullCredentialStore())
        self.assertEqual(svc.get("mapbox_access_token"), "pk.test")

    def test_set_sensitive_falls_back_to_qsettings_on_keyring_error(self):
        """If the keyring write raises, the value must still land in QSettings."""
        from unittest.mock import MagicMock

        broken_cred = MagicMock()
        broken_cred.available = True
        broken_cred.set.side_effect = RuntimeError("keyring locked")

        qs = FakeQSettings()
        svc = SettingsService(qsettings=qs, credential_store=broken_cred)
        svc.set("refresh_token", "tok")

        self.assertEqual(qs._data.get("qfit/refresh_token"), "tok")
