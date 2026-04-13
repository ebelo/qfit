from .analysis_result_builder import (
    build_activity_heatmap_result,
    build_empty_analysis_result,
)


def run_activity_heatmap_analysis(activities_layer=None, points_layer=None):
    if activities_layer is None and points_layer is None:
        return build_empty_analysis_result()

    layer, sample_count = _build_activity_heatmap_layer(
        activities_layer=activities_layer,
        points_layer=points_layer,
    )
    return build_activity_heatmap_result(layer, sample_count)


def _build_activity_heatmap_layer(activities_layer=None, points_layer=None):
    from ..infrastructure.activity_heatmap_layer import build_activity_heatmap_layer

    return build_activity_heatmap_layer(
        activities_layer=activities_layer,
        points_layer=points_layer,
    )
