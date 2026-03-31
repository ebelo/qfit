"""Compatibility shim for the Strava API adapter.

Prefer importing from ``qfit.providers.infrastructure.strava_client``.
This module remains available to avoid breaking existing imports during the
feature-oriented package migration.
"""

from .providers.infrastructure.strava_client import StravaClient, StravaClientError, requests

__all__ = ["StravaClient", "StravaClientError", "requests"]
