"""Backward-compatible import for qfit's QGIS layer gateway adapter."""

from .visualization.infrastructure.qgis_layer_gateway import QgisLayerGateway

# Preserve the long-standing import path while application services migrate
# toward the explicit layer gateway terminology.
LayerManager = QgisLayerGateway
