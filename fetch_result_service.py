"""Compatibility shim for fetch result workflow objects.

Prefer importing from ``qfit.activities.application.fetch_result_service``.
This module remains as a stable forwarding import during the package move.
"""

from .activities.application.fetch_result_service import FetchActivitiesRequest, FetchResult, FetchResultService

__all__ = ["FetchActivitiesRequest", "FetchResult", "FetchResultService"]
