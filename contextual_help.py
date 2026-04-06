"""Compatibility shim for qfit dock-widget contextual help helpers.

Prefer importing from ``qfit.ui.contextual_help``.
This module remains as a stable forwarding import during the package move.
"""

try:
    from .ui.contextual_help import ContextualHelpBinder, HelpEntry, build_dock_help_entries
except ImportError:  # pragma: no cover - top-level test/import fallback
    from ui.contextual_help import ContextualHelpBinder, HelpEntry, build_dock_help_entries

__all__ = ["ContextualHelpBinder", "HelpEntry", "build_dock_help_entries"]
