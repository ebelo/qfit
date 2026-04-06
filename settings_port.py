"""Compatibility shim for qfit configuration settings protocol.

Prefer importing from ``qfit.configuration.application.settings_port``.
This module remains as a stable forwarding import during the package move.
"""

from .configuration.application.settings_port import SettingsPort

__all__ = ["SettingsPort"]
