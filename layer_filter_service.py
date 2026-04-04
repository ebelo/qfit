"""Compatibility shim for the visualization layer-filter service.

Prefer importing from ``qfit.visualization.infrastructure.layer_filter_service``.
This module remains as a stable forwarding import during the package move.
"""

from .visualization.infrastructure.layer_filter_service import LayerFilterService

__all__ = ["LayerFilterService"]
