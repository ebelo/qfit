"""Compatibility shim for the visualization/apply workflow.

Prefer importing from ``qfit.visualization.application.visual_apply``.
This module remains as a stable forwarding import during the package move.
"""

from .visualization.application.visual_apply import (
    ApplyVisualizationRequest,
    BackgroundConfig,
    LayerRefs,
    VisualApplyRequest,
    VisualApplyResult,
    VisualApplyService,
)

__all__ = [
    "ApplyVisualizationRequest",
    "BackgroundConfig",
    "LayerRefs",
    "VisualApplyRequest",
    "VisualApplyResult",
    "VisualApplyService",
]
