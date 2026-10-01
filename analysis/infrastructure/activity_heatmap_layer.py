"""Synchronous compatibility entry point for the cached route-usage raster.

The live dock uses a cancellable task; legacy application callers can still
build the same artifact synchronously. Sampled points are deliberately ignored.
"""
ACTIVITY_HEATMAP_LAYER_NAME = "qfit activity heatmap"


def build_activity_heatmap_layer(activities_layer=None, points_layer=None):
    # Preserve the legacy keyword API without allowing sample density to bias visits.
    del points_layer
    from pathlib import Path
    if activities_layer is None or not activities_layer.isValid():
        return None, 0
    path = activities_layer.source().split("|", 1)[0]
    if not Path(path).is_file():
        return None, 0
    from qgis.PyQt.QtCore import QStandardPaths
    from ...ui.qt_enum_compat import qt_class_enum_value
    from ..application.route_heatmap import RouteHeatmapRequest
    from .route_heatmap_raster import build_route_heatmap
    from .route_heatmap_layer import create_route_heatmap_layer
    root = QStandardPaths.writableLocation(qt_class_enum_value(QStandardPaths, "StandardLocation", "AppDataLocation"))
    request = RouteHeatmapRequest(path, activities_layer.subsetString(), str(Path(root) / "qfit/cache/route-heatmaps"))
    artifact = build_route_heatmap(request)
    return (create_route_heatmap_layer(artifact), artifact.activity_count) if artifact is not None else (None, 0)
