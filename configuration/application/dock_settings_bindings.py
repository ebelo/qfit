from __future__ import annotations

from .ui_settings_binding import UIFieldBinding
from ...activities.domain.activity_query import DEFAULT_SORT_LABEL, DETAILED_ROUTE_FILTER_ANY
from ...detailed_route_strategy import DEFAULT_DETAILED_ROUTE_STRATEGY
from ...mapbox_config import DEFAULT_BACKGROUND_PRESET, TILE_MODE_RASTER
from ...providers.infrastructure.strava_provider import StravaProvider


DEFAULT_STYLE_PRESET = "By activity type"
DEFAULT_DEPENDENT_DATE_PRESET = "None"


def build_dock_settings_bindings(dock) -> list[UIFieldBinding]:
    """Build the main dock widget settings binding table.

    The dock remains responsible for its concrete UI widgets and coercion
    helpers, while configuration-owned code owns the settings key mapping and
    defaults.
    """

    return [
        UIFieldBinding("client_id", "", lambda: dock.clientIdLineEdit.text().strip(), dock.clientIdLineEdit.setText),
        UIFieldBinding("client_secret", "", lambda: dock.clientSecretLineEdit.text().strip(), dock.clientSecretLineEdit.setText),
        UIFieldBinding(
            "redirect_uri",
            StravaProvider.DEFAULT_REDIRECT_URI,
            lambda: dock.redirectUriLineEdit.text().strip(),
            dock.redirectUriLineEdit.setText,
        ),
        UIFieldBinding("refresh_token", "", lambda: dock.refreshTokenLineEdit.text().strip(), dock.refreshTokenLineEdit.setText),
        UIFieldBinding("output_path", dock._default_output_path(), lambda: dock.outputPathLineEdit.text().strip(), dock.outputPathLineEdit.setText),
        UIFieldBinding("per_page", 200, lambda: dock.perPageSpinBox.value(), lambda value: dock._set_int_value(dock.perPageSpinBox, value, 200)),
        UIFieldBinding("max_pages", 0, lambda: dock.maxPagesSpinBox.value(), lambda value: dock._set_int_value(dock.maxPagesSpinBox, value, 0)),
        UIFieldBinding(
            "use_detailed_streams",
            False,
            lambda: dock.detailedStreamsCheckBox.isChecked(),
            lambda value: dock._set_bool_value(dock.detailedStreamsCheckBox, value, False),
        ),
        UIFieldBinding(
            "max_detailed_activities",
            25,
            lambda: dock.maxDetailedActivitiesSpinBox.value(),
            lambda value: dock._set_int_value(dock.maxDetailedActivitiesSpinBox, value, 25),
        ),
        UIFieldBinding(
            "detailed_route_strategy",
            DEFAULT_DETAILED_ROUTE_STRATEGY,
            lambda: dock.detailedRouteStrategyComboBox.currentText(),
            lambda value: dock._set_combo_value(
                dock.detailedRouteStrategyComboBox,
                value,
                DEFAULT_DETAILED_ROUTE_STRATEGY,
            ),
        ),
        UIFieldBinding(
            "write_activity_points",
            True,
            lambda: dock.writeActivityPointsCheckBox.isChecked(),
            lambda value: dock._set_bool_value(dock.writeActivityPointsCheckBox, value, True),
        ),
        UIFieldBinding(
            "point_sampling_stride",
            5,
            lambda: dock.pointSamplingStrideSpinBox.value(),
            lambda value: dock._set_int_value(dock.pointSamplingStrideSpinBox, value, 5),
        ),
        UIFieldBinding(
            "activity_search_text",
            "",
            lambda: dock.activitySearchLineEdit.text().strip(),
            dock.activitySearchLineEdit.setText,
        ),
        UIFieldBinding(
            "dependent_date_preset",
            DEFAULT_DEPENDENT_DATE_PRESET,
            lambda: dock.dependentDatePresetComboBox.currentText(),
            lambda value: dock._set_combo_value(
                dock.dependentDatePresetComboBox,
                value,
                DEFAULT_DEPENDENT_DATE_PRESET,
            ),
        ),
        UIFieldBinding(
            "dependent_birth_date",
            "",
            lambda: dock.dependentBirthDateLineEdit.text().strip(),
            dock.dependentBirthDateLineEdit.setText,
        ),
        UIFieldBinding(
            "max_distance_km",
            0.0,
            lambda: dock.maxDistanceSpinBox.value(),
            lambda value: dock._set_float_value(dock.maxDistanceSpinBox, value, 0.0),
        ),
        UIFieldBinding(
            "detailed_route_filter",
            DETAILED_ROUTE_FILTER_ANY,
            lambda: dock.detailedRouteStatusComboBox.currentData(),
            lambda value: dock._set_combo_data_value(
                dock.detailedRouteStatusComboBox,
                value,
                DETAILED_ROUTE_FILTER_ANY,
            ),
        ),
        UIFieldBinding(
            "use_background_map",
            False,
            lambda: dock.backgroundMapCheckBox.isChecked(),
            lambda value: dock._set_bool_value(dock.backgroundMapCheckBox, value, False),
        ),
        UIFieldBinding(
            "mapbox_style_owner",
            "mapbox",
            lambda: dock.mapboxStyleOwnerLineEdit.text().strip(),
            dock.mapboxStyleOwnerLineEdit.setText,
        ),
        UIFieldBinding(
            "mapbox_style_id",
            "",
            lambda: dock.mapboxStyleIdLineEdit.text().strip(),
            dock.mapboxStyleIdLineEdit.setText,
        ),
        UIFieldBinding(
            "atlas_title",
            "qfit Activity Atlas",
            lambda: dock.atlasTitleLineEdit.text().strip(),
            dock.atlasTitleLineEdit.setText,
        ),
        UIFieldBinding(
            "atlas_subtitle",
            "",
            lambda: dock.atlasSubtitleLineEdit.text().strip(),
            dock.atlasSubtitleLineEdit.setText,
        ),
        UIFieldBinding(
            "atlas_pdf_path",
            dock._default_atlas_pdf_path(),
            lambda: dock.atlasPdfPathLineEdit.text().strip(),
            dock.atlasPdfPathLineEdit.setText,
        ),
        UIFieldBinding(
            "analysis_mode",
            "None",
            lambda: dock.analysisModeComboBox.currentText(),
            lambda value: dock._set_combo_value(dock.analysisModeComboBox, value, "None"),
        ),
        UIFieldBinding(
            "background_preset",
            DEFAULT_BACKGROUND_PRESET,
            lambda: dock.backgroundPresetComboBox.currentText(),
            lambda value: dock._set_combo_value(dock.backgroundPresetComboBox, value, DEFAULT_BACKGROUND_PRESET),
        ),
        UIFieldBinding(
            "tile_mode",
            TILE_MODE_RASTER,
            lambda: dock.tileModeComboBox.currentText(),
            lambda value: dock._set_combo_value(dock.tileModeComboBox, value, TILE_MODE_RASTER),
        ),
        UIFieldBinding(
            "preview_sort",
            DEFAULT_SORT_LABEL,
            lambda: dock.previewSortComboBox.currentText(),
            lambda value: dock._set_combo_value(dock.previewSortComboBox, value, DEFAULT_SORT_LABEL),
        ),
        UIFieldBinding(
            "style_preset",
            DEFAULT_STYLE_PRESET,
            lambda: dock.stylePresetComboBox.currentText(),
            lambda value: dock._set_combo_value(dock.stylePresetComboBox, value, DEFAULT_STYLE_PRESET),
        ),
    ]
