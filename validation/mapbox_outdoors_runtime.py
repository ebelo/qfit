from __future__ import annotations


def qgis_runtime_snapshot(qgis_api: object) -> dict[str, object]:
    return {
        "qgis_version": getattr(qgis_api, "QGIS_VERSION", None),
        "qgis_version_int": getattr(qgis_api, "QGIS_VERSION_INT", None),
        "qgis_release_name": getattr(qgis_api, "QGIS_RELEASE_NAME", None),
    }


def format_qgis_runtime_label(value: object, *, missing_label: str) -> str:
    if not isinstance(value, dict):
        return missing_label
    qgis_version = value.get("qgis_version")
    if qgis_version:
        return str(qgis_version)
    qgis_version_int = value.get("qgis_version_int")
    if qgis_version_int is not None:
        return str(qgis_version_int)
    qgis_release_name = value.get("qgis_release_name")
    if qgis_release_name:
        return str(qgis_release_name)
    return missing_label


def _integer_tile_zooms(matrix, scale: float) -> tuple[int, int]:
    try:
        return matrix.scaleToZoomLevel(scale, False), matrix.scaleToZoomLevel(scale, True)
    except TypeError:
        # QGIS 3.28/3.30 expose only the inherited, matrix-clamped overload.
        # Their renderer uses that same integer zoom for rendering and fetching.
        zoom = matrix.scaleToZoomLevel(scale)
        return zoom, zoom


def qgis_render_context_snapshot(*, settings, layer, image, camera_zoom: float) -> dict[str, object]:
    """Record actual capture scale/DPI without calibrating or mutating rendering.

    For this harness's Mapbox tile matrix, the renderer derives its continuous
    vector_tile_zoom and rounded integer zooms from the map settings scale.
    The requested browser camera zoom is not a substitute for those values.
    """
    scale = settings.scale()
    matrix = layer.tileMatrixSet()
    extent = settings.visibleExtent()
    render_zoom, fetch_zoom = _integer_tile_zooms(matrix, scale)
    return {
        "requested_camera_zoom": camera_zoom,
        "map_settings_output_dpi": settings.outputDpi(),
        "image_logical_dpi": [image.logicalDpiX(), image.logicalDpiY()],
        "image_device_pixel_ratio": image.devicePixelRatio(),
        "image_size_pixels": [image.width(), image.height()],
        "map_settings_size_pixels": [settings.outputSize().width(), settings.outputSize().height()],
        "map_crs": settings.destinationCrs().authid(),
        "visible_extent": [extent.xMinimum(), extent.yMinimum(), extent.xMaximum(), extent.yMaximum()],
        "map_scale": scale,
        "vector_tile_zoom": matrix.scaleToZoom(scale),
        "integer_render_zoom": render_zoom,
        "integer_fetch_zoom": fetch_zoom,
    }
