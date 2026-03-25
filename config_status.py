"""Pure-logic helpers for computing configuration status text.

These functions depend only on ``SettingsService`` and can be tested
without a running Qt/QGIS environment.
"""

from .settings_service import SettingsService


def strava_status_text(settings: SettingsService) -> str:
    """Return a human-readable Strava connection status."""
    client_id = settings.get("client_id", "")
    client_secret = settings.get("client_secret", "")
    refresh_token = settings.get("refresh_token", "")
    if refresh_token:
        return "Connected (refresh token saved)"
    if client_id and client_secret:
        return "App credentials set — authorization needed"
    return "Not configured"


def mapbox_status_text(settings: SettingsService) -> str:
    """Return a human-readable Mapbox connection status."""
    token = settings.get("mapbox_access_token", "")
    if not token:
        return "Not configured"
    style_owner = settings.get("mapbox_style_owner", "")
    style_id = settings.get("mapbox_style_id", "")
    if style_owner and style_id:
        return f"Access token saved · style {style_owner}/{style_id}"
    return "Access token saved"
