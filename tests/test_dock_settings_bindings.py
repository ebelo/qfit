import unittest

from tests import _path  # noqa: F401

from qfit.configuration.infrastructure.credential_store import InMemoryCredentialStore
from qfit.settings_service import SettingsService
from qfit.activities.domain.activity_query import DEFAULT_SORT_LABEL, DETAILED_ROUTE_FILTER_ANY
from qfit.atlas.layout_metrics import BUILTIN_ATLAS_MAP_TARGET_ASPECT_RATIO
from qfit.configuration.application.dock_settings_bindings import build_dock_settings_bindings
from qfit.configuration.application.ui_settings_binding import load_bindings, save_bindings
from qfit.detailed_route_strategy import DEFAULT_DETAILED_ROUTE_STRATEGY
from qfit.mapbox_config import DEFAULT_BACKGROUND_PRESET, TILE_MODE_RASTER
from qfit.providers.infrastructure.strava_provider import StravaProvider


class FakeQSettings:
    def __init__(self, data=None):
        self._data = data or {}

    def value(self, key, default=None):
        return self._data.get(key, default)

    def setValue(self, key, value):
        self._data[key] = value

    def remove(self, key):
        self._data.pop(key, None)


class TextWidget:
    def __init__(self, value=""):
        self._value = value

    def text(self):
        return self._value

    def setText(self, value):
        self._value = value


class SpinWidget:
    def __init__(self, value=0):
        self._value = value

    def value(self):
        return self._value

    def setValue(self, value):
        self._value = value


class CheckWidget:
    def __init__(self, checked=False):
        self._checked = checked

    def isChecked(self):
        return self._checked

    def setChecked(self, checked):
        self._checked = checked


class ComboWidget:
    def __init__(self, items, current_index=0, data=None):
        self._items = list(items)
        self._data = list(data) if data is not None else list(items)
        self._current_index = current_index

    def currentText(self):
        return self._items[self._current_index]

    def currentData(self):
        return self._data[self._current_index]

    def findText(self, text):
        try:
            return self._items.index(text)
        except ValueError:
            return -1

    def findData(self, value):
        try:
            return self._data.index(value)
        except ValueError:
            return -1

    def setCurrentIndex(self, index):
        self._current_index = index


def _settings(data=None):
    return SettingsService(
        qsettings=FakeQSettings(data or {}),
        credential_store=InMemoryCredentialStore(),
    )


