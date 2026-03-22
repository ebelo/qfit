import os
from datetime import date, datetime, time

from qgis.core import QgsApplication, QgsProject
from qgis.PyQt import uic
from qgis.PyQt.QtCore import QDate, QSettings, QStandardPaths, QUrl
from qgis.PyQt.QtGui import QDesktopServices
from qgis.PyQt.QtWidgets import QApplication, QFileDialog, QDockWidget, QMessageBox

from .activity_query import (
    DEFAULT_SORT_LABEL,
    SORT_OPTIONS,
    ActivityQuery,
    build_preview_lines,
    filter_activities,
    format_summary_text,
    sort_activities,
    summarize_activities,
)
from .contextual_help import ContextualHelpBinder, build_dock_help_entries
from .gpkg_writer import GeoPackageWriter
from .layer_manager import LayerManager
from .mapbox_config import (
    DEFAULT_BACKGROUND_PRESET,
    TILE_MODE_RASTER,
    TILE_MODE_VECTOR,
    TILE_MODES,
    MapboxConfigError,
    background_preset_names,
    preset_defaults,
    preset_requires_custom_style,
)
from .fetch_task import StravaFetchTask
from .atlas_export_task import AtlasExportTask, BUILTIN_ATLAS_MAP_TARGET_ASPECT_RATIO
from .qfit_cache import QfitCache
from .strava_client import StravaClient, StravaClientError
from .temporal_config import DEFAULT_TEMPORAL_MODE_LABEL, temporal_mode_labels

FORM_CLASS, _ = uic.loadUiType(
    __import__("os").path.join(__import__("os").path.dirname(__file__), "qfit_dockwidget_base.ui")
)


