"""Connection-test helpers for the qfit configuration dialog.

These routines validate provider credentials without depending on Qt widgets,
so they can be unit-tested in isolation and reused by the configuration UI.
"""

from __future__ import annotations

from dataclasses import dataclass
from .mapbox_config import DEFAULT_BACKGROUND_PRESET, fetch_mapbox_style_definition, preset_defaults
from .strava_client import StravaClient, StravaClientError


@dataclass(frozen=True)
class ConnectionTestResult:
    ok: bool
    message: str


def validate_strava_connection(
    client_id: str,
    client_secret: str,
    refresh_token: str,
    *,
    client_factory=StravaClient,
) -> ConnectionTestResult:
    """Validate current Strava credentials and activity-read access."""
    resolved_client_id = (client_id or "").strip()
    resolved_client_secret = (client_secret or "").strip()
    resolved_refresh_token = (refresh_token or "").strip()

    if not resolved_client_id or not resolved_client_secret:
        return ConnectionTestResult(False, "Enter a Strava client ID and client secret first.")
    if not resolved_refresh_token:
        return ConnectionTestResult(False, "Enter a Strava refresh token first.")

    try:
        client = client_factory(
            client_id=resolved_client_id,
            client_secret=resolved_client_secret,
            refresh_token=resolved_refresh_token,
        )
        client.refresh_access_token()
        client.fetch_activities(per_page=1, max_pages=1)
    except StravaClientError as exc:
        return ConnectionTestResult(False, _format_strava_validation_error(str(exc)))
    except Exception as exc:  # noqa: BLE001
        return ConnectionTestResult(False, _format_strava_validation_error(str(exc)))

    return ConnectionTestResult(True, "Strava activity access OK")


def _format_strava_validation_error(message: str) -> str:
    if "activity.read_permission" in message:
        return (
            "Strava connection failed: token refresh succeeded, but activity-read permission is missing. "
            "Re-authorize Strava and save a refresh token with activity:read_all scope."
        )
    return f"Strava connection failed: {message}"


def validate_mapbox_connection(
    access_token: str,
    *,
    fetch_style_definition=fetch_mapbox_style_definition,
    default_preset_name: str = DEFAULT_BACKGROUND_PRESET,
) -> ConnectionTestResult:
    """Validate the current Mapbox token using a built-in qfit preset style."""
    token = (access_token or "").strip()
    if not token:
        return ConnectionTestResult(False, "Enter a Mapbox access token first.")

    style_owner, style_id = preset_defaults(default_preset_name)

    try:
        style_definition = fetch_style_definition(token, style_owner, style_id)
    except (OSError, ValueError) as exc:
        return ConnectionTestResult(False, f"Mapbox connection failed: {exc}")
    except Exception as exc:  # noqa: BLE001
        return ConnectionTestResult(False, f"Mapbox connection failed: {exc}")

    style_name = None
    if isinstance(style_definition, dict):
        style_name = style_definition.get("name")

    if style_name:
        return ConnectionTestResult(True, f"Mapbox connection OK ({style_name})")
    return ConnectionTestResult(True, "Mapbox connection OK")
