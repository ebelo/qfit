"""Compatibility shim for qfit UI/settings binding helpers.

Prefer importing from ``qfit.configuration.application.ui_settings_binding``.
This module remains as a stable forwarding import during the package move.
"""

from .configuration.application.ui_settings_binding import UIFieldBinding, load_bindings, save_bindings

__all__ = ["UIFieldBinding", "load_bindings", "save_bindings"]
