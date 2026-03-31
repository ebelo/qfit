"""Compatibility shim for the Strava provider adapter.

Prefer importing from ``qfit.providers.infrastructure.strava_provider``.
This module remains as a stable forwarding import during the package move.
"""

from .providers.infrastructure.strava_provider import StravaProvider

__all__ = ["StravaProvider"]