class FakeDock:
    def __init__(self):
        self.clientIdLineEdit = TextWidget()
        self.clientSecretLineEdit = TextWidget()
        self.redirectUriLineEdit = TextWidget()
        self.refreshTokenLineEdit = TextWidget()
        self.outputPathLineEdit = TextWidget()
        self.perPageSpinBox = SpinWidget(200)
        self.maxPagesSpinBox = SpinWidget(0)
        self.detailedStreamsCheckBox = CheckWidget(False)
        self.maxDetailedActivitiesSpinBox = SpinWidget(25)
        self.detailedRouteStrategyComboBox = ComboWidget(
            [DEFAULT_DETAILED_ROUTE_STRATEGY, "Only missing detailed routes"],
        )
        self.writeActivityPointsCheckBox = CheckWidget(True)
        self.pointSamplingStrideSpinBox = SpinWidget(5)
        self.activitySearchLineEdit = TextWidget()
        self.maxDistanceSpinBox = SpinWidget(0.0)
        self.detailedRouteStatusComboBox = ComboWidget(
            ["Any routes", "Detailed routes only", "Missing detailed routes"],
            data=[DETAILED_ROUTE_FILTER_ANY, "present", "missing"],
        )
        self.backgroundMapCheckBox = CheckWidget(False)
        self.mapboxStyleOwnerLineEdit = TextWidget()
        self.mapboxStyleIdLineEdit = TextWidget()
        self.atlasMarginPercentSpinBox = SpinWidget(8.0)
        self.atlasMinExtentSpinBox = SpinWidget(0.01)
        self.atlasTargetAspectRatioSpinBox = SpinWidget(BUILTIN_ATLAS_MAP_TARGET_ASPECT_RATIO)
        self.atlasPdfPathLineEdit = TextWidget()
        self.analysisModeComboBox = ComboWidget(["None", "Most frequent starting points"])
        self.backgroundPresetComboBox = ComboWidget([DEFAULT_BACKGROUND_PRESET, "Custom"])
        self.tileModeComboBox = ComboWidget([TILE_MODE_RASTER, "Vector"])
        self.previewSortComboBox = ComboWidget([DEFAULT_SORT_LABEL, "Newest first"])
        self.stylePresetComboBox = ComboWidget(["By activity type", "Heatmap"])

    def _default_output_path(self):
        return "/tmp/qfit_activities.gpkg"

    def _default_atlas_pdf_path(self):
        return "/tmp/qfit_atlas.pdf"

    @staticmethod
    def _set_combo_value(combo_box, value, default_text):
        selected = default_text if value in (None, "") else str(value)
        index = combo_box.findText(selected)
        if index < 0:
            index = combo_box.findText(default_text)
        combo_box.setCurrentIndex(max(index, 0))

    @staticmethod
    def _set_bool_value(check_box, value, default):
        if isinstance(value, str):
            check_box.setChecked(value.lower() in ("1", "true", "yes", "on"))
            return
        if value is None:
            check_box.setChecked(default)
            return
        check_box.setChecked(bool(value))

    @staticmethod
    def _set_int_value(spin_box, value, default):
        try:
            spin_box.setValue(int(value))
        except (TypeError, ValueError):
            spin_box.setValue(int(default))

    @staticmethod
    def _set_combo_data_value(combo_box, value, default):
        target = value if value not in (None, "") else default
        index = combo_box.findData(target)
        if index < 0:
            index = combo_box.findData(default)
        if index < 0:
            index = 0
        combo_box.setCurrentIndex(index)

    @staticmethod
    def _set_float_value(spin_box, value, default):
        try:
            spin_box.setValue(float(value))
        except (TypeError, ValueError):
            spin_box.setValue(float(default))

    def _set_atlas_target_aspect_ratio_value(self, value):
        try:
            aspect_ratio = float(value)
        except (TypeError, ValueError):
            aspect_ratio = BUILTIN_ATLAS_MAP_TARGET_ASPECT_RATIO
        if aspect_ratio <= 0:
            aspect_ratio = BUILTIN_ATLAS_MAP_TARGET_ASPECT_RATIO
        self.atlasTargetAspectRatioSpinBox.setValue(aspect_ratio)


