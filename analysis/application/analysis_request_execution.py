from .analysis_execution_dispatch import dispatch_analysis_request


def run_analysis_workflow(*, build_request, request=None, legacy_kwargs=None):
    if request is None:
        request = build_request(**(legacy_kwargs or {}))

    return dispatch_analysis_request(request)
