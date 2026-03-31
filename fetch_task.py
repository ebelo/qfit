"""Compatibility shim for the background fetch task.

Prefer importing from ``qfit.activities.application.fetch_task``.
This module remains as a stable forwarding import during the package move.
"""

from .activities.application.fetch_task import FetchTask

__all__ = ["FetchTask"]
