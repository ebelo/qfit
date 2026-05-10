from __future__ import annotations

from ...activities.domain.activity_query import (
    DETAILED_ROUTE_FILTER_ANY,
    DETAILED_ROUTE_FILTER_MISSING,
    DETAILED_ROUTE_FILTER_PRESENT,
)
from ...activities.application import build_activity_preview_request


def build_current_activity_preview_request(dock):
    """Build the activity preview request from local-first backing controls."""

    date_from = dock.dateFromEdit.date()
    date_to = dock.dateToEdit.date()
    return build_activity_preview_request(
        activities=dock.runtime_state.activities,
        activity_type=dock.activityTypeComboBox.currentText() or "All",
        date_from=(
            date_from.toString("yyyy-MM-dd")
            if date_from.isValid()
            else None
        ),
        date_to=(
            date_to.toString("yyyy-MM-dd")
            if date_to.isValid()
            else None
        ),
        min_distance_km=dock.minDistanceSpinBox.value(),
        max_distance_km=dock.maxDistanceSpinBox.value(),
        search_text=dock.activitySearchLineEdit.text().strip(),
        detailed_route_filter=dock.detailedRouteStatusComboBox.currentData(),
    )


def configure_local_first_activity_preview_options(dock) -> None:
    """Prepare activity preview backing controls for the Data page."""

    configure_detailed_route_filter_options(dock)


def configure_detailed_route_filter_options(dock) -> None:
    """Populate the detailed-route availability filter backing combo."""

    legacy_checkbox = getattr(dock, "detailedOnlyCheckBox", None)
    combo = getattr(dock, "detailedRouteStatusComboBox", None)
    if combo is None:
        from qgis.PyQt.QtWidgets import QComboBox

        combo = QComboBox(legacy_checkbox.parentWidget())
        combo.setObjectName("detailedRouteStatusComboBox")
        layout = legacy_checkbox.parentWidget().layout()
        if layout is not None and hasattr(layout, "replaceWidget"):
            layout.replaceWidget(legacy_checkbox, combo)
        legacy_checkbox.hide()
        dock.detailedRouteStatusComboBox = combo
    combo.clear()
    combo.addItem("Any routes", DETAILED_ROUTE_FILTER_ANY)
    combo.addItem("Detailed routes only", DETAILED_ROUTE_FILTER_PRESENT)
    combo.addItem("Missing detailed routes", DETAILED_ROUTE_FILTER_MISSING)
    combo.setToolTip("Filter activities by detailed-route availability")


__all__ = [
    "build_current_activity_preview_request",
    "configure_detailed_route_filter_options",
    "configure_local_first_activity_preview_options",
]
