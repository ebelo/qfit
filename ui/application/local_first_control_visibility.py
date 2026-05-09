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
        visible=expanded,
    )


def build_detailed_fetch_visibility_update(
    enabled: bool,
) -> LocalFirstControlVisibilityUpdate:
    """Return the local-first detailed-route controls visibility update."""

    return LocalFirstControlVisibilityUpdate(
        key="detailed_fetch",
        widget_attrs=DETAILED_FETCH_VISIBILITY_WIDGETS,
        visible=enabled,
    )


def build_point_sampling_visibility_update(
    enabled: bool,
) -> LocalFirstControlVisibilityUpdate:
    """Return the local-first point-sampling controls visibility update."""

    return LocalFirstControlVisibilityUpdate(
        key="point_sampling",
        widget_attrs=POINT_SAMPLING_VISIBILITY_WIDGETS,
        visible=enabled,
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


__all__ = [
    "ADVANCED_FETCH_VISIBILITY_WIDGETS",
    "DETAILED_FETCH_VISIBILITY_WIDGETS",
    "MAPBOX_CUSTOM_STYLE_VISIBILITY_WIDGETS",
    "POINT_SAMPLING_VISIBILITY_WIDGETS",
    "LocalFirstControlVisibilityUpdate",
    "build_advanced_fetch_visibility_update",
    "build_detailed_fetch_visibility_update",
    "build_mapbox_custom_style_visibility_update",
    "build_point_sampling_visibility_update",
]