class QfitDockWidget(QDockWidget, FORM_CLASS):
    SETTINGS_PREFIX = "qfit"
    LEGACY_SETTINGS_PREFIX = "QFIT"

    def __init__(self, iface, parent=None):
        super().__init__(parent)
        self.iface = iface
        self.activities = []
        self.output_path = None
        self.activities_layer = None
        self.starts_layer = None
        self.points_layer = None
        self.atlas_layer = None
        self.background_layer = None
        self.last_fetch_context = {}
        self._fetch_task = None
        self._atlas_export_task = None
        self.layer_manager = LayerManager(iface)
        self.cache = self._build_cache()
        self.setupUi(self)
        self._remove_stale_qfit_layers()
        self._apply_contextual_help()
        self._configure_background_preset_options()
        self._configure_preview_sort_options()
        self._configure_temporal_mode_options()
        self._load_settings()
        self._wire_events()
        self._set_default_dates()
        self._configure_workflow_sections()
        self._refresh_activity_preview()
        self._update_connection_status()

    def _remove_stale_qfit_layers(self):
        """Remove qfit layers from the project whose source file no longer exists.

        Stale layers from a previous session generate SQLite errors when QGIS
        tries to query them.  We clean them up on startup before any signals fire.
        """
        _QFIT_LAYER_NAMES = {
            "qfit activities",
            "qfit activity starts",
            "qfit activity points",
            "qfit atlas pages",
        }
        project = QgsProject.instance()
        to_remove = []
        for layer in project.mapLayers().values():
            if layer.name() not in _QFIT_LAYER_NAMES:
                continue
            source = layer.source()
            # GeoPackage URI looks like "/path/to/file.gpkg|layername=..."
            gpkg_path = source.split("|")[0].strip()
            if gpkg_path and not os.path.exists(gpkg_path):
                to_remove.append(layer.id())
        for layer_id in to_remove:
            project.removeMapLayer(layer_id)

    def _apply_contextual_help(self):
        for name in [
            "backgroundHelpLabel",
            "analysisHelpLabel",
            "publishHelpLabel",
            "temporalHelpLabel",
        ]:
            label = getattr(self, name, None)
            if label is not None:
                label.hide()

        ContextualHelpBinder(self).apply(build_dock_help_entries())

    def _wire_events(self):
        self.openAuthorizeButton.clicked.connect(self.on_open_authorize_clicked)
        self.exchangeCodeButton.clicked.connect(self.on_exchange_code_clicked)
        self.browseButton.clicked.connect(self.on_browse_clicked)
        self.refreshButton.clicked.connect(self.on_refresh_clicked)
        self.loadButton.clicked.connect(self.on_load_clicked)
        self.loadLayersButton.clicked.connect(self.on_load_layers_clicked)
        self.clearDatabaseButton.clicked.connect(self.on_clear_database_clicked)
        self.applyFiltersButton.clicked.connect(self.on_apply_filters_clicked)
        self.loadBackgroundButton.clicked.connect(self.on_load_background_clicked)
        self.backgroundPresetComboBox.currentTextChanged.connect(self.on_background_preset_changed)
        self.detailedStreamsCheckBox.toggled.connect(self._update_detailed_fetch_visibility)
        self.writeActivityPointsCheckBox.toggled.connect(self._update_point_sampling_visibility)
        self.publishGroupBox.toggled.connect(self._update_publish_section_visibility)
        self.advancedFetchGroupBox.toggled.connect(self._update_advanced_fetch_visibility)
        self.atlasPdfBrowseButton.clicked.connect(self.on_atlas_pdf_browse_clicked)
        self.generateAtlasPdfButton.clicked.connect(self.on_generate_atlas_pdf_clicked)
        self.clientIdLineEdit.textChanged.connect(self._update_connection_status)
        self.clientSecretLineEdit.textChanged.connect(self._update_connection_status)
        self.refreshTokenLineEdit.textChanged.connect(self._update_connection_status)

        preview_inputs = [
            self.activityTypeComboBox.currentTextChanged,
            self.activitySearchLineEdit.textChanged,
            self.dateFromEdit.dateChanged,
            self.dateToEdit.dateChanged,
            self.minDistanceSpinBox.valueChanged,
            self.maxDistanceSpinBox.valueChanged,
            self.detailedOnlyCheckBox.toggled,
            self.previewSortComboBox.currentTextChanged,
        ]
        for signal in preview_inputs:
            signal.connect(self._refresh_activity_preview)

    def _configure_background_preset_options(self):
        self.backgroundPresetComboBox.clear()
        for preset_name in background_preset_names():
            self.backgroundPresetComboBox.addItem(preset_name)
        self.tileModeComboBox.clear()
        for mode in TILE_MODES:
            self.tileModeComboBox.addItem(mode)

    def _configure_preview_sort_options(self):
        self.previewSortComboBox.clear()
        for label in SORT_OPTIONS:
            self.previewSortComboBox.addItem(label)

    def _configure_temporal_mode_options(self):
        self.temporalModeComboBox.clear()
        for label in temporal_mode_labels():
            self.temporalModeComboBox.addItem(label)

    def _configure_workflow_sections(self):
        self._update_detailed_fetch_visibility(self.detailedStreamsCheckBox.isChecked())
        self._update_point_sampling_visibility(self.writeActivityPointsCheckBox.isChecked())
        self._update_publish_section_visibility(self.publishGroupBox.isChecked())
        self._update_advanced_fetch_visibility(self.advancedFetchGroupBox.isChecked())
        self._update_mapbox_advanced_visibility(self.backgroundPresetComboBox.currentText())

    def _update_detailed_fetch_visibility(self, enabled):
        self.maxDetailedActivitiesLabel.setVisible(enabled)
        self.maxDetailedActivitiesSpinBox.setVisible(enabled)
        helper = getattr(self, "maxDetailedActivitiesSpinBoxContextHelpLabel", None)
        if helper is not None:
            helper.setVisible(enabled)
        wrapper = getattr(self, "maxDetailedActivitiesSpinBoxHelpField", None)
        if wrapper is not None:
            wrapper.setVisible(enabled)

    def _update_point_sampling_visibility(self, enabled):
        self.pointSamplingStrideLabel.setVisible(enabled)
        self.pointSamplingStrideSpinBox.setVisible(enabled)
        helper = getattr(self, "pointSamplingStrideSpinBoxContextHelpLabel", None)
        if helper is not None:
            helper.setVisible(enabled)
        wrapper = getattr(self, "pointSamplingStrideSpinBoxHelpField", None)
        if wrapper is not None:
            wrapper.setVisible(enabled)

    def _update_publish_section_visibility(self, expanded):
        if hasattr(self, "publishSettingsWidget"):
            self.publishSettingsWidget.setVisible(expanded)

    def _update_advanced_fetch_visibility(self, expanded):
        widget = getattr(self, "advancedFetchSettingsWidget", None)
        if widget is not None:
            widget.setVisible(expanded)

    def _update_mapbox_advanced_visibility(self, preset_name):
        show_advanced = preset_requires_custom_style(preset_name)
        self.mapboxStyleOwnerLabel.setVisible(show_advanced)
        self.mapboxStyleOwnerLineEdit.setVisible(show_advanced)
        self.mapboxStyleIdLabel.setVisible(show_advanced)
        self.mapboxStyleIdLineEdit.setVisible(show_advanced)
        owner_helper = getattr(self, "mapboxStyleOwnerLineEditContextHelpLabel", None)
        if owner_helper is not None:
            owner_helper.setVisible(show_advanced)
        style_helper = getattr(self, "mapboxStyleIdLineEditContextHelpLabel", None)
        if style_helper is not None:
            style_helper.setVisible(show_advanced)
        style_wrapper = getattr(self, "mapboxStyleIdLineEditHelpField", None)
        if style_wrapper is not None:
            style_wrapper.setVisible(show_advanced)

    def _build_cache(self):
        base_path = QStandardPaths.writableLocation(QStandardPaths.AppDataLocation)
        if not base_path:
            base_path = os.path.join(os.path.expanduser("~"), ".qfit")

        current_cache_path = os.path.join(base_path, "qfit", "cache")
        legacy_cache_path = os.path.join(base_path, "QFIT", "cache")
        if not os.path.exists(current_cache_path) and os.path.exists(legacy_cache_path):
            return QfitCache(legacy_cache_path)
        return QfitCache(current_cache_path)

    def _load_settings(self):
        settings = QSettings()
        self.clientIdLineEdit.setText(self._setting_value(settings, "client_id", ""))
        self.clientSecretLineEdit.setText(self._setting_value(settings, "client_secret", ""))
        self.redirectUriLineEdit.setText(
            self._setting_value(
                settings,
                "redirect_uri",
                StravaClient.DEFAULT_REDIRECT_URI,
            )
        )
        self.authCodeLineEdit.setText("")
        self.refreshTokenLineEdit.setText(self._setting_value(settings, "refresh_token", ""))
        default_output = self._setting_value(
            settings,
            "output_path",
            os.path.join(os.path.expanduser("~"), "qfit_activities.gpkg"),
        )
        self.outputPathLineEdit.setText(default_output)
        self.perPageSpinBox.setValue(int(self._setting_value(settings, "per_page", 200)))
        self.maxPagesSpinBox.setValue(int(self._setting_value(settings, "max_pages", 0)))
        self.detailedStreamsCheckBox.setChecked(self._settings_bool(settings, "use_detailed_streams", False))
        self.maxDetailedActivitiesSpinBox.setValue(int(self._setting_value(settings, "max_detailed_activities", 25)))
        self.writeActivityPointsCheckBox.setChecked(
            self._settings_bool(settings, "write_activity_points", False)
        )
        self.pointSamplingStrideSpinBox.setValue(int(self._setting_value(settings, "point_sampling_stride", 5)))
        self.activitySearchLineEdit.setText(self._setting_value(settings, "activity_search_text", ""))
        self.maxDistanceSpinBox.setValue(float(self._setting_value(settings, "max_distance_km", 0.0)))
        self.detailedOnlyCheckBox.setChecked(self._settings_bool(settings, "detailed_only", False))
        self.backgroundMapCheckBox.setChecked(self._settings_bool(settings, "use_background_map", False))
        self.mapboxAccessTokenLineEdit.setText(self._setting_value(settings, "mapbox_access_token", ""))
        self.mapboxStyleOwnerLineEdit.setText(
            self._setting_value(settings, "mapbox_style_owner", "mapbox")
        )
        self.mapboxStyleIdLineEdit.setText(self._setting_value(settings, "mapbox_style_id", ""))
        self.atlasMarginPercentSpinBox.setValue(float(self._setting_value(settings, "atlas_margin_percent", 8.0)))
        self.atlasMinExtentSpinBox.setValue(float(self._setting_value(settings, "atlas_min_extent_degrees", 0.01)))
        stored_atlas_target_aspect_ratio = float(
            self._setting_value(settings, "atlas_target_aspect_ratio", BUILTIN_ATLAS_MAP_TARGET_ASPECT_RATIO)
        )
        if stored_atlas_target_aspect_ratio <= 0:
            stored_atlas_target_aspect_ratio = BUILTIN_ATLAS_MAP_TARGET_ASPECT_RATIO
        self.atlasTargetAspectRatioSpinBox.setValue(stored_atlas_target_aspect_ratio)
        default_pdf_path = self._setting_value(
            settings,
            "atlas_pdf_path",
            os.path.join(os.path.expanduser("~"), "qfit_atlas.pdf"),
        )
        self.atlasPdfPathLineEdit.setText(default_pdf_path)

        temporal_mode = self._setting_value(settings, "temporal_mode", DEFAULT_TEMPORAL_MODE_LABEL)
        temporal_mode_index = self.temporalModeComboBox.findText(temporal_mode)
        if temporal_mode_index < 0:
            temporal_mode_index = self.temporalModeComboBox.findText(DEFAULT_TEMPORAL_MODE_LABEL)
        self.temporalModeComboBox.setCurrentIndex(max(temporal_mode_index, 0))

        preset_name = self._setting_value(settings, "background_preset", DEFAULT_BACKGROUND_PRESET)
        preset_index = self.backgroundPresetComboBox.findText(preset_name)
        if preset_index < 0:
            preset_index = self.backgroundPresetComboBox.findText(DEFAULT_BACKGROUND_PRESET)
        self.backgroundPresetComboBox.setCurrentIndex(max(preset_index, 0))
        self._sync_background_style_fields(self.backgroundPresetComboBox.currentText(), force=False)

        tile_mode = self._setting_value(settings, "tile_mode", TILE_MODE_RASTER)
        tile_mode_index = self.tileModeComboBox.findText(tile_mode)
        self.tileModeComboBox.setCurrentIndex(max(tile_mode_index, 0))

        preview_sort = self._setting_value(settings, "preview_sort", DEFAULT_SORT_LABEL)
        preview_sort_index = self.previewSortComboBox.findText(preview_sort)
        if preview_sort_index < 0:
            preview_sort_index = self.previewSortComboBox.findText(DEFAULT_SORT_LABEL)
        self.previewSortComboBox.setCurrentIndex(max(preview_sort_index, 0))

        style_preset = self._setting_value(settings, "style_preset", "By activity type")
        style_preset_index = self.stylePresetComboBox.findText(style_preset)
        if style_preset_index < 0:
            style_preset_index = self.stylePresetComboBox.findText("By activity type")
        self.stylePresetComboBox.setCurrentIndex(max(style_preset_index, 0))

        last_sync = self._setting_value(settings, "last_sync_date", None)
        if last_sync:
            self.countLabel.setText(f"Last sync: {last_sync}")

    def _save_settings(self):
        settings = QSettings()
        settings.setValue(f"{self.SETTINGS_PREFIX}/client_id", self.clientIdLineEdit.text().strip())
        settings.setValue(f"{self.SETTINGS_PREFIX}/client_secret", self.clientSecretLineEdit.text().strip())
        settings.setValue(f"{self.SETTINGS_PREFIX}/redirect_uri", self.redirectUriLineEdit.text().strip())
        settings.setValue(f"{self.SETTINGS_PREFIX}/refresh_token", self.refreshTokenLineEdit.text().strip())
        settings.setValue(f"{self.SETTINGS_PREFIX}/output_path", self.outputPathLineEdit.text().strip())
        settings.setValue(f"{self.SETTINGS_PREFIX}/per_page", self.perPageSpinBox.value())
        settings.setValue(f"{self.SETTINGS_PREFIX}/max_pages", self.maxPagesSpinBox.value())
        settings.setValue(f"{self.SETTINGS_PREFIX}/use_detailed_streams", self.detailedStreamsCheckBox.isChecked())
        settings.setValue(
            f"{self.SETTINGS_PREFIX}/max_detailed_activities",
            self.maxDetailedActivitiesSpinBox.value(),
        )
        settings.setValue(
            f"{self.SETTINGS_PREFIX}/write_activity_points",
            self.writeActivityPointsCheckBox.isChecked(),
        )
        settings.setValue(
            f"{self.SETTINGS_PREFIX}/point_sampling_stride",
            self.pointSamplingStrideSpinBox.value(),
        )
        settings.setValue(
            f"{self.SETTINGS_PREFIX}/activity_search_text",
            self.activitySearchLineEdit.text().strip(),
        )
        settings.setValue(
            f"{self.SETTINGS_PREFIX}/max_distance_km",
            self.maxDistanceSpinBox.value(),
        )
        settings.setValue(
            f"{self.SETTINGS_PREFIX}/detailed_only",
            self.detailedOnlyCheckBox.isChecked(),
        )
        settings.setValue(
            f"{self.SETTINGS_PREFIX}/preview_sort",
            self.previewSortComboBox.currentText(),
        )
        settings.setValue(
            f"{self.SETTINGS_PREFIX}/style_preset",
            self.stylePresetComboBox.currentText(),
        )
        settings.setValue(
            f"{self.SETTINGS_PREFIX}/temporal_mode",
            self.temporalModeComboBox.currentText(),
        )
        settings.setValue(
            f"{self.SETTINGS_PREFIX}/use_background_map",
            self.backgroundMapCheckBox.isChecked(),
        )
        settings.setValue(
            f"{self.SETTINGS_PREFIX}/background_preset",
            self.backgroundPresetComboBox.currentText(),
        )
        settings.setValue(
            f"{self.SETTINGS_PREFIX}/mapbox_access_token",
            self.mapboxAccessTokenLineEdit.text().strip(),
        )
        settings.setValue(
            f"{self.SETTINGS_PREFIX}/mapbox_style_owner",
            self.mapboxStyleOwnerLineEdit.text().strip(),
        )
        settings.setValue(
            f"{self.SETTINGS_PREFIX}/mapbox_style_id",
            self.mapboxStyleIdLineEdit.text().strip(),
        )
        settings.setValue(
            f"{self.SETTINGS_PREFIX}/tile_mode",
            self.tileModeComboBox.currentText(),
        )
        settings.setValue(
            f"{self.SETTINGS_PREFIX}/atlas_margin_percent",
            self.atlasMarginPercentSpinBox.value(),
        )
        settings.setValue(
            f"{self.SETTINGS_PREFIX}/atlas_min_extent_degrees",
            self.atlasMinExtentSpinBox.value(),
        )
        settings.setValue(
            f"{self.SETTINGS_PREFIX}/atlas_target_aspect_ratio",
            self.atlasTargetAspectRatioSpinBox.value(),
        )
        settings.setValue(
            f"{self.SETTINGS_PREFIX}/atlas_pdf_path",
            self.atlasPdfPathLineEdit.text().strip(),
        )

    def _setting_value(self, settings, key, default=None):
        value = settings.value(f"{self.SETTINGS_PREFIX}/{key}", None)
        if value not in (None, ""):
            return value
        legacy_value = settings.value(f"{self.LEGACY_SETTINGS_PREFIX}/{key}", None)
        if legacy_value not in (None, ""):
            return legacy_value
        return default

    def _settings_bool(self, settings, key, default=False):
        value = self._setting_value(settings, key, default)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ("1", "true", "yes", "on")
        return bool(value)

    def _set_default_dates(self):
        if not self.dateFromEdit.date().isValid():
            self.dateFromEdit.setDate(QDate.currentDate().addYears(-1))
        if not self.dateToEdit.date().isValid():
            self.dateToEdit.setDate(QDate.currentDate())

    def on_background_preset_changed(self, preset_name):
        self._sync_background_style_fields(preset_name, force=True)
        self._update_mapbox_advanced_visibility(preset_name)

    def on_load_background_clicked(self):
        self._save_settings()
        enabled = self.backgroundMapCheckBox.isChecked()
        try:
            self.background_layer = self.layer_manager.ensure_background_layer(
                enabled=enabled,
                preset_name=self.backgroundPresetComboBox.currentText(),
                access_token=self.mapboxAccessTokenLineEdit.text().strip(),
                style_owner=self.mapboxStyleOwnerLineEdit.text().strip(),
                style_id=self.mapboxStyleIdLineEdit.text().strip(),
                tile_mode=self.tileModeComboBox.currentText(),
            )
        except (MapboxConfigError, RuntimeError) as exc:
            self._show_error("Background map failed", str(exc))
            self._set_status("Background map could not be updated")
            return

        if enabled and self.background_layer is not None:
            self._set_status("Background map loaded below the qfit activity layers")
        else:
            self._set_status("Background map cleared")

    def _sync_background_style_fields(self, preset_name, force=False):
        if preset_requires_custom_style(preset_name):
            return
        current_owner = self.mapboxStyleOwnerLineEdit.text().strip()
        current_style_id = self.mapboxStyleIdLineEdit.text().strip()
        if current_owner and current_style_id and not force:
            return
        style_owner, style_id = preset_defaults(preset_name)
        self.mapboxStyleOwnerLineEdit.setText(style_owner)
        self.mapboxStyleIdLineEdit.setText(style_id)

    def on_open_authorize_clicked(self):
        self._save_settings()
        try:
            client = self._build_client(require_refresh_token=False)
            redirect_uri = self._redirect_uri()
            url = client.build_authorize_url(redirect_uri=redirect_uri)
            if not QDesktopServices.openUrl(QUrl(url)):
                clipboard = QApplication.clipboard()
                if clipboard is not None:
                    clipboard.setText(url)
                self._show_info(
                    "Open Strava authorize page manually",
                    "qfit could not open the browser automatically. The authorization URL was copied to your clipboard.\n\nOpen this URL in a browser and continue the flow there:\n\n{url}".format(
                        url=url
                    ),
                )
                self._set_status(
                    "Could not open browser automatically. Authorization URL copied to clipboard."
                )
                return
            self._set_status(
                "Strava authorization opened in your browser. Approve access, copy the returned code, then paste it here and click Exchange code."
            )
        except StravaClientError as exc:
            self._show_error("Strava authorization failed", str(exc))
            self._set_status("Could not start the Strava authorization flow")

    def on_exchange_code_clicked(self):
        self._save_settings()
        authorization_code = self.authCodeLineEdit.text().strip()
        if not authorization_code:
            self._show_error("Missing authorization code", "Paste the code returned by Strava first.")
            return

        try:
            client = self._build_client(require_refresh_token=False)
            payload = client.exchange_code_for_tokens(
                authorization_code=authorization_code,
                redirect_uri=self._redirect_uri(),
            )
            refresh_token = payload.get("refresh_token")
            if not refresh_token:
                raise StravaClientError("Strava returned no refresh token")
            self.refreshTokenLineEdit.setText(refresh_token)
            self.authCodeLineEdit.clear()
            self._save_settings()
            self._update_connection_status()
            athlete = payload.get("athlete") or {}
            athlete_name = " ".join(
                part for part in [athlete.get("firstname"), athlete.get("lastname")] if part
            ).strip()
            if athlete_name:
                self._set_status(
                    "Strava connected for {name}. Refresh token saved locally in QGIS settings.".format(
                        name=athlete_name
                    )
                )
            else:
                self._set_status("Strava refresh token saved locally in QGIS settings.")
        except StravaClientError as exc:
            self._show_error("Token exchange failed", str(exc))
            self._set_status("Could not exchange the Strava authorization code")

    def on_browse_clicked(self):
        path, _selected = QFileDialog.getSaveFileName(
            self,
            "Choose GeoPackage output",
            self.outputPathLineEdit.text(),
            "GeoPackage (*.gpkg)",
        )
        if path:
            if not path.lower().endswith(".gpkg"):
                path = "{path}.gpkg".format(path=path)
            self.outputPathLineEdit.setText(path)

    def on_refresh_clicked(self):
        # If a fetch is already running, cancel it.
        if self._fetch_task is not None:
            self._fetch_task.cancel()
            self._set_fetch_running(False)
            self._set_status("Fetch cancelled.")
            self._fetch_task = None
            return

        self._save_settings()
        try:
            client = self._build_client(require_refresh_token=True)
        except StravaClientError as exc:
            self._show_error("Strava import failed", str(exc))
            self._set_status("Strava fetch failed")
            return

        # Issue #38: fetch all activities — no date filtering at import time.
        # Date filters are visualization-only (applied post-import to loaded layers).
        self._fetch_task = StravaFetchTask(
            client=client,
            per_page=self.perPageSpinBox.value(),
            max_pages=self.maxPagesSpinBox.value(),
            before=None,
            after=None,
            use_detailed_streams=self.detailedStreamsCheckBox.isChecked(),
            max_detailed_activities=self.maxDetailedActivitiesSpinBox.value(),
            on_finished=self._on_fetch_finished,
        )
        self._set_fetch_running(True)
        self._set_status("Fetching activities from Strava…")
        QgsApplication.taskManager().addTask(self._fetch_task)

    def _set_fetch_running(self, running):
        """Toggle UI state while a background fetch is in progress."""
        self.refreshButton.setText("Cancel" if running else "Fetch activities")
        self.exchangeCodeButton.setEnabled(not running)
        self.openAuthorizeButton.setEnabled(not running)

    def _on_fetch_finished(self, activities, error, cancelled, client):
        """Called on the main thread when the background fetch completes."""
        self._fetch_task = None
        self._set_fetch_running(False)

        if cancelled:
            self._set_status("Fetch cancelled.")
            return

        if error is not None:
            self._show_error("Strava import failed", error)
            self._set_status("Strava fetch failed")
            return

        before, after = self._build_fetch_epoch_range()
        self.activities = activities
        detailed_count = sum(1 for activity in self.activities if activity.geometry_source == "stream")
        today_str = date.today().isoformat()
        self.last_fetch_context = {
            "provider": "strava",
            "before_epoch": before,
            "after_epoch": after,
            "fetched_count": len(self.activities),
            "detailed_count": detailed_count,
            "stream_stats": client.last_stream_enrichment_stats,
            "rate_limit": client.last_rate_limit,
            "is_full_sync": self._is_full_sync_window(before, after),
        }
        # Persist last sync date
        settings = QSettings()
        settings.setValue(f"{self.SETTINGS_PREFIX}/last_sync_date", today_str)

        self._populate_activity_types()
        self.countLabel.setText(
            "{count} activities loaded (last sync: {sync_date}, detailed tracks: {detailed})".format(
                count=len(self.activities),
                sync_date=today_str,
                detailed=detailed_count,
            )
        )
        self._refresh_activity_preview()
        self._set_status(self._fetch_status_text(client, len(self.activities), detailed_count))

    def on_load_clicked(self):
        if not self.activities:
            self._show_error("Nothing to load", "Fetch activities from Strava first.")
            return

        self._save_settings()
        output_path = self.outputPathLineEdit.text().strip()
        if not output_path:
            self._show_error("Missing output path", "Choose a GeoPackage output path first.")
            return

        self._set_status("Writing GeoPackage…")
        try:
            writer = GeoPackageWriter(
                output_path=output_path,
                write_activity_points=self.writeActivityPointsCheckBox.isChecked(),
                point_stride=self.pointSamplingStrideSpinBox.value(),
                atlas_margin_percent=self.atlasMarginPercentSpinBox.value(),
                atlas_min_extent_degrees=self.atlasMinExtentSpinBox.value(),
                atlas_target_aspect_ratio=self.atlasTargetAspectRatioSpinBox.value(),
            )
            result = writer.write_activities(self.activities, sync_metadata=self.last_fetch_context)
            self.output_path = result["path"]
            self.activities_layer, self.starts_layer, self.points_layer, self.atlas_layer = self.layer_manager.load_output_layers(
                self.output_path
            )
            visual_status = self._apply_visual_configuration(apply_subset_filters=False)
            sync = result.get("sync") or {}
            if visual_status:
                visual_status = f" {visual_status}"

            # Update completeness indicator with last sync date from QSettings
            settings = QSettings()
            last_sync = self._setting_value(settings, "last_sync_date", date.today().isoformat())
            total_stored = sync.get("total_count", 0)
            self.countLabel.setText(
                "{total} activities stored (last sync: {sync_date})".format(
                    total=total_stored,
                    sync_date=last_sync,
                )
            )

            self._set_status(
                "Synced {fetched} fetched activities into GeoPackage: inserted {inserted}, updated {updated}, unchanged {unchanged}, stored total {total}. Loaded {track_count} tracks, {start_count} starts, {point_count} activity points, and {atlas_count} atlas pages into QGIS without auto-filtering the layer tables.{visual_status}".format(
                    fetched=result.get("fetched_count", len(self.activities)),
                    inserted=sync.get("inserted", 0),
                    updated=sync.get("updated", 0),
                    unchanged=sync.get("unchanged", 0),
                    total=total_stored,
                    track_count=result.get("track_count", 0),
                    start_count=result.get("start_count", 0),
                    point_count=result.get("point_count", 0),
                    atlas_count=result.get("atlas_count", 0),
                    visual_status=visual_status,
                )
            )
        except Exception as exc:  # noqa: BLE001
            self._show_error("GeoPackage export failed", str(exc))
            self._set_status("GeoPackage export failed")

    def on_load_layers_clicked(self):
        """Load an existing GeoPackage into QGIS without fetching from Strava."""
        self._save_settings()
        output_path = self.outputPathLineEdit.text().strip()
        if not output_path:
            self._show_error("Missing output path", "Choose a GeoPackage output path first.")
            return
        if not os.path.exists(output_path):
            self._show_error(
                "GeoPackage not found",
                f"No database found at:\n  {output_path}\n\nFetch & Store activities first to create it.",
            )
            return

        self._set_status("Loading layers from GeoPackage…")
        try:
            self.output_path = output_path
            self.activities_layer, self.starts_layer, self.points_layer, self.atlas_layer = self.layer_manager.load_output_layers(
                self.output_path
            )
            self._populate_activity_types_from_layer()
            visual_status = self._apply_visual_configuration(apply_subset_filters=False)
            if visual_status:
                visual_status = f" {visual_status}"

            settings = QSettings()
            last_sync = self._setting_value(settings, "last_sync_date", "unknown")
            total = (self.activities_layer.featureCount() if self.activities_layer else 0)
            self.countLabel.setText(
                "{total} activities loaded (last sync: {sync_date})".format(
                    total=total, sync_date=last_sync
                )
            )
            self._set_status(
                "Layers loaded from {path}.{visual_status}".format(
                    path=output_path, visual_status=visual_status
                )
            )
        except Exception as exc:  # noqa: BLE001
            self._show_error("Load layers failed", str(exc))
            self._set_status("Load layers failed")

    def on_clear_database_clicked(self):
        """Delete the GeoPackage, clear loaded layers, and reset status."""
        output_path = self.outputPathLineEdit.text().strip()
        if not output_path:
            self._show_error("No database path", "Set a GeoPackage output path first.")
            return

        reply = QMessageBox.question(
            self,
            "Clear database & re-import",
            (
                "This will delete the GeoPackage file and remove all qfit layers from QGIS:\n\n"
                f"  {output_path}\n\n"
                "The file cannot be recovered. Continue?"
            ),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        # Remove layers from QGIS project
        for layer in [self.activities_layer, self.starts_layer, self.points_layer, self.atlas_layer]:
            if layer is not None:
                try:
                    QgsProject.instance().removeMapLayer(layer)
                except Exception:  # noqa: BLE001
                    pass

        self.activities_layer = None
        self.starts_layer = None
        self.points_layer = None
        self.atlas_layer = None
        self.activities = []
        self.output_path = None
        self.last_fetch_context = {}

        # Delete the file
        deleted = False
        if os.path.exists(output_path):
            try:
                os.remove(output_path)
                deleted = True
            except OSError as exc:
                self._show_error("Could not delete database", str(exc))
                self._set_status("Failed to delete the GeoPackage file")
                return

        self.countLabel.setText("Activities fetched: 0")
        if deleted:
            self._set_status(
                f"Database cleared: {output_path} deleted. Fetch and store activities to start fresh."
            )
        else:
            self._set_status("Layers cleared. No file to delete at the specified path.")

    def on_apply_filters_clicked(self):
        has_layers = any(layer is not None for layer in [self.activities_layer, self.starts_layer, self.points_layer, self.atlas_layer])
        wants_background = self.backgroundMapCheckBox.isChecked()
        if not has_layers and not wants_background:
            return

        self._save_settings()
        status = self._apply_visual_configuration(apply_subset_filters=True)
        if status:
            self._set_status(status)

    def _apply_visual_configuration(self, apply_subset_filters):
        has_layers = any(layer is not None for layer in [self.activities_layer, self.starts_layer, self.points_layer, self.atlas_layer])
        wants_background = self.backgroundMapCheckBox.isChecked()
        filtered_activities = self._refresh_activity_preview()
        query = self._current_activity_query()
        preset = self.stylePresetComboBox.currentText()
        temporal_note = ""

        if has_layers and apply_subset_filters:
            self.layer_manager.apply_filters(
                self.activities_layer,
                query.activity_type,
                query.date_from,
                query.date_to,
                query.min_distance_km,
                query.max_distance_km,
                query.search_text,
                query.detailed_only,
            )
            self.layer_manager.apply_filters(
                self.starts_layer,
                query.activity_type,
                query.date_from,
                query.date_to,
                query.min_distance_km,
                query.max_distance_km,
                query.search_text,
                query.detailed_only,
            )
            self.layer_manager.apply_filters(
                self.points_layer,
                query.activity_type,
                query.date_from,
                query.date_to,
                query.min_distance_km,
                query.max_distance_km,
                query.search_text,
                query.detailed_only,
            )
            self.layer_manager.apply_filters(
                self.atlas_layer,
                query.activity_type,
                query.date_from,
                query.date_to,
                query.min_distance_km,
                query.max_distance_km,
                query.search_text,
                query.detailed_only,
            )

        if has_layers:
            self.layer_manager.apply_style(
                self.activities_layer,
                self.starts_layer,
                self.points_layer,
                self.atlas_layer,
                preset,
                background_preset_name=self.backgroundPresetComboBox.currentText() if wants_background else None,
            )
            temporal_note = self.layer_manager.apply_temporal_configuration(
                self.activities_layer,
                self.starts_layer,
                self.points_layer,
                self.atlas_layer,
                self.temporalModeComboBox.currentText(),
            )

        try:
            self.background_layer = self.layer_manager.ensure_background_layer(
                enabled=wants_background,
                preset_name=self.backgroundPresetComboBox.currentText(),
                access_token=self.mapboxAccessTokenLineEdit.text().strip(),
                style_owner=self.mapboxStyleOwnerLineEdit.text().strip(),
                style_id=self.mapboxStyleIdLineEdit.text().strip(),
                tile_mode=self.tileModeComboBox.currentText(),
            )
        except (MapboxConfigError, RuntimeError) as exc:
            self._show_error("Background map failed", str(exc))
            if not has_layers:
                failure_status = "Background map could not be updated"
            elif apply_subset_filters:
                failure_status = "Applied filters and styling, but the background map could not be updated"
            else:
                failure_status = "Loaded layers with styling, but the background map could not be updated"
            if temporal_note:
                failure_status = f"{failure_status}. {temporal_note}."
            return failure_status

        filtered_count = len(filtered_activities)
        if has_layers and wants_background and self.background_layer is not None:
            if apply_subset_filters:
                status = f"Applied filters, styling, and background map ({filtered_count} matching activities)"
            else:
                status = "Applied styling and loaded the background map below the qfit activity layers"
        elif has_layers:
            status = f"Applied filters and styling ({filtered_count} matching activities)" if apply_subset_filters else "Applied styling to the loaded qfit layers"
        elif wants_background and self.background_layer is not None:
            status = f"Background map updated ({filtered_count} matching activities)" if apply_subset_filters else "Background map loaded below the qfit activity layers"
        else:
            status = f"Background map cleared ({filtered_count} matching activities)" if apply_subset_filters else "Background map cleared"

        if temporal_note:
            status = f"{status}. {temporal_note}."
        return status

    def _current_activity_query(self):
        return ActivityQuery(
            activity_type=self.activityTypeComboBox.currentText() or "All",
            date_from=self.dateFromEdit.date().toString("yyyy-MM-dd") if self.dateFromEdit.date().isValid() else None,
            date_to=self.dateToEdit.date().toString("yyyy-MM-dd") if self.dateToEdit.date().isValid() else None,
            min_distance_km=self.minDistanceSpinBox.value(),
            max_distance_km=self.maxDistanceSpinBox.value(),
            search_text=self.activitySearchLineEdit.text().strip(),
            detailed_only=self.detailedOnlyCheckBox.isChecked(),
            sort_label=self.previewSortComboBox.currentText() or DEFAULT_SORT_LABEL,
        )

    def _refresh_activity_preview(self):
        if not self.activities:
            self.querySummaryLabel.setText("Fetch activities to see a query summary.")
            self.activityPreviewPlainTextEdit.setPlainText("")
            return []

        query = self._current_activity_query()
        filtered = filter_activities(self.activities, query)
        sorted_activities = sort_activities(filtered, query.sort_label)
        summary = summarize_activities(sorted_activities)
        self.querySummaryLabel.setText(format_summary_text(summary))

        preview_lines = build_preview_lines(sorted_activities, limit=10)
        if len(sorted_activities) > len(preview_lines):
            preview_lines.append("… and {count} more".format(count=len(sorted_activities) - len(preview_lines)))
        self.activityPreviewPlainTextEdit.setPlainText("\n".join(preview_lines))
        return sorted_activities

    def _build_client(self, require_refresh_token=True):
        client = StravaClient(
            client_id=self.clientIdLineEdit.text().strip(),
            client_secret=self.clientSecretLineEdit.text().strip(),
            refresh_token=self.refreshTokenLineEdit.text().strip(),
            cache=self.cache,
        )
        if not client.has_client_credentials():
            raise StravaClientError("Enter Strava client ID and client secret first.")
        if require_refresh_token and not client.refresh_token:
            raise StravaClientError(
                "Enter a refresh token, or use the built-in authorization flow to generate one."
            )
        return client

    def _redirect_uri(self):
        return self.redirectUriLineEdit.text().strip() or StravaClient.DEFAULT_REDIRECT_URI

    def _build_fetch_epoch_range(self):
        local_tz = datetime.now().astimezone().tzinfo
        after = None
        before = None

        if self.dateFromEdit.date().isValid():
            start_date = self._qdate_to_date(self.dateFromEdit.date())
            after = int(datetime.combine(start_date, time(0, 0, 0), tzinfo=local_tz).timestamp())

        if self.dateToEdit.date().isValid():
            end_date = self._qdate_to_date(self.dateToEdit.date())
            before = int(datetime.combine(end_date, time(23, 59, 59), tzinfo=local_tz).timestamp())

        return before, after

    def _qdate_to_date(self, value):
        return date(value.year(), value.month(), value.day())

    def _is_full_sync_window(self, before_epoch, after_epoch):
        if before_epoch is None or after_epoch is None:
            return False
        return (before_epoch - after_epoch) >= 365 * 24 * 60 * 60

    def _populate_activity_types(self):
        current_value = self.activityTypeComboBox.currentText() or "All"
        values = sorted({activity.activity_type for activity in self.activities if activity.activity_type})
        self.activityTypeComboBox.clear()
        self.activityTypeComboBox.addItem("All")
        for value in values:
            self.activityTypeComboBox.addItem(value)
        index = self.activityTypeComboBox.findText(current_value)
        self.activityTypeComboBox.setCurrentIndex(max(index, 0))

    def _populate_activity_types_from_layer(self):
        """Populate the activity type filter from the loaded activities layer.

        Used when layers are loaded directly (without fetching), so the combo
        box shows the correct activity types from the existing GeoPackage.
        """
        if self.activities_layer is None or not self.activities_layer.isValid():
            return
        current_value = self.activityTypeComboBox.currentText() or "All"
        try:
            field_names = [self.activities_layer.fields().at(i).name() for i in range(self.activities_layer.fields().count())]
            type_field = next((f for f in ["sport_type", "activity_type"] if f in field_names), None)
            if type_field is None:
                return
            values = sorted({
                f[type_field]
                for f in self.activities_layer.getFeatures()
                if f[type_field]
            })
        except Exception:
            return
        self.activityTypeComboBox.clear()
        self.activityTypeComboBox.addItem("All")
        for value in values:
            self.activityTypeComboBox.addItem(value)
        index = self.activityTypeComboBox.findText(current_value)
        self.activityTypeComboBox.setCurrentIndex(max(index, 0))

    def _fetch_status_text(self, client, activity_count, detailed_count):
        stream_stats = client.last_stream_enrichment_stats or {}
        rate_limit_note = self._rate_limit_note(client.last_rate_limit)
        return (
            "Fetched {activity_count} activities from Strava, detailed tracks: {detailed_count}, "
            "cached streams: {cached}, downloaded streams: {downloaded}, rate-limit skips: {skipped}.{rate_note}"
        ).format(
            activity_count=activity_count,
            detailed_count=detailed_count,
            cached=stream_stats.get("cached", 0),
            downloaded=stream_stats.get("downloaded", 0),
            skipped=stream_stats.get("skipped_rate_limit", 0),
            rate_note=rate_limit_note,
        )

    def _rate_limit_note(self, rate_limit):
        if not rate_limit:
            return ""
        short_remaining = rate_limit.get("short_remaining")
        long_remaining = rate_limit.get("long_remaining")
        if short_remaining is None and long_remaining is None:
            return ""
        return " Remaining rate limit: short={short}, long={long}.".format(
            short=short_remaining if short_remaining is not None else "?",
            long=long_remaining if long_remaining is not None else "?",
        )

    def _update_connection_status(self):
        has_client = bool(self.clientIdLineEdit.text().strip() and self.clientSecretLineEdit.text().strip())
        has_refresh = bool(self.refreshTokenLineEdit.text().strip())
        if has_client and has_refresh:
            message = "Strava connection: ready to fetch activities"
        elif has_client:
            message = "Strava connection: app credentials saved; complete OAuth to fetch activities"
        else:
            message = "Strava connection: enter your Strava app credentials to begin"
        self.connectionStatusLabel.setText(message)

    def on_atlas_pdf_browse_clicked(self):
        path, _selected = QFileDialog.getSaveFileName(
            self,
            "Save Atlas PDF",
            self.atlasPdfPathLineEdit.text(),
            "PDF files (*.pdf)",
        )
        if path:
            if not path.lower().endswith(".pdf"):
                path = f"{path}.pdf"
            self.atlasPdfPathLineEdit.setText(path)

    def on_generate_atlas_pdf_clicked(self):
        # Cancel any running export
        if self._atlas_export_task is not None:
            self._atlas_export_task.cancel()
            self._set_atlas_pdf_status("Atlas PDF export cancelled.")
            self._set_atlas_export_running(False)
            self._atlas_export_task = None
            return

        if self.atlas_layer is None:
            self._show_error(
                "No atlas layer",
                "Store and load activity layers first (step 3: Store and load layers).",
            )
            return

        if self.atlas_layer.featureCount() == 0:
            self._show_error(
                "Atlas layer is empty",
                "The atlas_pages layer has no features. "
                "Fetch activities with geometry and store/load layers first.",
            )
            return

        output_path = self.atlasPdfPathLineEdit.text().strip()
        if not output_path:
            self._show_error("Missing output path", "Enter or browse to an output PDF path.")
            return
        if not output_path.lower().endswith(".pdf"):
            output_path = f"{output_path}.pdf"
            self.atlasPdfPathLineEdit.setText(output_path)

        self._save_settings()

        # Switch basemap to vector mode for export if currently raster — vector
        # tiles embed as true PDF vectors, dramatically reducing file size.
        # We reload the basemap in vector mode and restore raster after export.
        pre_export_tile_mode = self.tileModeComboBox.currentText()
        if (
            pre_export_tile_mode == TILE_MODE_RASTER
            and self.backgroundMapCheckBox.isChecked()
        ):
            try:
                self.layer_manager.ensure_background_layer(
                    enabled=True,
                    preset_name=self.backgroundPresetComboBox.currentText(),
                    access_token=self.mapboxAccessTokenLineEdit.text().strip(),
                    style_owner=self.mapboxStyleOwnerLineEdit.text().strip(),
                    style_id=self.mapboxStyleIdLineEdit.text().strip(),
                    tile_mode=TILE_MODE_VECTOR,
                )
            except Exception:
                pass  # fall back to raster if vector fails

        self._set_atlas_export_running(True)
        self._set_atlas_pdf_status(
            f"Exporting atlas ({self.atlas_layer.featureCount()} pages)…"
        )
        self._set_status("Generating atlas PDF…")

        self._atlas_export_task = AtlasExportTask(
            atlas_layer=self.atlas_layer,
            output_path=output_path,
            on_finished=self._on_atlas_export_finished,
            restore_tile_mode=pre_export_tile_mode,
            layer_manager=self.layer_manager,
            preset_name=self.backgroundPresetComboBox.currentText(),
            access_token=self.mapboxAccessTokenLineEdit.text().strip(),
            style_owner=self.mapboxStyleOwnerLineEdit.text().strip(),
            style_id=self.mapboxStyleIdLineEdit.text().strip(),
            background_enabled=self.backgroundMapCheckBox.isChecked(),
        )
        QgsApplication.taskManager().addTask(self._atlas_export_task)

    def _set_atlas_export_running(self, running: bool) -> None:
        self.generateAtlasPdfButton.setText(
            "Cancel export" if running else "Generate Atlas PDF"
        )
        self.loadButton.setEnabled(not running)
        self.loadLayersButton.setEnabled(not running)
        self.refreshButton.setEnabled(not running)

    def _on_atlas_export_finished(
        self,
        output_path,
        error,
        cancelled,
        page_count,
    ) -> None:
        """Called on the main thread when the atlas export task completes."""
        self._atlas_export_task = None
        self._set_atlas_export_running(False)

        if cancelled:
            self._set_atlas_pdf_status("Atlas PDF export cancelled.")
            self._set_status("Atlas PDF export cancelled.")
            return

        if error is not None:
            self._show_error("Atlas PDF export failed", error)
            self._set_atlas_pdf_status(f"Export failed: {error}")
            self._set_status("Atlas PDF export failed.")
            return

        status = (
            f"Atlas PDF exported: {page_count} page(s) → {output_path}"
        )
        self._set_atlas_pdf_status(status)
        self._set_status(status)

    def _set_atlas_pdf_status(self, text: str) -> None:
        label = getattr(self, "atlasPdfStatusLabel", None)
        if label is not None:
            label.setText(text)

    def _set_status(self, text):
        self.statusLabel.setText(text)

    def _show_info(self, title, message):
        QMessageBox.information(self, title, message)

    def _show_error(self, title, message):
        QMessageBox.critical(self, title, message)
