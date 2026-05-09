from __future__ import annotations

from ...activities.domain.activity_query import (
    DEFAULT_SORT_LABEL,
    DETAILED_ROUTE_FILTER_ANY,
    DETAILED_ROUTE_FILTER_MISSING,
    DETAILED_ROUTE_FILTER_PRESENT,
    SORT_OPTIONS,
)
from ...activities.application import build_activity_preview_request
from ...detailed_route_strategy import detailed_route_strategy_labels


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
        sort_label=dock.previewSortComboBox.currentText() or DEFAULT_SORT_LABEL,
    )


def configure_local_first_activity_preview_options(dock) -> None:
    """Prepare activity preview backing controls for the Data page."""

    configure_detailed_route_filter_options(dock)
    configure_detailed_route_strategy_options(dock)
    configure_preview_sort_options(dock)


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


def configure_detailed_route_strategy_options(dock) -> None:
    """Populate the detailed-route fetch strategy backing combo."""

    combo = getattr(dock, "detailedRouteStrategyComboBox", None)
    if combo is None:
        return
    combo.clear()
    for label in detailed_route_strategy_labels():
        combo.addItem(label)


def configure_preview_sort_options(dock) -> None:
    """Populate the activity preview sort backing combo."""

    combo = getattr(dock, "previewSortComboBox", None)
    if combo is None:
        return
    combo.clear()
    for label in SORT_OPTIONS:
        combo.addItem(label)


__all__ = [
    "build_current_activity_preview_request",
    "configure_detailed_route_filter_options",
    "configure_detailed_route_strategy_options",
    "configure_local_first_activity_preview_options",
    "configure_preview_sort_options",
]
