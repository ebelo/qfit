from __future__ import annotations

from dataclasses import dataclass

from ...mapbox_config import preset_requires_custom_style


@dataclass(frozen=True)
class LocalFirstControlVisibilityUpdate:
    """Visibility update for a conditional local-first backing control group."""

    key: str
    widget_attrs: tuple[str, ...]
    visible: bool


ADVANCED_FETCH_VISIBILITY_WIDGETS = ("advancedFetchSettingsWidget",)
DETAILED_FETCH_VISIBILITY_WIDGETS = (
    "backfillMissingDetailedRoutesButton",
    "detailedRouteStrategyLabel",
    "detailedRouteStrategyComboBox",
    "detailedRouteStrategyComboBoxContextHelpLabel",
    "detailedRouteStrategyComboBoxHelpField",
    "maxDetailedActivitiesLabel",
    "maxDetailedActivitiesSpinBox",
    "maxDetailedActivitiesSpinBoxContextHelpLabel",
    "maxDetailedActivitiesSpinBoxHelpField",
)
POINT_SAMPLING_VISIBILITY_WIDGETS = (
    "pointSamplingStrideLabel",
    "pointSamplingStrideSpinBox",
    "pointSamplingStrideSpinBoxContextHelpLabel",
    "pointSamplingStrideSpinBoxHelpField",
)
MAPBOX_CUSTOM_STYLE_VISIBILITY_WIDGETS = (
    "mapboxStyleOwnerLabel",
    "mapboxStyleOwnerLineEdit",
    "mapboxStyleIdLabel",
    "mapboxStyleIdLineEdit",
    "mapboxStyleOwnerLineEditContextHelpLabel",
    "mapboxStyleIdLineEditContextHelpLabel",
    "mapboxStyleIdLineEditHelpField",
)


def build_advanced_fetch_visibility_update(
    expanded: bool,
) -> LocalFirstControlVisibilityUpdate:
    """Return the local-first advanced-fetch details visibility update."""

    return LocalFirstControlVisibilityUpdate(
        key="advanced_fetch",
        widget_attrs=ADVANCED_FETCH_VISIBILITY_WIDGETS,
        visible=bool(expanded),
    )


def build_detailed_fetch_visibility_update(
    enabled: bool,
) -> LocalFirstControlVisibilityUpdate:
    """Return the local-first detailed-route controls visibility update."""

    return LocalFirstControlVisibilityUpdate(
        key="detailed_fetch",
        widget_attrs=DETAILED_FETCH_VISIBILITY_WIDGETS,
        visible=bool(enabled),
    )


def build_point_sampling_visibility_update(
    enabled: bool,
) -> LocalFirstControlVisibilityUpdate:
    """Return the local-first point-sampling controls visibility update."""

    return LocalFirstControlVisibilityUpdate(
        key="point_sampling",
        widget_attrs=POINT_SAMPLING_VISIBILITY_WIDGETS,
        visible=bool(enabled),
    )


def build_mapbox_custom_style_visibility_update(
    preset_name: str | None,
) -> LocalFirstControlVisibilityUpdate:
    """Return the local-first custom Mapbox style controls visibility update."""

    return LocalFirstControlVisibilityUpdate(
        key="mapbox_custom_style",
        widget_attrs=MAPBOX_CUSTOM_STYLE_VISIBILITY_WIDGETS,
        visible=preset_requires_custom_style(preset_name),
    )


def apply_local_first_visibility_update(
    dock,
    update: LocalFirstControlVisibilityUpdate,
) -> None:
    """Apply a visibility update to named legacy-backed local-first widgets."""

    set_named_widgets_visible(dock, update.widget_attrs, update.visible)


def update_local_first_advanced_fetch_visibility(dock, expanded: bool) -> None:
    """Apply the advanced-fetch visibility rule to a local-first dock."""

    apply_local_first_visibility_update(
        dock,
        build_advanced_fetch_visibility_update(expanded),
    )


def update_local_first_detailed_fetch_visibility(dock, enabled: bool) -> None:
    """Apply the detailed-fetch visibility rule to a local-first dock."""

    apply_local_first_visibility_update(
        dock,
        build_detailed_fetch_visibility_update(enabled),
    )


