from __future__ import annotations

from .ui_settings_binding import UIFieldBinding
from ...activities.domain.activity_query import DETAILED_ROUTE_FILTER_ANY
from ...mapbox_config import DEFAULT_BACKGROUND_PRESET, TILE_MODE_RASTER


DEFAULT_STYLE_PRESET = "By activity type"


def build_dock_settings_bindings(dock) -> list[UIFieldBinding]:
    """Build the main dock widget settings binding table.

    The dock remains responsible for its concrete UI widgets and coercion
    helpers, while configuration-owned code owns the settings key mapping and
    defaults.
    """

    return [
        UIFieldBinding("output_path", dock._default_output_path(), lambda: dock.outputPathLineEdit.text().strip(), dock.outputPathLineEdit.setText),
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
            "style_preset",
            DEFAULT_STYLE_PRESET,
            lambda: dock.stylePresetComboBox.currentText(),
            lambda value: dock._set_combo_value(dock.stylePresetComboBox, value, DEFAULT_STYLE_PRESET),
        ),
    ]
