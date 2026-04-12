from __future__ import annotations


def build_strava_connection_status(
    *,
    client_id: str | None,
    client_secret: str | None,
    refresh_token: str | None,
) -> str:
    has_client = bool((client_id or "").strip() and (client_secret or "").strip())
    has_refresh = bool((refresh_token or "").strip())
    if has_client and has_refresh:
        return "Strava connection: ready to fetch activities"
    if has_client:
        return "Strava connection: app credentials saved; add a refresh token in Configuration to fetch activities"
    return "Strava connection: open qfit → Configuration to add your Strava credentials"
