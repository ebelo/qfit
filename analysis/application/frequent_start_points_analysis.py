from .analysis_result_builder import (
    build_empty_analysis_result,
    build_frequent_start_points_result,
)


def run_frequent_start_points_analysis(starts_layer):
    if starts_layer is None:
        return build_empty_analysis_result()

    layer, clusters = _build_frequent_start_points_layer(starts_layer)
    return build_frequent_start_points_result(layer, clusters)


def _build_frequent_start_points_layer(starts_layer):
    from ..infrastructure.frequent_start_points_layer import (
        build_frequent_start_points_layer,
    )

    return build_frequent_start_points_layer(starts_layer)
