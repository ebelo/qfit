"""Deprecated compatibility shim for qfit's QGIS layer gateway adapter.

Use :mod:`qfit.visualization.infrastructure.qgis_layer_gateway` for new
in-repo imports.
"""

from .visualization.infrastructure.qgis_layer_gateway import QgisLayerGateway

# Preserve the long-standing import path while application services migrate
# toward the explicit layer gateway terminology.
LayerManager = QgisLayerGateway
