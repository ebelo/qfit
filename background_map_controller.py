"""Compatibility shim for the background-map workflow.

Prefer importing from ``qfit.visualization.application.background_map_controller``.
This module remains as a stable forwarding import during the package move.
"""

from .visualization.application.background_map_controller import (
    BackgroundMapController,
    LoadBackgroundRequest,
    LoadBackgroundResult,
)

__all__ = ["BackgroundMapController", "LoadBackgroundRequest", "LoadBackgroundResult"]
