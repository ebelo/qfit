"""QGIS-backed adapters for visualization workflows."""

__all__ = ["BackgroundMapService", "LayerManager", "QgisLayerGateway", "TemporalService"]


def __getattr__(name):
    if name == "BackgroundMapService":
        from .background_map_service import BackgroundMapService

        return BackgroundMapService
    if name in {"LayerManager", "QgisLayerGateway"}:
        from .qgis_layer_gateway import QgisLayerGateway

        return QgisLayerGateway
    if name == "TemporalService":
        from .temporal_service import TemporalService

        return TemporalService
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
