from ...activities.domain.activity_query import ActivityQuery, build_subset_string


class LayerFilterService:
    """Applies qfit activity subset filters to loaded output layers."""

    def apply_filters(
        self,
        layer,
        activity_type=None,
        date_from=None,
        date_to=None,
        min_distance_km=None,
        max_distance_km=None,
        search_text=None,
        detailed_only=False,
        detailed_route_filter=None,
    ):
        if layer is None or not layer.isValid():
            return

        query = ActivityQuery(
            activity_type=activity_type,
            date_from=date_from,
            date_to=date_to,
            min_distance_km=min_distance_km,
            max_distance_km=max_distance_km,
            search_text=search_text,
            detailed_only=detailed_only,
            detailed_route_filter=detailed_route_filter,
        )
        layer.setSubsetString(build_subset_string(query))
        layer.triggerRepaint()
