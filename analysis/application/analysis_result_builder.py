from .analysis_models import RunAnalysisResult
from .analysis_status_messages import (
    build_frequent_start_points_empty_status,
    build_frequent_start_points_success_status,
)


def build_frequent_start_points_result(layer, clusters) -> RunAnalysisResult:
    if layer is None or not clusters:
        return RunAnalysisResult(status=build_frequent_start_points_empty_status())

    return RunAnalysisResult(
        status=build_frequent_start_points_success_status(len(clusters)),
        layer=layer,
    )