def update_local_first_mapbox_custom_style_visibility(
    dock,
    preset_name: str | None,
) -> None:
    """Apply the Mapbox custom-style visibility rule to a local-first dock."""

    apply_local_first_visibility_update(
        dock,
        build_mapbox_custom_style_visibility_update(preset_name),
    )


def update_local_first_point_sampling_visibility(dock, enabled: bool) -> None:
    """Apply the point-sampling visibility rule to a local-first dock."""

    apply_local_first_visibility_update(
        dock,
        build_point_sampling_visibility_update(enabled),
    )


def bind_local_first_conditional_visibility_controls(dock) -> None:
    """Bind local-first conditional-control signals to application visibility rules."""

    _connect_widget_signal(
        dock,
        "detailedStreamsCheckBox",
        "toggled",
        lambda enabled: update_local_first_detailed_fetch_visibility(dock, enabled),
    )
    _connect_widget_signal(
        dock,
        "writeActivityPointsCheckBox",
        "toggled",
        lambda enabled: update_local_first_point_sampling_visibility(dock, enabled),
    )
    _connect_widget_signal(
        dock,
        "advancedFetchGroupBox",
        "toggled",
        lambda expanded: update_local_first_advanced_fetch_visibility(dock, expanded),
    )


def refresh_local_first_conditional_control_visibility(dock) -> None:
    """Refresh all conditional local-first backing controls from live widget state."""

    for update in build_local_first_conditional_visibility_updates(dock):
        apply_local_first_visibility_update(dock, update)


def build_local_first_conditional_visibility_updates(
    dock,
) -> tuple[LocalFirstControlVisibilityUpdate, ...]:
    """Return the current conditional visibility updates for the local-first dock."""

    return (
        build_advanced_fetch_visibility_update(
            _checked(getattr(dock, "advancedFetchGroupBox", None))
        ),
        build_detailed_fetch_visibility_update(
            _checked(getattr(dock, "detailedStreamsCheckBox", None))
        ),
        build_mapbox_custom_style_visibility_update(
            _current_text(getattr(dock, "backgroundPresetComboBox", None))
        ),
        build_point_sampling_visibility_update(
            _checked(getattr(dock, "writeActivityPointsCheckBox", None))
        ),
    )


def set_named_widgets_visible(
    dock,
    widget_attrs: tuple[str, ...],
    visible: bool,
) -> None:
    """Set visibility for every named dock widget that exposes setVisible()."""

    for widget_attr in widget_attrs:
        widget = getattr(dock, widget_attr, None)
        if widget is not None and hasattr(widget, "setVisible"):
            widget.setVisible(visible)


def _connect_widget_signal(dock, widget_attr: str, signal_attr: str, callback) -> None:
    widget = getattr(dock, widget_attr, None)
    signal = getattr(widget, signal_attr, None)
    connect = getattr(signal, "connect", None)
    if callable(connect):
        connect(callback)


def _checked(widget) -> bool:
    is_checked = getattr(widget, "isChecked", None)
    if not callable(is_checked):
        return False
    try:
        return bool(is_checked())
    except RuntimeError:
        return False


def _current_text(widget) -> str | None:
    current_text = getattr(widget, "currentText", None)
    if not callable(current_text):
        return None
    try:
        text = current_text()
    except RuntimeError:
        return None
    return text if isinstance(text, str) else None


__all__ = [
    "ADVANCED_FETCH_VISIBILITY_WIDGETS",
    "DETAILED_FETCH_VISIBILITY_WIDGETS",
    "MAPBOX_CUSTOM_STYLE_VISIBILITY_WIDGETS",
    "POINT_SAMPLING_VISIBILITY_WIDGETS",
    "LocalFirstControlVisibilityUpdate",
    "apply_local_first_visibility_update",
    "bind_local_first_conditional_visibility_controls",
    "build_advanced_fetch_visibility_update",
    "build_detailed_fetch_visibility_update",
    "build_local_first_conditional_visibility_updates",
    "build_mapbox_custom_style_visibility_update",
    "build_point_sampling_visibility_update",
    "refresh_local_first_conditional_control_visibility",
    "set_named_widgets_visible",
    "update_local_first_advanced_fetch_visibility",
    "update_local_first_detailed_fetch_visibility",
    "update_local_first_mapbox_custom_style_visibility",
    "update_local_first_point_sampling_visibility",
]
