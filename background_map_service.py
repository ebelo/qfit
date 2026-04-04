"""Compatibility shim for the visualization background-map service.

Prefer importing from ``qfit.visualization.infrastructure.background_map_service``.
This module remains as a stable forwarding import during the package move.
"""

from .visualization.infrastructure.background_map_service import BackgroundMapService

__all__ = ["BackgroundMapService"]
