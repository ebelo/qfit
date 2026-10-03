from __future__ import annotations

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
        activity_types=(
            tuple(dock.activityTypeComboBox.selectedTypes())
            if hasattr(dock.activityTypeComboBox, "selectedTypes") else None
        ),
    )


def configure_local_first_activity_preview_options(dock) -> None:
    """Prepare activity preview backing controls for the Data page."""

    if hasattr(dock, "activityTypeComboBox"):
        from ..widgets.activity_type_selector import install_activity_type_selector
        install_activity_type_selector(dock)


__all__ = [
    "build_current_activity_preview_request",
    "configure_local_first_activity_preview_options",
]
