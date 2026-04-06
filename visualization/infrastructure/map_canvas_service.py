import logging

from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsProject,
    QgsRectangle,
)

logger = logging.getLogger(__name__)

WORKING_CRS = "EPSG:3857"


class MapCanvasService:
    """Manages map canvas CRS setup and extent coordination.

    Extracted from :class:`QgisLayerGateway` to isolate canvas-level concerns
    (CRS switching, extent preservation, zoom-to-layers) from the
    layer-loading orchestration.
    """

    def __init__(self, background_service):
        self._background_service = background_service

    def ensure_working_crs(self, iface, preserve_extent: bool = True):
        """Set the project CRS to Web Mercator.

        Parameters
        ----------
        preserve_extent : bool, default True
            When true, transforms and reapplies the current canvas extent across
            the CRS switch. When false, only switches the CRS and leaves extent
            management to the caller (for example a later zoom-to-layers step).
        """
        project = QgsProject.instance()
        working_crs = QgsCoordinateReferenceSystem(WORKING_CRS)
        if not working_crs.isValid():
            return

        canvas = iface.mapCanvas() if iface is not None else None

        current_extent = canvas.extent() if canvas is not None else None
        current_crs = project.crs()

        project.setCrs(working_crs)
        if canvas is not None:
            canvas.setDestinationCrs(working_crs)
            if preserve_extent and current_extent is not None and current_crs.isValid() and not current_extent.isEmpty():
                transform = QgsCoordinateTransform(current_crs, working_crs, project)
                try:
                    transformed = transform.transformBoundingBox(current_extent)
                    if not transformed.isEmpty():
                        canvas.setExtent(transformed)
                        canvas.refresh()
                except RuntimeError:
                    logger.debug("Extent transform in CRS switch failed", exc_info=True)

    def zoom_to_layers(self, iface, layers):
        """Combine layer extents, snap to tile zoom, and set canvas extent."""
        extents = None
        for layer in layers:
            if layer is None or not layer.isValid():
                continue
            layer_extent = layer.extent()
            if layer_extent.isEmpty():
                continue
            if extents is None:
                extents = QgsRectangle(layer_extent)
            else:
                extents.combineExtentWith(layer_extent)

        if extents is None or extents.isEmpty():
            return

        canvas = iface.mapCanvas() if iface is not None else None
        if canvas is None:
            return

        extents = self._background_service.snap_extent_to_background_tile_zoom(extents, canvas)
        canvas.setExtent(extents)
        canvas.refresh()
