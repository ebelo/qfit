"""Activity workflow services and task helpers.

This package keeps its public re-exports lazy so pure-Python consumers can
import lightweight application models without pulling in QGIS task modules.
"""

from importlib import import_module

__all__ = [
    "ActivitySelectionState",
    "BuildStravaProviderRequest",
    "FetchActivitiesRequest",
    "FetchResult",
    "FetchResultService",
    "FetchTask",
    "LoadDatabaseRequest",
    "LoadDatasetRequest",
    "LoadExistingRequest",
    "LoadResult",
    "LoadWorkflowError",
    "LoadWorkflowService",
    "StoreActivitiesRequest",
    "SyncController",
]

_EXPORTS = {
    "ActivitySelectionState": (".activity_selection_state", "ActivitySelectionState"),
    "BuildStravaProviderRequest": (".sync_controller", "BuildStravaProviderRequest"),
    "FetchActivitiesRequest": (".fetch_result_service", "FetchActivitiesRequest"),
    "FetchResult": (".fetch_result_service", "FetchResult"),
    "FetchResultService": (".fetch_result_service", "FetchResultService"),
    "FetchTask": (".fetch_task", "FetchTask"),
    "LoadDatabaseRequest": (".load_workflow", "LoadDatabaseRequest"),
    "LoadDatasetRequest": (".load_workflow", "LoadDatasetRequest"),
    "LoadExistingRequest": (".load_workflow", "LoadExistingRequest"),
    "LoadResult": (".load_workflow", "LoadResult"),
    "LoadWorkflowError": (".load_workflow", "LoadWorkflowError"),
    "LoadWorkflowService": (".load_workflow", "LoadWorkflowService"),
    "StoreActivitiesRequest": (".load_workflow", "StoreActivitiesRequest"),
    "SyncController": (".sync_controller", "SyncController"),
}


def __getattr__(name):
    if name not in _EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    module_name, attr_name = _EXPORTS[name]
    module = import_module(module_name, __name__)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value
