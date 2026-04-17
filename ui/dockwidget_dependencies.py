import os
from dataclasses import dataclass

from ..analysis.application.analysis_workflow_provider import build_analysis_workflow
from ..analysis.application.analysis_workflow_port import AnalysisWorkflowPort
from ..atlas.export_controller import AtlasExportController
from ..atlas.export_service import AtlasExportService
from ..atlas.export_use_case import AtlasExportUseCase
from ..activities.application.fetch_result_service import FetchResultService
from ..activities.application.activity_preview_service import ActivityPreviewService
from ..activities.application.load_workflow import (
    ClearDatabaseWorkflow,
    LoadDatasetWorkflow,
    LoadWorkflowService,
    StoreActivitiesWorkflow,
)
from ..qfit_cache import QfitCache
from ..configuration.application.settings_service import SettingsService
from ..activities.application.sync_controller import SyncController
from ..ui.application import DockActivityWorkflowCoordinator, DockAtlasWorkflowCoordinator
from ..visualization.application import (
    BackgroundMapController,
    LayerGateway,
    ProjectHygienePort,
    VisualApplyService,
)


@dataclass(frozen=True)
class DockWidgetDependencies:
    """Workflow collaborators used by :class:`qfit.qfit_dockwidget.QfitDockWidget`.

    Grouping these dependencies behind a single adapter object keeps the dock
    widget constructor focused on UI setup and provides a narrow injection seam
    for tests and future composition-root refactors.
    """

    settings: SettingsService
    sync_controller: SyncController
    analysis_workflow: AnalysisWorkflowPort
    atlas_export_controller: AtlasExportController
    atlas_export_use_case: AtlasExportUseCase
    layer_gateway: LayerGateway
    background_controller: BackgroundMapController
    project_hygiene_service: ProjectHygienePort
    store_workflow: StoreActivitiesWorkflow
    dataset_load_workflow: LoadDatasetWorkflow
    clear_database_workflow: ClearDatabaseWorkflow
    load_workflow: LoadWorkflowService
    visual_apply: VisualApplyService
    atlas_export_service: AtlasExportService
    activity_workflow: DockActivityWorkflowCoordinator
    atlas_workflow: DockAtlasWorkflowCoordinator
    cache: QfitCache


def build_dockwidget_dependencies(iface) -> DockWidgetDependencies:
    """Build the default workflow adapters used by ``QfitDockWidget``."""

    settings = SettingsService()
    sync_controller = SyncController()
    atlas_export_controller = AtlasExportController()
    layer_gateway = _build_layer_gateway(iface)
    cache = _build_cache()
    atlas_export_service = AtlasExportService(layer_gateway)
    atlas_export_use_case = AtlasExportUseCase(atlas_export_controller, atlas_export_service)
    fetch_result_service = FetchResultService(sync_controller)
    activity_preview_service = ActivityPreviewService()
    store_workflow = StoreActivitiesWorkflow()
    dataset_load_workflow = LoadDatasetWorkflow(layer_gateway)
    clear_database_workflow = ClearDatabaseWorkflow(layer_gateway)
    return DockWidgetDependencies(
        settings=settings,
        sync_controller=sync_controller,
        analysis_workflow=build_analysis_workflow(),
        atlas_export_controller=atlas_export_controller,
        atlas_export_use_case=atlas_export_use_case,
        layer_gateway=layer_gateway,
        background_controller=BackgroundMapController(layer_gateway),
        project_hygiene_service=_build_project_hygiene_service(),
        store_workflow=store_workflow,
        dataset_load_workflow=dataset_load_workflow,
        clear_database_workflow=clear_database_workflow,
        load_workflow=LoadWorkflowService(
            layer_gateway,
            store_workflow=store_workflow,
            dataset_load_workflow=dataset_load_workflow,
            clear_database_workflow=clear_database_workflow,
        ),
        visual_apply=VisualApplyService(layer_gateway),
        atlas_export_service=atlas_export_service,
        activity_workflow=DockActivityWorkflowCoordinator(
            sync_controller=sync_controller,
            fetch_result_service=fetch_result_service,
            activity_preview_service=activity_preview_service,
        ),
        atlas_workflow=DockAtlasWorkflowCoordinator(
            atlas_export_use_case=atlas_export_use_case,
        ),
        cache=cache,
    )


def _build_layer_gateway(iface) -> LayerGateway:
    from ..visualization.infrastructure.qgis_layer_gateway import QgisLayerGateway

    return QgisLayerGateway(iface)


def _build_project_hygiene_service() -> ProjectHygienePort:
    from ..visualization.infrastructure.project_hygiene_service import ProjectHygieneService

    return ProjectHygieneService()


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
