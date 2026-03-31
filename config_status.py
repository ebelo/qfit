"""Pure-logic helpers for computing configuration status text.

These functions depend only on ``SettingsService`` and can be tested
without a running Qt/QGIS environment.
"""

from .settings_port import SettingsPort


def strava_status_text(settings: SettingsPort) -> str:
    """Return a human-readable Strava connection status."""
    client_id = settings.get("client_id", "")
    client_secret = settings.get("client_secret", "")
    refresh_token = settings.get("refresh_token", "")
    if refresh_token:
        return "Connected (refresh token saved)"
    if client_id and client_secret:
        return "App credentials set — authorization needed"
    return "Not configured"


def mapbox_status_text(settings: SettingsPort) -> str:
    """Return a human-readable Mapbox connection status."""
    token = settings.get("mapbox_access_token", "")
    if not token:
        return "Not configured"
    return "Access token saved"
