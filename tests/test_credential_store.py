"""Tests for the credential_store module."""

import unittest

from tests import _path  # noqa: F401

from qfit.configuration.infrastructure.credential_store import (
    SENSITIVE_KEYS,
    InMemoryCredentialStore,
    KeyringCredentialStore,
    NullCredentialStore,
    make_credential_store,
)


class TestSensitiveKeys(unittest.TestCase):
    def test_expected_keys_present(self):
        self.assertIn("client_secret", SENSITIVE_KEYS)
        self.assertIn("refresh_token", SENSITIVE_KEYS)
        self.assertIn("mapbox_access_token", SENSITIVE_KEYS)

    def test_non_sensitive_keys_absent(self):
        for key in ("client_id", "redirect_uri", "per_page", "mapbox_style_owner"):
            self.assertNotIn(key, SENSITIVE_KEYS)


class TestNullCredentialStore(unittest.TestCase):
    def setUp(self):
        self.store = NullCredentialStore()

    def test_not_available(self):
        self.assertFalse(self.store.available)

    def test_get_returns_none(self):
        self.assertIsNone(self.store.get("anything"))

    def test_set_is_noop(self):
        self.store.set("key", "value")
        self.assertIsNone(self.store.get("key"))

    def test_delete_is_noop(self):
        self.store.delete("key")  # must not raise


class TestInMemoryCredentialStore(unittest.TestCase):
    def setUp(self):
        self.store = InMemoryCredentialStore()

    def test_available(self):
        self.assertTrue(self.store.available)

    def test_set_then_get(self):
        self.store.set("client_secret", "abc123")
        self.assertEqual(self.store.get("client_secret"), "abc123")

    def test_get_missing_returns_none(self):
        self.assertIsNone(self.store.get("nonexistent"))

    def test_delete_removes_value(self):
        self.store.set("refresh_token", "tok")
        self.store.delete("refresh_token")
        self.assertIsNone(self.store.get("refresh_token"))

    def test_delete_nonexistent_is_noop(self):
        self.store.delete("nonexistent")  # must not raise

    def test_overwrite_existing(self):
        self.store.set("mapbox_access_token", "old")
        self.store.set("mapbox_access_token", "new")
        self.assertEqual(self.store.get("mapbox_access_token"), "new")

    def test_initial_data(self):
        store = InMemoryCredentialStore({"client_secret": "pre"})
        self.assertEqual(store.get("client_secret"), "pre")

    def test_multiple_keys_independent(self):
        self.store.set("client_secret", "s")
        self.store.set("refresh_token", "t")
        self.assertEqual(self.store.get("client_secret"), "s")
        self.assertEqual(self.store.get("refresh_token"), "t")


class TestMakeCredentialStore(unittest.TestCase):
    """make_credential_store() must not hang and must return a usable store.

    conftest.py sets PYTHON_KEYRING_BACKEND=keyring.backends.fail.Keyring so
    keyring.get_keyring() returns a fail.Keyring instance in tests.  We
    therefore expect a NullCredentialStore to be returned.
    """

    def test_returns_credential_store(self):
        store = make_credential_store()
        # Must expose the CredentialStore interface
        self.assertTrue(hasattr(store, "available"))
        self.assertTrue(hasattr(store, "get"))
        self.assertTrue(hasattr(store, "set"))
        self.assertTrue(hasattr(store, "delete"))

    def test_returns_null_store_when_keyring_fails(self):
        """With PYTHON_KEYRING_BACKEND=fail, we expect NullCredentialStore."""
        store = make_credential_store()
        self.assertIsInstance(store, NullCredentialStore)

    def test_null_store_get_returns_none(self):
        store = make_credential_store()
        self.assertIsNone(store.get("client_secret"))


class TestKeyringCredentialStoreInterface(unittest.TestCase):
    """KeyringCredentialStore interface: only test the wrapper, not real keyring I/O."""

    def test_available_is_true(self):
        import unittest.mock as mock

        fake_keyring = mock.MagicMock()
        fake_keyring.get_password.return_value = "mysecret"
        fake_keyring.set_password.return_value = None
        fake_keyring.delete_password.return_value = None

        store = KeyringCredentialStore.__new__(KeyringCredentialStore)
        store._keyring = fake_keyring

        self.assertTrue(store.available)

    def test_get_delegates_to_keyring(self):
        import unittest.mock as mock

        fake_keyring = mock.MagicMock()
        fake_keyring.get_password.return_value = "tok123"

        store = KeyringCredentialStore.__new__(KeyringCredentialStore)
        store._keyring = fake_keyring

        result = store.get("refresh_token")
        self.assertEqual(result, "tok123")
        fake_keyring.get_password.assert_called_once_with("qfit", "refresh_token")

    def test_set_delegates_to_keyring(self):
        import unittest.mock as mock

        fake_keyring = mock.MagicMock()
        store = KeyringCredentialStore.__new__(KeyringCredentialStore)
        store._keyring = fake_keyring

        store.set("client_secret", "secret!")
        fake_keyring.set_password.assert_called_once_with("qfit", "client_secret", "secret!")

    def test_delete_delegates_to_keyring(self):
        import unittest.mock as mock

        fake_keyring = mock.MagicMock()
        store = KeyringCredentialStore.__new__(KeyringCredentialStore)
        store._keyring = fake_keyring

        store.delete("mapbox_access_token")
        fake_keyring.delete_password.assert_called_once_with("qfit", "mapbox_access_token")

    def test_get_returns_none_on_exception(self):
        import unittest.mock as mock

        fake_keyring = mock.MagicMock()
        fake_keyring.get_password.side_effect = RuntimeError("keyring error")

        store = KeyringCredentialStore.__new__(KeyringCredentialStore)
        store._keyring = fake_keyring

        self.assertIsNone(store.get("refresh_token"))

    def test_delete_swallows_exception(self):
        import unittest.mock as mock

        fake_keyring = mock.MagicMock()
        fake_keyring.delete_password.side_effect = RuntimeError("not found")

        store = KeyringCredentialStore.__new__(KeyringCredentialStore)
        store._keyring = fake_keyring

        store.delete("client_secret")  # must not raise


if __name__ == "__main__":
    unittest.main()
