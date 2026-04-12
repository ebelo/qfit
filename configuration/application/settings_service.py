import logging
from typing import Optional

from ..infrastructure.credential_store import (
    CredentialStore,
    SENSITIVE_KEYS,
    make_credential_store,
)
from .settings_port import SettingsPort

logger = logging.getLogger(__name__)

SETTINGS_PREFIX = "qfit"
LEGACY_SETTINGS_PREFIX = "QFIT"


class QgisSettingsAdapter(SettingsPort):
    """QGIS-backed implementation of the :class:`~qfit.settings_port.SettingsPort`.

    Sensitive keys (see :data:`~qfit.configuration.infrastructure.credential_store.SENSITIVE_KEYS`) are
    routed through a :class:`~qfit.configuration.infrastructure.credential_store.CredentialStore` so they
    are stored in the OS keyring rather than in plain QSettings.  All other
    keys continue to use QSettings directly.

    When no secure keyring backend is available (e.g. headless CI), the
    credential store transparently falls back to QSettings with a logged
    warning so that existing behaviour is preserved.
    """

    def __init__(
        self,
        prefix: str = SETTINGS_PREFIX,
        legacy_prefix: str = LEGACY_SETTINGS_PREFIX,
        qsettings=None,
        credential_store: Optional[CredentialStore] = None,
    ):
        self._prefix = prefix
        self._legacy_prefix = legacy_prefix
        if qsettings is None:
            from qgis.PyQt.QtCore import QSettings
            qsettings = QSettings()
        self._settings = qsettings
        self._credential_store = (
            credential_store if credential_store is not None else make_credential_store()
        )

    # -- read helpers --------------------------------------------------------

    def get(self, key: str, default=None):
        """Return the value for *key*, falling back to the legacy prefix, then *default*.

        For sensitive keys the credential store is checked first; if the secret
        is not there (e.g. a legacy installation that predates this change),
        the lookup falls through to QSettings so existing credentials remain
        accessible until the user saves them again.
        """
        if key in SENSITIVE_KEYS:
            secret = self._credential_store.get(key)
            if secret is not None:
                return secret
            # Fall through to QSettings for backward-compatibility with
            # credentials stored before this feature was introduced.

        value = self._settings.value(f"{self._prefix}/{key}", None)
        if value not in (None, ""):
            return value
        legacy_value = self._settings.value(f"{self._legacy_prefix}/{key}", None)
        if legacy_value not in (None, ""):
            return legacy_value
        return default

    def get_bool(self, key: str, default: bool = False) -> bool:
        """Return a boolean for *key*, handling string representations."""
        value = self.get(key, default)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ("1", "true", "yes", "on")
        return bool(value)

    # -- write helpers -------------------------------------------------------

    def set(self, key: str, value) -> None:
        """Store *value* under the current (non-legacy) prefix.

        Sensitive keys are written to the credential store when a secure
        backend is available.  On success the plaintext QSettings entry is
        removed so the secret is no longer duplicated in plain storage.

        When no secure backend is available, a warning is logged and the value
        is stored in QSettings (legacy behaviour).
        """
        if key in SENSITIVE_KEYS:
            if self._credential_store.available:
                try:
                    self._credential_store.set(key, value)
                    # Remove the plaintext copy that may have been written by
                    # an older version of the plugin.
                    self._settings.remove(f"{self._prefix}/{key}")
                    self._settings.remove(f"{self._legacy_prefix}/{key}")
                    return
                except Exception as exc:
                    logger.warning(
                        "Keyring write failed for %r (%s); falling back to "
                        "plain QSettings.  The keyring may be locked or "
                        "temporarily unavailable.",
                        key,
                        exc,
                    )
            else:
                logger.warning(
                    "No secure keyring available; storing sensitive key %r in "
                    "plain QSettings.  Install a keyring backend to protect "
                    "this credential.",
                    key,
                )
        self._settings.setValue(f"{self._prefix}/{key}", value)


# Backward-compatible name kept while qfit incrementally moves callers toward
# the SettingsPort abstraction.
SettingsService = QgisSettingsAdapter
