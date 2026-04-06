"""Compatibility shim for qfit configuration settings services.

Prefer importing from ``qfit.configuration.application.settings_service``.
This module remains as a stable forwarding import during the package move.
"""

from .configuration.application.settings_service import (
    LEGACY_SETTINGS_PREFIX,
    SETTINGS_PREFIX,
    QgisSettingsAdapter,
    SettingsService,
)

__all__ = [
    "LEGACY_SETTINGS_PREFIX",
    "SETTINGS_PREFIX",
    "QgisSettingsAdapter",
    "SettingsService",
]
