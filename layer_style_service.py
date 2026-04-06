"""Compatibility shim for the visualization layer-style service.

Prefer importing from ``qfit.visualization.infrastructure.layer_style_service``.
This module remains as a stable forwarding import during the package move.
"""

from .visualization.infrastructure.layer_style_service import LayerStyleService

__all__ = ["LayerStyleService"]
