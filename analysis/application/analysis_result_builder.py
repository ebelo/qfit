from .analysis_models import RunAnalysisResult
from .analysis_status_messages import (
    build_activity_heatmap_empty_status,
    build_activity_heatmap_success_status,
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


def build_activity_heatmap_result(layer, sample_count: int) -> RunAnalysisResult:
    if layer is None or sample_count <= 0:
        return RunAnalysisResult(status=build_activity_heatmap_empty_status())

    return RunAnalysisResult(
        status=build_activity_heatmap_success_status(sample_count),
        layer=layer,
    )
