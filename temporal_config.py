"""Compatibility shim for visualization temporal configuration helpers.

Prefer importing from ``qfit.visualization.application.temporal_config``.
This module remains as a stable forwarding import during the package move.
"""

from .visualization.application.temporal_config import (
    DEFAULT_TEMPORAL_MODE_LABEL,
    TEMPORAL_MODE_LABELS,
    TemporalLayerPlan,
    build_temporal_plan,
    describe_temporal_configuration,
    is_temporal_mode_enabled,
    temporal_mode_labels,
)

__all__ = [
    "DEFAULT_TEMPORAL_MODE_LABEL",
    "TEMPORAL_MODE_LABELS",
    "TemporalLayerPlan",
    "build_temporal_plan",
    "describe_temporal_configuration",
    "is_temporal_mode_enabled",
    "temporal_mode_labels",
]
