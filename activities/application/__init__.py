"""Activity workflow services and task helpers.

This package keeps its public re-exports lazy so pure-Python consumers can
import lightweight application models without pulling in QGIS task modules.
"""

from importlib import import_module

_ACTIVITY_PREVIEW_MODULE = ".activity_preview"

__all__ = [
    "ActivityStore",
    "ActivityPreviewRequest",
    "ActivityPreviewResult",
    "ActivityPreviewService",
    "ActivitySelectionState",
    "ActivityTypeOptionsResult",
    "BuildStravaProviderRequest",
    "BuildRouteSyncTaskRequest",
    "ClearDatabaseWorkflow",
    "FetchActivitiesRequest",
    "FetchResult",
    "FetchResultService",
    "FetchTask",
    "RouteSyncTask",
    "LoadDatabaseRequest",
    "LoadDatasetRequest",
    "LoadDatasetResult",
    "LoadDatasetWorkflow",
    "LoadExistingRequest",
    "LoadResult",
    "LoadWorkflowError",
    "LoadWorkflowService",
    "StoreActivitiesRequest",
    "StoreActivitiesResult",
    "StoreActivitiesWorkflow",
    "SyncController",
    "build_activity_preview",
    "build_activity_preview_filtered_activities",
    "build_filtered_activity_preview_activities",
    "build_activity_preview_query",
    "build_activity_preview_request",
    "build_activity_preview_selection_state",
    "build_activity_query",
    "build_activity_selection_state",
    "build_activity_type_options",
    "build_activity_type_options_from_activities",
    "build_activity_type_options_from_records",
    "build_route_sync_task",
]

_ACTIVITY_TYPE_OPTIONS_MODULE = ".activity_type_options"

_EXPORTS = {
    "ActivityStore": (".activity_storage", "ActivityStore"),
    "ActivityPreviewRequest": (_ACTIVITY_PREVIEW_MODULE, "ActivityPreviewRequest"),
    "ActivityPreviewResult": (_ACTIVITY_PREVIEW_MODULE, "ActivityPreviewResult"),
    "ActivityPreviewService": (".activity_preview_service", "ActivityPreviewService"),
    "ActivitySelectionState": (".activity_selection_state", "ActivitySelectionState"),
    "ActivityTypeOptionsResult": (_ACTIVITY_TYPE_OPTIONS_MODULE, "ActivityTypeOptionsResult"),
    "BuildStravaProviderRequest": (".sync_controller", "BuildStravaProviderRequest"),
    "BuildRouteSyncTaskRequest": (".sync_controller", "BuildRouteSyncTaskRequest"),
    "ClearDatabaseWorkflow": (".load_workflow", "ClearDatabaseWorkflow"),
    "FetchActivitiesRequest": (".fetch_result_service", "FetchActivitiesRequest"),
    "FetchResult": (".fetch_result_service", "FetchResult"),
    "FetchResultService": (".fetch_result_service", "FetchResultService"),
    "FetchTask": (".fetch_task", "FetchTask"),
    "RouteSyncTask": (".route_sync_task", "RouteSyncTask"),
    "LoadDatabaseRequest": (".load_workflow", "LoadDatabaseRequest"),
    "LoadDatasetRequest": (".load_workflow", "LoadDatasetRequest"),
    "LoadDatasetResult": (".load_workflow", "LoadDatasetResult"),
    "LoadDatasetWorkflow": (".load_workflow", "LoadDatasetWorkflow"),
    "LoadExistingRequest": (".load_workflow", "LoadExistingRequest"),
    "LoadResult": (".load_workflow", "LoadResult"),
    "LoadWorkflowError": (".load_workflow", "LoadWorkflowError"),
    "LoadWorkflowService": (".load_workflow", "LoadWorkflowService"),
    "StoreActivitiesRequest": (".load_workflow", "StoreActivitiesRequest"),
    "StoreActivitiesResult": (".load_workflow", "StoreActivitiesResult"),
    "StoreActivitiesWorkflow": (".load_workflow", "StoreActivitiesWorkflow"),
    "SyncController": (".sync_controller", "SyncController"),
    "build_activity_preview": (_ACTIVITY_PREVIEW_MODULE, "build_activity_preview"),
    "build_activity_preview_filtered_activities": (_ACTIVITY_PREVIEW_MODULE, "build_activity_preview_filtered_activities"),
    "build_filtered_activity_preview_activities": (_ACTIVITY_PREVIEW_MODULE, "build_filtered_activity_preview_activities"),
    "build_activity_preview_query": (_ACTIVITY_PREVIEW_MODULE, "build_activity_preview_query"),
    "build_activity_preview_request": (_ACTIVITY_PREVIEW_MODULE, "build_activity_preview_request"),
    "build_activity_preview_selection_state": (_ACTIVITY_PREVIEW_MODULE, "build_activity_preview_selection_state"),
    "build_activity_query": (_ACTIVITY_PREVIEW_MODULE, "build_activity_query"),
    "build_activity_selection_state": (_ACTIVITY_PREVIEW_MODULE, "build_activity_selection_state"),
    "build_activity_type_options": (_ACTIVITY_TYPE_OPTIONS_MODULE, "build_activity_type_options"),
    "build_activity_type_options_from_activities": (_ACTIVITY_TYPE_OPTIONS_MODULE, "build_activity_type_options_from_activities"),
    "build_activity_type_options_from_records": (_ACTIVITY_TYPE_OPTIONS_MODULE, "build_activity_type_options_from_records"),
    "build_route_sync_task": (".route_sync_task", "build_route_sync_task"),
}


def __getattr__(name):
    if name not in _EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    module_name, attr_name = _EXPORTS[name]
    module = import_module(module_name, __name__)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value
