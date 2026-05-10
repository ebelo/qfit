from .activity_heatmap_analysis import run_activity_heatmap_analysis
from .analysis_result_builder import build_empty_analysis_result
from .frequent_start_points_analysis import run_frequent_start_points_analysis
from .slope_grade_analysis import SLOPE_GRADE_MODE, run_slope_grade_analysis

FREQUENT_STARTING_POINTS_MODE = "Most frequent starting points"
HEATMAP_MODE = "Heatmap"


def dispatch_analysis_request(request):
    if request.analysis_mode == FREQUENT_STARTING_POINTS_MODE:
        return run_frequent_start_points_analysis(request.starts_layer)

    if request.analysis_mode == HEATMAP_MODE:
        return run_activity_heatmap_analysis(
            activities_layer=request.activities_layer,
            points_layer=request.points_layer,
        )

    if request.analysis_mode == SLOPE_GRADE_MODE:
        return run_slope_grade_analysis(request)

    return build_empty_analysis_result()
