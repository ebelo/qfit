import os
from dataclasses import dataclass
from typing import Any

from ..atlas.export_controller import AtlasExportController
from ..atlas.export_service import AtlasExportService
from ..background_map_controller import BackgroundMapController
from ..fetch_result_service import FetchResultService
from ..load_workflow import LoadWorkflowService
from ..qfit_cache import QfitCache
from ..settings_service import SettingsService
from ..sync_controller import SyncController
from ..visual_apply import VisualApplyService


@dataclass(frozen=True)
class DockWidgetDependencies:
    """Workflow collaborators used by :class:`qfit.qfit_dockwidget.QfitDockWidget`.

    Grouping these dependencies behind a single adapter object keeps the dock
    widget constructor focused on UI setup and provides a narrow injection seam
    for tests and future composition-root refactors.
    """

    settings: SettingsService
    sync_controller: SyncController
    atlas_export_controller: AtlasExportController
    layer_gateway: Any
    background_controller: BackgroundMapController
    load_workflow: LoadWorkflowService
    visual_apply: VisualApplyService
    atlas_export_service: AtlasExportService
    fetch_result_service: FetchResultService
    cache: QfitCache


def build_dockwidget_dependencies(iface) -> DockWidgetDependencies:
    """Build the default workflow adapters used by ``QfitDockWidget``."""

    settings = SettingsService()
    sync_controller = SyncController()
    atlas_export_controller = AtlasExportController()
    layer_gateway = _build_layer_gateway(iface)
    cache = _build_cache()
    return DockWidgetDependencies(
        settings=settings,
        sync_controller=sync_controller,
        atlas_export_controller=atlas_export_controller,
        layer_gateway=layer_gateway,
        background_controller=BackgroundMapController(layer_gateway),
        load_workflow=LoadWorkflowService(layer_gateway),
        visual_apply=VisualApplyService(layer_gateway),
        atlas_export_service=AtlasExportService(layer_gateway),
        fetch_result_service=FetchResultService(sync_controller),
        cache=cache,
    )


def _build_layer_gateway(iface):
    from ..visualization.infrastructure.qgis_layer_gateway import QgisLayerGateway

    return QgisLayerGateway(iface)



def _writable_app_data_location() -> str:
    from qgis.PyQt.QtCore import QStandardPaths

    return QStandardPaths.writableLocation(QStandardPaths.AppDataLocation)



def _build_cache() -> QfitCache:
    base_path = _writable_app_data_location()
    if not base_path:
        base_path = os.path.join(os.path.expanduser("~"), ".qfit")

    current_cache_path = os.path.join(base_path, "qfit", "cache")
    legacy_cache_path = os.path.join(base_path, "QFIT", "cache")
    if not os.path.exists(current_cache_path) and os.path.exists(legacy_cache_path):
        return QfitCache(legacy_cache_path)
    return QfitCache(current_cache_path)
