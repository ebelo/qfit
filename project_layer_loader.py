"""Compatibility shim for the visualization project-layer loader.

Prefer importing from ``qfit.visualization.infrastructure.project_layer_loader``.
This module remains as a stable forwarding import during the package move.
"""

from .visualization.infrastructure.project_layer_loader import ProjectLayerLoader

__all__ = ["ProjectLayerLoader"]
