"""QGIS-backed adapters for visualization workflows."""

__all__ = [
    "BackgroundMapService",
    "LayerFilterService",
    "LayerManager",
    "LayerStyleService",
    "QgisLayerGateway",
    "TemporalService",
]


def __getattr__(name):
    if name == "BackgroundMapService":
        from .background_map_service import BackgroundMapService

        return BackgroundMapService
    if name == "LayerFilterService":
        from .layer_filter_service import LayerFilterService

        return LayerFilterService
    if name in {"LayerManager", "QgisLayerGateway"}:
        from .qgis_layer_gateway import QgisLayerGateway

        return QgisLayerGateway
    if name == "LayerStyleService":
        from .layer_style_service import LayerStyleService

        return LayerStyleService
    if name == "TemporalService":
        from .temporal_service import TemporalService

        return TemporalService
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
