"""Compatibility shim for the visualization temporal service.

Prefer importing from ``qfit.visualization.infrastructure.temporal_service``.
This module remains as a stable forwarding import during the package move.
"""

from .visualization.infrastructure.temporal_service import TemporalService

__all__ = ["TemporalService"]
