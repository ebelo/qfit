"""Compatibility shim for activity sync workflows.

Prefer importing from ``qfit.activities.application.sync_controller``.
This module remains as a stable forwarding import during the package move.
"""

from .activities.application.sync_controller import (
    ExchangeStravaCodeRequest,
    BuildFetchTaskRequest,
    BuildStravaProviderRequest,
    StravaAuthorizeRequest,
    SyncController,
)

__all__ = [
    "BuildFetchTaskRequest",
    "BuildStravaProviderRequest",
    "ExchangeStravaCodeRequest",
    "StravaAuthorizeRequest",
    "SyncController",
]
