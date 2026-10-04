"""Background computation only; QGIS raster widgets are created by the caller."""
from qgis.core import QgsTask

from ..domain.route_density import HeatmapCancelled
from .route_heatmap_raster import build_route_heatmap


class RouteHeatmapTask(QgsTask):
    def __init__(self, request, on_finished):
        super().__init__("Build static route heatmap", QgsTask.Flag.CanCancel)
        self.request = request
        self._on_finished = on_finished
        self.artifact = None
        self.error_message = None

    def run(self):
        try:
            self.artifact = build_route_heatmap(self.request, self.isCanceled, self.setProgress)
            return not self.isCanceled()
        except HeatmapCancelled:
            return False
        except Exception as exc:
            self.error_message = str(exc)
            return False

    def finished(self, ok):
        self._on_finished(self, self.artifact, self.error_message, self.isCanceled() and not ok)
