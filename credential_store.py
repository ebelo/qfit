"""Secure credential storage for qfit.

Sensitive credentials (OAuth secrets, API tokens) must not be kept in plain
QSettings.  This module provides a small abstraction over the system keyring
(via the ``keyring`` library) with a graceful fallback to QSettings when no
secure backend is available.

Sensitive keys
--------------
``SENSITIVE_KEYS`` lists the QSettings keys whose values should be stored in
the credential store rather than in plain QSettings.  All other keys continue
to use QSettings as before.

Backend selection
-----------------
``make_credential_store()`` inspects the active ``keyring`` backend at
runtime:

* If a real backend is detected (SecretService / Keychain / Windows
  Credential Manager), a ``KeyringCredentialStore`` is returned.
* If the ``keyring`` library is absent, or its selected backend is
  ``keyring.backends.fail.Keyring`` (no usable backend), a
  ``NullCredentialStore`` is returned.  Callers must then fall back to plain
  QSettings and a warning is logged.

The backend can be forced in tests or CI by setting the environment variable::

    PYTHON_KEYRING_BACKEND=keyring.backends.fail.Keyring

before the ``keyring`` package is first imported.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

KEYRING_SERVICE = "qfit"

# Keys whose values are considered sensitive and must be stored securely.
SENSITIVE_KEYS: frozenset = frozenset(
    {
        "client_secret",
        "refresh_token",
        "mapbox_access_token",
    }
)


class CredentialStore:
    """Abstract base for credential stores."""

    @property
    def available(self) -> bool:
        """True when this store can actually persist secrets."""
        raise NotImplementedError

    def get(self, key: str) -> Optional[str]:
        """Return the secret for *key*, or ``None`` if not stored."""
        raise NotImplementedError

    def set(self, key: str, value: str) -> None:
        """Persist *value* under *key*."""
        raise NotImplementedError

    def delete(self, key: str) -> None:
        """Remove the secret for *key* (no-op if not present)."""
        raise NotImplementedError


class KeyringCredentialStore(CredentialStore):
    """Credential store backed by the OS keyring via the ``keyring`` library.

    On most desktops this resolves to:

    * **Linux** – GNOME Keyring / KWallet via SecretService D-Bus API
    * **macOS** – macOS Keychain
    * **Windows** – Windows Credential Manager
    """

    def __init__(self):
        import keyring as _keyring  # lazy import – avoids module-level hang

        self._keyring = _keyring

    @property
    def available(self) -> bool:
        return True

    def get(self, key: str) -> Optional[str]:
        try:
            return self._keyring.get_password(KEYRING_SERVICE, key)
        except Exception as exc:
            logger.warning("keyring get failed for %r: %s", key, exc)
            return None

    def set(self, key: str, value: str) -> None:
        self._keyring.set_password(KEYRING_SERVICE, key, value)

    def delete(self, key: str) -> None:
        try:
            self._keyring.delete_password(KEYRING_SERVICE, key)
        except Exception:
            pass


class NullCredentialStore(CredentialStore):
    """No-op store used when no secure backend is available.

    ``available`` returns ``False`` so that callers know to fall back to plain
    QSettings.
    """

    @property
    def available(self) -> bool:
        return False

    def get(self, key: str) -> Optional[str]:
        return None

    def set(self, key: str, value: str) -> None:
        pass

    def delete(self, key: str) -> None:
        pass


class InMemoryCredentialStore(CredentialStore):
    """In-memory credential store for use in unit tests."""

    def __init__(self, data: Optional[dict] = None):
        self._data: dict = dict(data or {})

    @property
    def available(self) -> bool:
        return True

    def get(self, key: str) -> Optional[str]:
        return self._data.get(key)

    def set(self, key: str, value: str) -> None:
        self._data[key] = value

    def delete(self, key: str) -> None:
        self._data.pop(key, None)


def make_credential_store() -> CredentialStore:
    """Return the best available credential store for this environment.

    Checks the active ``keyring`` backend at call time.  If a real backend is
    found (i.e. not ``keyring.backends.fail.Keyring``), returns a
    :class:`KeyringCredentialStore`.  Otherwise returns a
    :class:`NullCredentialStore` and logs an informational message.
    """
    try:
        import keyring
        from keyring.backends import fail as _fail

        backend = keyring.get_keyring()
        if isinstance(backend, _fail.Keyring):
            logger.info(
                "No system keyring backend available "
                "(backend=%s); sensitive credentials will be stored in plain "
                "QSettings — consider installing a keyring backend",
                type(backend).__name__,
            )
            return NullCredentialStore()

        logger.debug("Using keyring backend: %s", type(backend).__name__)
        return KeyringCredentialStore()

    except ImportError:
        logger.info(
            "keyring library not installed; sensitive credentials will be "
            "stored in plain QSettings"
        )
        return NullCredentialStore()
