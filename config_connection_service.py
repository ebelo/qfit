"""Compatibility shim for qfit configuration connection-test helpers.

Prefer importing from ``qfit.configuration.application.config_connection_service``.
This module remains as a stable forwarding import during the package move.
"""

from .configuration.application.config_connection_service import (
    ConnectionTestResult,
    MapboxConnectionTestRequest,
    StravaConnectionTestRequest,
    build_mapbox_connection_test_request,
    build_strava_connection_test_request,
    validate_mapbox_connection,
    validate_mapbox_connection_request,
    validate_strava_connection,
    validate_strava_connection_request,
)

__all__ = [
    "ConnectionTestResult",
    "MapboxConnectionTestRequest",
    "StravaConnectionTestRequest",
    "build_mapbox_connection_test_request",
    "build_strava_connection_test_request",
    "validate_mapbox_connection",
    "validate_mapbox_connection_request",
    "validate_strava_connection",
    "validate_strava_connection_request",
]
