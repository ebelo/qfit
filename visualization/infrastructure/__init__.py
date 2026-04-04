"""QGIS-backed adapters for visualization workflows."""

__all__ = ["BackgroundMapService", "LayerManager", "QgisLayerGateway"]


def __getattr__(name):
    if name == "BackgroundMapService":
        from .background_map_service import BackgroundMapService

        return BackgroundMapService
    if name in {"LayerManager", "QgisLayerGateway"}:
        from .qgis_layer_gateway import QgisLayerGateway

        return QgisLayerGateway
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
