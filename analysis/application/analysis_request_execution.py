from .analysis_execution_dispatch import dispatch_analysis_request


def execute_analysis_request(*, build_request, request=None, legacy_kwargs=None):
    if request is None:
        request = build_request(**(legacy_kwargs or {}))

    return dispatch_analysis_request(request)