class DockSettingsBindingsTests(unittest.TestCase):
    EXPECTED_KEYS = {
        "client_id",
        "client_secret",
        "redirect_uri",
        "refresh_token",
        "output_path",
        "per_page",
        "max_pages",
        "use_detailed_streams",
        "max_detailed_activities",
        "detailed_route_strategy",
        "write_activity_points",
        "point_sampling_stride",
        "activity_search_text",
        "max_distance_km",
        "detailed_route_filter",
        "use_background_map",
        "mapbox_style_owner",
        "mapbox_style_id",
        "atlas_margin_percent",
        "atlas_min_extent_degrees",
        "atlas_target_aspect_ratio",
        "atlas_pdf_path",
        "analysis_mode",
        "background_preset",
        "tile_mode",
        "preview_sort",
        "style_preset",
    }

    def test_binding_table_covers_expected_keys(self):
        bindings = build_dock_settings_bindings(FakeDock())
        self.assertEqual({binding.key for binding in bindings}, self.EXPECTED_KEYS)

    def test_load_applies_stored_values_and_defaults(self):
        dock = FakeDock()
        settings = _settings(
            {
                "qfit/client_id": "client-123",
                "qfit/redirect_uri": "http://example.test/callback",
                "qfit/per_page": "75",
                "qfit/use_detailed_streams": "true",
                "qfit/detailed_route_filter": "missing",
                "qfit/use_background_map": True,
                "qfit/atlas_target_aspect_ratio": "2.5",
                "qfit/preview_sort": "Newest first",
                "qfit/style_preset": "Heatmap",
            }
        )

        load_bindings(build_dock_settings_bindings(dock), settings)

        self.assertEqual(dock.clientIdLineEdit.text(), "client-123")
        self.assertEqual(dock.redirectUriLineEdit.text(), "http://example.test/callback")
        self.assertEqual(dock.outputPathLineEdit.text(), dock._default_output_path())
        self.assertEqual(dock.perPageSpinBox.value(), 75)
        self.assertTrue(dock.detailedStreamsCheckBox.isChecked())
        self.assertEqual(dock.detailedRouteStatusComboBox.currentData(), "missing")
        self.assertTrue(dock.backgroundMapCheckBox.isChecked())
        self.assertEqual(dock.atlasTargetAspectRatioSpinBox.value(), 2.5)
        self.assertEqual(dock.previewSortComboBox.currentText(), "Newest first")
        self.assertEqual(dock.stylePresetComboBox.currentText(), "Heatmap")
        self.assertEqual(dock.analysisModeComboBox.currentText(), "None")

    def test_save_roundtrip_preserves_values(self):
        dock = FakeDock()
        dock.clientIdLineEdit.setText("  abc  ")
        dock.clientSecretLineEdit.setText("secret")
        dock.redirectUriLineEdit.setText(StravaProvider.DEFAULT_REDIRECT_URI)
        dock.outputPathLineEdit.setText("/tmp/out.gpkg")
        dock.perPageSpinBox.setValue(123)
        dock.detailedStreamsCheckBox.setChecked(True)
        dock.maxDetailedActivitiesSpinBox.setValue(11)
        dock.detailedRouteStrategyComboBox.setCurrentIndex(1)
        dock.writeActivityPointsCheckBox.setChecked(False)
        dock.pointSamplingStrideSpinBox.setValue(9)
        dock.activitySearchLineEdit.setText(" commute ")
        dock.maxDistanceSpinBox.setValue(42.5)
        dock.detailedRouteStatusComboBox.setCurrentIndex(2)
        dock.backgroundMapCheckBox.setChecked(True)
        dock.mapboxStyleOwnerLineEdit.setText("custom-owner")
        dock.mapboxStyleIdLineEdit.setText("style-id")
        dock.atlasMarginPercentSpinBox.setValue(12.0)
        dock.atlasMinExtentSpinBox.setValue(0.25)
        dock.atlasTargetAspectRatioSpinBox.setValue(1.75)
        dock.atlasPdfPathLineEdit.setText("/tmp/atlas.pdf")
        dock.analysisModeComboBox.setCurrentIndex(1)
        dock.backgroundPresetComboBox.setCurrentIndex(1)
        dock.tileModeComboBox.setCurrentIndex(1)
        dock.previewSortComboBox.setCurrentIndex(1)
        dock.stylePresetComboBox.setCurrentIndex(1)

        settings = _settings()
        save_bindings(build_dock_settings_bindings(dock), settings)

        self.assertEqual(settings.get("client_id"), "abc")
        self.assertEqual(settings.get("activity_search_text"), "commute")
        self.assertEqual(settings.get("per_page"), 123)
        self.assertTrue(settings.get_bool("use_detailed_streams"))
        self.assertEqual(settings.get("detailed_route_strategy"), "Only missing detailed routes")
        self.assertFalse(settings.get_bool("write_activity_points", True))
        self.assertEqual(settings.get("detailed_route_filter"), "missing")
        self.assertEqual(settings.get("mapbox_style_owner"), "custom-owner")
        self.assertEqual(settings.get("atlas_target_aspect_ratio"), 1.75)
        self.assertEqual(settings.get("analysis_mode"), "Most frequent starting points")
        self.assertEqual(settings.get("style_preset"), "Heatmap")


if __name__ == "__main__":
    unittest.main()
