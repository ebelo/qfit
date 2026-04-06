"""Connection-test helpers for the qfit configuration dialog.

These routines validate provider credentials without depending on Qt widgets,
so they can be unit-tested in isolation and reused by the configuration UI.
"""

from __future__ import annotations

from dataclasses import dataclass
from ...mapbox_config import (
    DEFAULT_BACKGROUND_PRESET,
    fetch_mapbox_style_definition,
    preset_defaults,
)
from ...providers.infrastructure.strava_client import StravaClient, StravaClientError


@dataclass(frozen=True)
class StravaConnectionTestRequest:
    client_id: str = ""
    client_secret: str = ""
    refresh_token: str = ""


@dataclass(frozen=True)
class MapboxConnectionTestRequest:
    access_token: str = ""
    default_preset_name: str = DEFAULT_BACKGROUND_PRESET


@dataclass(frozen=True)
class ConnectionTestResult:
    ok: bool
    message: str


def build_strava_connection_test_request(
    client_id: str,
    client_secret: str,
    refresh_token: str,
) -> StravaConnectionTestRequest:
    return StravaConnectionTestRequest(
        client_id=client_id,
        client_secret=client_secret,
        refresh_token=refresh_token,
    )


def build_mapbox_connection_test_request(
    access_token: str,
    *,
    default_preset_name: str = DEFAULT_BACKGROUND_PRESET,
) -> MapboxConnectionTestRequest:
    return MapboxConnectionTestRequest(
        access_token=access_token,
        default_preset_name=default_preset_name,
    )


def validate_strava_connection(
    client_id: str,
    client_secret: str,
    refresh_token: str,
    *,
    client_factory=StravaClient,
) -> ConnectionTestResult:
    request = build_strava_connection_test_request(client_id, client_secret, refresh_token)
    return validate_strava_connection_request(request, client_factory=client_factory)


def validate_strava_connection_request(
    request: StravaConnectionTestRequest,
    *,
    client_factory=StravaClient,
) -> ConnectionTestResult:
    """Validate current Strava credentials and activity-read access."""
    resolved_client_id = (request.client_id or "").strip()
    resolved_client_secret = (request.client_secret or "").strip()
    resolved_refresh_token = (request.refresh_token or "").strip()

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
    request = build_mapbox_connection_test_request(
        access_token,
        default_preset_name=default_preset_name,
    )
    return validate_mapbox_connection_request(
        request,
        fetch_style_definition=fetch_style_definition,
    )


def validate_mapbox_connection_request(
    request: MapboxConnectionTestRequest,
    *,
    fetch_style_definition=fetch_mapbox_style_definition,
) -> ConnectionTestResult:
    """Validate the current Mapbox token using a built-in qfit preset style."""
    token = (request.access_token or "").strip()
    if not token:
        return ConnectionTestResult(False, "Enter a Mapbox access token first.")

    style_owner, style_id = preset_defaults(request.default_preset_name)

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
