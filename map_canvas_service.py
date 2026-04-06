"""Compatibility shim for the visualization map-canvas service.

Prefer importing from ``qfit.visualization.infrastructure.map_canvas_service``.
This module remains as a stable forwarding import during the package move.
"""

from .visualization.infrastructure.map_canvas_service import MapCanvasService, WORKING_CRS

__all__ = ["MapCanvasService", "WORKING_CRS"]
