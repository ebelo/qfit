"""Compatibility shim for qfit configuration status helpers.

Prefer importing from ``qfit.configuration.application.config_status``.
This module remains as a stable forwarding import during the package move.
"""

from .configuration.application.config_status import mapbox_status_text, strava_status_text

__all__ = ["mapbox_status_text", "strava_status_text"]
