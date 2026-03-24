import logging

logger = logging.getLogger(__name__)

SETTINGS_PREFIX = "qfit"
LEGACY_SETTINGS_PREFIX = "QFIT"


class SettingsService:
    """Centralised get/set wrapper around QSettings with legacy-prefix fallback."""

    def __init__(
        self,
        prefix: str = SETTINGS_PREFIX,
        legacy_prefix: str = LEGACY_SETTINGS_PREFIX,
        qsettings=None,
    ):
        self._prefix = prefix
        self._legacy_prefix = legacy_prefix
        if qsettings is None:
            from qgis.PyQt.QtCore import QSettings
            qsettings = QSettings()
        self._settings = qsettings

    # -- read helpers --------------------------------------------------------

    def get(self, key: str, default=None):
        """Return the value for *key*, falling back to the legacy prefix, then *default*."""
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
        """Store *value* under the current (non-legacy) prefix."""
        self._settings.setValue(f"{self._prefix}/{key}", value)
