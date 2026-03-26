import logging
import os
from datetime import date

logger = logging.getLogger(__name__)

from qgis.core import QgsApplication, QgsProject
from qgis.PyQt import uic
from qgis.PyQt.QtCore import QDate, QStandardPaths, QUrl
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
from .atlas.export_controller import AtlasExportController, AtlasExportValidationError
from .atlas.export_service import AtlasExportResult, AtlasExportService
from .background_map_controller import BackgroundMapController
from .contextual_help import ContextualHelpBinder, build_dock_help_entries
from .layer_manager import LayerManager
from .load_workflow import LoadWorkflowError, LoadWorkflowService
from .mapbox_config import (
    DEFAULT_BACKGROUND_PRESET,
    TILE_MODES,
    MapboxConfigError,
    background_preset_names,
    preset_requires_custom_style,
)
from .visual_apply import BackgroundConfig, LayerRefs, VisualApplyService
from .fetch_result_service import FetchResultService
from .fetch_task import FetchTask
from .atlas.export_task import BUILTIN_ATLAS_MAP_TARGET_ASPECT_RATIO
from .qfit_cache import QfitCache
from .provider import ProviderError
from .strava_provider import StravaProvider
from .settings_service import SettingsService
from .sync_controller import SyncController
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
        self.settings = SettingsService()
        self.sync_controller = SyncController()
        self.atlas_export_controller = AtlasExportController()
        self.layer_manager = LayerManager(iface)
        self.background_controller = BackgroundMapController(self.layer_manager)
        self.load_workflow = LoadWorkflowService(self.layer_manager)
        self.visual_apply = VisualApplyService(self.layer_manager)
        self.atlas_export_service = AtlasExportService(self.layer_manager)
        self.fetch_result_service = FetchResultService(self.sync_controller)
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
        s = self.settings
        self.clientIdLineEdit.setText(s.get("client_id", ""))
        self.clientSecretLineEdit.setText(s.get("client_secret", ""))
        self.redirectUriLineEdit.setText(
            s.get("redirect_uri", StravaProvider.DEFAULT_REDIRECT_URI)
        )
        self.authCodeLineEdit.setText("")
        self.refreshTokenLineEdit.setText(s.get("refresh_token", ""))
        default_output = s.get(
            "output_path",
            os.path.join(os.path.expanduser("~"), "qfit_activities.gpkg"),
        )
        self.outputPathLineEdit.setText(default_output)
        self.perPageSpinBox.setValue(int(s.get("per_page", 200)))
        self.maxPagesSpinBox.setValue(int(s.get("max_pages", 0)))
        self.detailedStreamsCheckBox.setChecked(s.get_bool("use_detailed_streams", False))
        self.maxDetailedActivitiesSpinBox.setValue(int(s.get("max_detailed_activities", 25)))
        self.writeActivityPointsCheckBox.setChecked(s.get_bool("write_activity_points", False))
        self.pointSamplingStrideSpinBox.setValue(int(s.get("point_sampling_stride", 5)))
        self.activitySearchLineEdit.setText(s.get("activity_search_text", ""))
        self.maxDistanceSpinBox.setValue(float(s.get("max_distance_km", 0.0)))
        self.detailedOnlyCheckBox.setChecked(s.get_bool("detailed_only", False))
        self.backgroundMapCheckBox.setChecked(s.get_bool("use_background_map", False))
        self.mapboxAccessTokenLineEdit.setText(s.get("mapbox_access_token", ""))
        self.mapboxStyleOwnerLineEdit.setText(s.get("mapbox_style_owner", "mapbox"))
        self.mapboxStyleIdLineEdit.setText(s.get("mapbox_style_id", ""))
        self.atlasMarginPercentSpinBox.setValue(float(s.get("atlas_margin_percent", 8.0)))
        self.atlasMinExtentSpinBox.setValue(float(s.get("atlas_min_extent_degrees", 0.01)))
        stored_atlas_target_aspect_ratio = float(
            s.get("atlas_target_aspect_ratio", BUILTIN_ATLAS_MAP_TARGET_ASPECT_RATIO)
        )
        if stored_atlas_target_aspect_ratio <= 0:
            stored_atlas_target_aspect_ratio = BUILTIN_ATLAS_MAP_TARGET_ASPECT_RATIO
        self.atlasTargetAspectRatioSpinBox.setValue(stored_atlas_target_aspect_ratio)
        default_pdf_path = s.get(
            "atlas_pdf_path",
            os.path.join(os.path.expanduser("~"), "qfit_atlas.pdf"),
        )
        self.atlasPdfPathLineEdit.setText(default_pdf_path)

        temporal_mode = s.get("temporal_mode", DEFAULT_TEMPORAL_MODE_LABEL)
        temporal_mode_index = self.temporalModeComboBox.findText(temporal_mode)
        if temporal_mode_index < 0:
            temporal_mode_index = self.temporalModeComboBox.findText(DEFAULT_TEMPORAL_MODE_LABEL)
        self.temporalModeComboBox.setCurrentIndex(max(temporal_mode_index, 0))

        preset_name = s.get("background_preset", DEFAULT_BACKGROUND_PRESET)
        preset_index = self.backgroundPresetComboBox.findText(preset_name)
        if preset_index < 0:
            preset_index = self.backgroundPresetComboBox.findText(DEFAULT_BACKGROUND_PRESET)
        self.backgroundPresetComboBox.setCurrentIndex(max(preset_index, 0))
        self._sync_background_style_fields(self.backgroundPresetComboBox.currentText(), force=False)

        tile_mode = s.get("tile_mode", TILE_MODE_RASTER)
        tile_mode_index = self.tileModeComboBox.findText(tile_mode)
        self.tileModeComboBox.setCurrentIndex(max(tile_mode_index, 0))

        preview_sort = s.get("preview_sort", DEFAULT_SORT_LABEL)
        preview_sort_index = self.previewSortComboBox.findText(preview_sort)
        if preview_sort_index < 0:
            preview_sort_index = self.previewSortComboBox.findText(DEFAULT_SORT_LABEL)
        self.previewSortComboBox.setCurrentIndex(max(preview_sort_index, 0))

        style_preset = s.get("style_preset", "By activity type")
        style_preset_index = self.stylePresetComboBox.findText(style_preset)
        if style_preset_index < 0:
            style_preset_index = self.stylePresetComboBox.findText("By activity type")
        self.stylePresetComboBox.setCurrentIndex(max(style_preset_index, 0))

        last_sync = s.get("last_sync_date", None)
        if last_sync:
            self.countLabel.setText(f"Last sync: {last_sync}")

    def _save_settings(self):
        s = self.settings
        s.set("client_id", self.clientIdLineEdit.text().strip())
        s.set("client_secret", self.clientSecretLineEdit.text().strip())
        s.set("redirect_uri", self.redirectUriLineEdit.text().strip())
        s.set("refresh_token", self.refreshTokenLineEdit.text().strip())
        s.set("output_path", self.outputPathLineEdit.text().strip())
        s.set("per_page", self.perPageSpinBox.value())
        s.set("max_pages", self.maxPagesSpinBox.value())
        s.set("use_detailed_streams", self.detailedStreamsCheckBox.isChecked())
        s.set("max_detailed_activities", self.maxDetailedActivitiesSpinBox.value())
        s.set("write_activity_points", self.writeActivityPointsCheckBox.isChecked())
        s.set("point_sampling_stride", self.pointSamplingStrideSpinBox.value())
        s.set("activity_search_text", self.activitySearchLineEdit.text().strip())
        s.set("max_distance_km", self.maxDistanceSpinBox.value())
        s.set("detailed_only", self.detailedOnlyCheckBox.isChecked())
        s.set("preview_sort", self.previewSortComboBox.currentText())
        s.set("style_preset", self.stylePresetComboBox.currentText())
        s.set("temporal_mode", self.temporalModeComboBox.currentText())
        s.set("use_background_map", self.backgroundMapCheckBox.isChecked())
        s.set("background_preset", self.backgroundPresetComboBox.currentText())
        s.set("mapbox_access_token", self.mapboxAccessTokenLineEdit.text().strip())
        s.set("mapbox_style_owner", self.mapboxStyleOwnerLineEdit.text().strip())
        s.set("mapbox_style_id", self.mapboxStyleIdLineEdit.text().strip())
        s.set("tile_mode", self.tileModeComboBox.currentText())
        s.set("atlas_margin_percent", self.atlasMarginPercentSpinBox.value())
        s.set("atlas_min_extent_degrees", self.atlasMinExtentSpinBox.value())
        s.set("atlas_target_aspect_ratio", self.atlasTargetAspectRatioSpinBox.value())
        s.set("atlas_pdf_path", self.atlasPdfPathLineEdit.text().strip())


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
            self.background_layer = self.background_controller.load_background(
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
        result = self.background_controller.resolve_style_defaults(
            preset_name,
            current_owner=self.mapboxStyleOwnerLineEdit.text().strip(),
            current_style_id=self.mapboxStyleIdLineEdit.text().strip(),
            force=force,
        )
        if result is not None:
            style_owner, style_id = result
            self.mapboxStyleOwnerLineEdit.setText(style_owner)
            self.mapboxStyleIdLineEdit.setText(style_id)

    def on_open_authorize_clicked(self):
        self._save_settings()
        try:
            client = self.sync_controller.build_strava_provider(
                client_id=self.clientIdLineEdit.text().strip(),
                client_secret=self.clientSecretLineEdit.text().strip(),
                refresh_token=self.refreshTokenLineEdit.text().strip(),
                cache=self.cache,
                require_refresh_token=False,
            )
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
        except ProviderError as exc:
            self._show_error("Strava authorization failed", str(exc))
            self._set_status("Could not start the Strava authorization flow")

    def on_exchange_code_clicked(self):
        self._save_settings()
        authorization_code = self.authCodeLineEdit.text().strip()
        if not authorization_code:
            self._show_error("Missing authorization code", "Paste the code returned by Strava first.")
            return

        try:
            client = self.sync_controller.build_strava_provider(
                client_id=self.clientIdLineEdit.text().strip(),
                client_secret=self.clientSecretLineEdit.text().strip(),
                refresh_token=self.refreshTokenLineEdit.text().strip(),
                cache=self.cache,
                require_refresh_token=False,
            )
            payload = client.exchange_code_for_tokens(
                authorization_code=authorization_code,
                redirect_uri=self._redirect_uri(),
            )
            refresh_token = payload.get("refresh_token")
            if not refresh_token:
                raise ProviderError("Strava returned no refresh token")
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
        except ProviderError as exc:
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
            client = self.sync_controller.build_strava_provider(
                client_id=self.clientIdLineEdit.text().strip(),
                client_secret=self.clientSecretLineEdit.text().strip(),
                refresh_token=self.refreshTokenLineEdit.text().strip(),
                cache=self.cache,
                require_refresh_token=True,
            )
        except ProviderError as exc:
            self._show_error("Strava import failed", str(exc))
            self._set_status("Strava fetch failed")
            return

        # Issue #38: fetch all activities — no date filtering at import time.
        # Date filters are visualization-only (applied post-import to loaded layers).
        self._fetch_task = FetchTask(
            provider=client,
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

    def _on_fetch_finished(self, activities, error, cancelled, provider):
        """Called on the main thread when the background fetch completes."""
        self._fetch_task = None
        self._set_fetch_running(False)

        result = self.fetch_result_service.build_result(
            activities=activities, error=error, cancelled=cancelled,
            provider=provider,
        )

        if cancelled:
            self._set_status(result.status_text)
            return

        if error is not None:
            self._show_error("Strava import failed", error)
            self._set_status(result.status_text)
            return

        self.activities = result.activities
        self.last_fetch_context = result.metadata
        # Persist last sync date
        self.settings.set("last_sync_date", result.today_str)

        self._populate_activity_types()
        self.countLabel.setText(result.count_label_text)
        self._refresh_activity_preview()
        self._set_status(result.status_text)

    def on_load_clicked(self):
        self._save_settings()
        try:
            result = self.load_workflow.write_and_load(
                activities=self.activities,
                output_path=self.outputPathLineEdit.text().strip(),
                write_activity_points=self.writeActivityPointsCheckBox.isChecked(),
                point_stride=self.pointSamplingStrideSpinBox.value(),
                atlas_margin_percent=self.atlasMarginPercentSpinBox.value(),
                atlas_min_extent_degrees=self.atlasMinExtentSpinBox.value(),
                atlas_target_aspect_ratio=self.atlasTargetAspectRatioSpinBox.value(),
                sync_metadata=self.last_fetch_context,
                last_sync_date=self.settings.get("last_sync_date", None),
            )
        except LoadWorkflowError as exc:
            self._show_error("Missing input", str(exc))
            return
        except (RuntimeError, OSError, ValueError) as exc:
            _msg = "GeoPackage export failed"
            logger.exception(_msg)
            self._show_error(_msg, str(exc))
            self._set_status(_msg)
            return

        self.output_path = result.output_path
        self.activities_layer = result.activities_layer
        self.starts_layer = result.starts_layer
        self.points_layer = result.points_layer
        self.atlas_layer = result.atlas_layer

        visual_status = self._apply_visual_configuration(apply_subset_filters=False)
        last_sync = self.settings.get("last_sync_date", date.today().isoformat())
        self.countLabel.setText(
            "{total} activities stored (last sync: {sync_date})".format(
                total=result.total_stored, sync_date=last_sync,
            )
        )
        status = result.status
        if visual_status:
            status = "{status} {visual_status}".format(status=status, visual_status=visual_status)
        self._set_status(status)

    def on_load_layers_clicked(self):
        """Load an existing GeoPackage into QGIS without fetching from Strava."""
        self._save_settings()
        try:
            result = self.load_workflow.load_existing(
                self.outputPathLineEdit.text().strip(),
            )
        except LoadWorkflowError as exc:
            self._show_error("GeoPackage not found", str(exc))
            return
        except (RuntimeError, OSError) as exc:
            _msg = "Load layers failed"
            logger.exception(_msg)
            self._show_error(_msg, str(exc))
            self._set_status(_msg)
            return

        self.output_path = result.output_path
        self.activities_layer = result.activities_layer
        self.starts_layer = result.starts_layer
        self.points_layer = result.points_layer
        self.atlas_layer = result.atlas_layer

        self._populate_activity_types_from_layer()
        visual_status = self._apply_visual_configuration(apply_subset_filters=False)

        last_sync = self.settings.get("last_sync_date", "unknown")
        self.countLabel.setText(
            "{total} activities loaded (last sync: {sync_date})".format(
                total=result.total_stored, sync_date=last_sync,
            )
        )
        status = result.status
        if visual_status:
            status = "{status} {visual_status}".format(status=status, visual_status=visual_status)
        self._set_status(status)

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
                except RuntimeError:
                    logger.debug("Failed to remove layer from project", exc_info=True)

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
        if not has_layers:
            return

        self._save_settings()
        status = self._apply_visual_configuration(apply_subset_filters=True)
        if status:
            self._set_status(status)

    def _apply_visual_configuration(self, apply_subset_filters):
        filtered_activities = self._refresh_activity_preview()
        query = self._current_activity_query()

        layers = LayerRefs(
            activities=self.activities_layer,
            starts=self.starts_layer,
            points=self.points_layer,
            atlas=self.atlas_layer,
        )
        bg_config = BackgroundConfig(
            enabled=self.backgroundMapCheckBox.isChecked(),
            preset_name=self.backgroundPresetComboBox.currentText(),
            access_token=self.mapboxAccessTokenLineEdit.text().strip(),
            style_owner=self.mapboxStyleOwnerLineEdit.text().strip(),
            style_id=self.mapboxStyleIdLineEdit.text().strip(),
            tile_mode=self.tileModeComboBox.currentText(),
        )

        result = self.visual_apply.apply(
            layers=layers,
            query=query,
            style_preset=self.stylePresetComboBox.currentText(),
            temporal_mode=self.temporalModeComboBox.currentText(),
            background_config=bg_config,
            apply_subset_filters=apply_subset_filters,
            filtered_count=len(filtered_activities),
        )

        if self.visual_apply.should_update_background(apply_subset_filters):
            if result.background_error:
                self._show_error("Background map failed", result.background_error)
            self.background_layer = result.background_layer

        return result.status

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


    def _redirect_uri(self):
        return self.redirectUriLineEdit.text().strip() or StravaProvider.DEFAULT_REDIRECT_URI

    def _qdate_to_date(self, value):
        return date(value.year(), value.month(), value.day())

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
        except (RuntimeError, KeyError):
            logger.debug("Failed to populate activity types from layer", exc_info=True)
            return
        self.activityTypeComboBox.clear()
        self.activityTypeComboBox.addItem("All")
        for value in values:
            self.activityTypeComboBox.addItem(value)
        index = self.activityTypeComboBox.findText(current_value)
        self.activityTypeComboBox.setCurrentIndex(max(index, 0))


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

        try:
            self.atlas_export_controller.validate_atlas_layer(self.atlas_layer)
        except AtlasExportValidationError as exc:
            self._show_error("Atlas export error", str(exc))
            return

        try:
            output_path, changed = self.atlas_export_controller.normalize_pdf_path(
                self.atlasPdfPathLineEdit.text().strip()
            )
        except AtlasExportValidationError as exc:
            self._show_error("Missing output path", str(exc))
            return
        if changed:
            self.atlasPdfPathLineEdit.setText(output_path)

        self._save_settings()

        pre_export_tile_mode = self.tileModeComboBox.currentText()
        self.atlas_export_service.prepare_basemap_for_export(
            pre_export_tile_mode=pre_export_tile_mode,
            background_enabled=self.backgroundMapCheckBox.isChecked(),
            preset_name=self.backgroundPresetComboBox.currentText(),
            access_token=self.mapboxAccessTokenLineEdit.text().strip(),
            style_owner=self.mapboxStyleOwnerLineEdit.text().strip(),
            style_id=self.mapboxStyleIdLineEdit.text().strip(),
        )

        self._set_atlas_export_running(True)
        self._set_atlas_pdf_status(
            f"Exporting atlas ({self.atlas_layer.featureCount()} pages)…"
        )
        self._set_status("Generating atlas PDF…")

        self._atlas_export_task = self.atlas_export_service.build_task(
            atlas_layer=self.atlas_layer,
            output_path=output_path,
            on_finished=self._on_atlas_export_finished,
            pre_export_tile_mode=pre_export_tile_mode,
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

        result = AtlasExportService.build_result(output_path, error, cancelled, page_count)
        self._set_atlas_pdf_status(result.pdf_status)
        self._set_status(result.main_status)
        if result.error is not None and not result.cancelled:
            self._show_error("Atlas PDF export failed", result.error)

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
