def build_frequent_start_points_empty_status() -> str:
    return "No frequent starting points matched the current filters"


def build_frequent_start_points_success_status(cluster_count: int) -> str:
    return "Showing top {count} frequent starting-point clusters".format(
        count=cluster_count
    )


def build_activity_heatmap_empty_status() -> str:
    return "No activity heatmap data matched the current filters"


def build_activity_heatmap_success_status(sample_count: int) -> str:
    return "Showing static red activity heatmap from {count} activities".format(
        count=sample_count
    )
