import logging
import os
from dataclasses import replace
from datetime import date

logger = logging.getLogger(__name__)

from qgis.core import QgsApplication, QgsProject
from qgis.PyQt import uic
from qgis.PyQt.QtCore import QDate, Qt, QUrl
from qgis.PyQt.QtGui import QDesktopServices
from qgis.PyQt.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QDockWidget,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .activities.domain.activity_query import (
    DEFAULT_SORT_LABEL,
    DETAILED_ROUTE_FILTER_ANY,
    DETAILED_ROUTE_FILTER_MISSING,
    DETAILED_ROUTE_FILTER_PRESENT,
    SORT_OPTIONS,
    filter_activities,
)
from .activities.application import (
    ActivityPreviewRequest,
    ActivitySelectionState,
    ActivityTypeOptionsResult,
    build_activity_preview,
    build_activity_selection_state,
    build_activity_type_options_from_activities,
    build_activity_type_options_from_records,
)
from .activities.application.layer_summary import (
    build_cleared_activities_summary,
    build_last_sync_summary,
    build_loaded_activities_summary,
    build_stored_activities_summary,
)
from .activities.application.load_workflow import LoadWorkflowError
from .activities.application.store_task import build_store_task
from .analysis.infrastructure.activity_heatmap_layer import (
    ACTIVITY_HEATMAP_LAYER_NAME,
)
from .analysis.infrastructure.frequent_start_points_layer import (
    FREQUENT_STARTING_POINTS_LAYER_NAME,
)
from .atlas.export_service import (
    AtlasExportResult,
    AtlasExportService,
)
from .atlas.profile_style import build_native_profile_plot_style_from_settings
from .ui.application import (
    ApplyVisualizationAction,
    DockActionDispatcher,
    RunAnalysisAction,
)
from .ui.contextual_help import ContextualHelpBinder, build_dock_help_entries
from .detailed_route_strategy import (
    DETAILED_ROUTE_STRATEGY_MISSING,
    detailed_route_strategy_labels,
)
from .mapbox_config import (
    TILE_MODES,
    MapboxConfigError,
    background_preset_names,
    preset_requires_custom_style,
)
from .visualization.application import BackgroundConfig, LayerRefs
from .atlas.layout_metrics import BUILTIN_ATLAS_MAP_TARGET_ASPECT_RATIO
from .providers.domain.provider import ProviderError
from .providers.infrastructure.strava_provider import StravaProvider
from .visualization.application import DEFAULT_TEMPORAL_MODE_LABEL, temporal_mode_labels
from .ui.dockwidget_dependencies import DockWidgetDependencies, build_dockwidget_dependencies
from .ui.dock_startup_coordinator import DockStartupCoordinator
from .ui.workflow_section_coordinator import WorkflowSectionCoordinator
from .configuration.application.connection_status import build_strava_connection_status
from .configuration.application.dock_settings_bindings import build_dock_settings_bindings
from .configuration.application.ui_settings_binding import load_bindings, save_bindings

FORM_CLASS, _ = uic.loadUiType(
    __import__("os").path.join(__import__("os").path.dirname(__file__), "qfit_dockwidget_base.ui")
)


class QfitDockWidget(QDockWidget, FORM_CLASS):
    SETTINGS_PREFIX = "qfit"
    LEGACY_SETTINGS_PREFIX = "QFIT"
    DEFAULT_DOCK_FEATURES = (
        QDockWidget.DockWidgetClosable
        | QDockWidget.DockWidgetMovable
        | QDockWidget.DockWidgetFloatable
    )
    STARTUP_ALLOWED_AREAS = Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea

    def __init__(self, iface, parent=None, dependencies: DockWidgetDependencies | None = None):
        if parent is None and iface is not None and hasattr(iface, "mainWindow"):
            parent = iface.mainWindow()
        super().__init__(parent)
        self.iface = iface
        self.activities = []
        self.output_path = None
        self.activities_layer = None
        self.starts_layer = None
        self.points_layer = None
        self.atlas_layer = None
        self.background_layer = None
        self.analysis_layer = None
        self.last_fetch_context = {}
        self._fetch_task = None
        self._store_task = None
        self._atlas_export_task = None
        self._dependencies = dependencies or build_dockwidget_dependencies(iface)
        self._bind_dependencies(self._dependencies)
        self.setupUi(self)
        self._workflow_section_coordinator = WorkflowSectionCoordinator(self)
        self._dock_startup_coordinator = DockStartupCoordinator(
            self,
            workflow_section_coordinator=self._workflow_section_coordinator,
        )
        self._startup_result = self._dock_startup_coordinator.run()
        self._dock_action_dispatcher = DockActionDispatcher(
            visual_apply=self.visual_apply,
            save_settings=self._save_settings,
            run_analysis=self._apply_analysis_configuration,
        )

    def _remove_stale_qfit_layers(self):
        """Remove stale qfit project layers before startup signals begin firing."""
        self.project_hygiene_service.remove_stale_qfit_layers()

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
        self.backfillMissingDetailedRoutesButton.clicked.connect(self.on_backfill_missing_detailed_routes_clicked)
        self.loadButton.clicked.connect(self.on_load_clicked)
        self.loadLayersButton.clicked.connect(self.on_load_layers_clicked)
        self.clearDatabaseButton.clicked.connect(self.on_clear_database_clicked)
        self.applyFiltersButton.clicked.connect(self.on_apply_filters_clicked)
        self.runAnalysisButton.clicked.connect(self.on_run_analysis_clicked)
        self.loadBackgroundButton.clicked.connect(self.on_load_background_clicked)
        self.backgroundPresetComboBox.currentTextChanged.connect(self.on_background_preset_changed)
        self.detailedStreamsCheckBox.toggled.connect(self._workflow_section_coordinator.update_detailed_fetch_visibility)
        self.writeActivityPointsCheckBox.toggled.connect(self._workflow_section_coordinator.update_point_sampling_visibility)
        self.advancedFetchGroupBox.toggled.connect(self._workflow_section_coordinator.update_advanced_fetch_visibility)
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
            self.detailedRouteStatusComboBox.currentIndexChanged,
            self.previewSortComboBox.currentTextChanged,
        ]
        for signal in preview_inputs:
            signal.connect(self._refresh_activity_preview)

    def _configure_background_preset_options(self):
        self.backgroundPresetComboBox.clear()
        for preset_name in background_preset_names():
            self.backgroundPresetComboBox.addItem(preset_name)

    def _configure_detailed_route_filter_options(self):
        legacy_checkbox = getattr(self, "detailedOnlyCheckBox", None)
        combo = getattr(self, "detailedRouteStatusComboBox", None)
        if combo is None:
            combo = QComboBox(legacy_checkbox.parentWidget())
            combo.setObjectName("detailedRouteStatusComboBox")
            layout = legacy_checkbox.parentWidget().layout()
            if layout is not None and hasattr(layout, "replaceWidget"):
                layout.replaceWidget(legacy_checkbox, combo)
            legacy_checkbox.hide()
            self.detailedRouteStatusComboBox = combo
        combo.clear()
        combo.addItem("Any routes", DETAILED_ROUTE_FILTER_ANY)
        combo.addItem("Detailed routes only", DETAILED_ROUTE_FILTER_PRESENT)
        combo.addItem("Missing detailed routes", DETAILED_ROUTE_FILTER_MISSING)
        combo.setToolTip("Filter activities by detailed-route availability")
        self.tileModeComboBox.clear()
        for mode in TILE_MODES:
            self.tileModeComboBox.addItem(mode)

    def _configure_detailed_route_strategy_options(self):
        combo = getattr(self, "detailedRouteStrategyComboBox", None)
        if combo is None:
            return
        combo.clear()
        for label in detailed_route_strategy_labels():
            combo.addItem(label)

    def _configure_preview_sort_options(self):
        self.previewSortComboBox.clear()
        for label in SORT_OPTIONS:
            self.previewSortComboBox.addItem(label)

    def _configure_temporal_mode_options(self):
        outer_layout = self.temporalModeLabel.parentWidget().layout()
        if hasattr(outer_layout, "setSpacing"):
            outer_layout.setSpacing(6)
        if isinstance(outer_layout, QGridLayout):
            outer_layout.setSpacing(6)
        self.temporalModeComboBox.setSizeAdjustPolicy(
            QComboBox.AdjustToMinimumContentsLengthWithIcon
        )
        self.temporalModeComboBox.setMinimumContentsLength(10)
        self.temporalHelpLabel.setMargin(2)
        self.temporalModeComboBox.clear()
        for label in temporal_mode_labels():
            self.temporalModeComboBox.addItem(label)
        self.temporalModeComboBox.setCurrentText(DEFAULT_TEMPORAL_MODE_LABEL)
        self.temporalModeComboBox.setMinimumContentsLength(10)
        self.temporalModeComboBox.hide()
        self.temporalModeLabel.hide()
        self.temporalHelpLabel.hide()
        temporal_row = getattr(self, "analysisTemporalModeRow", None)
        if temporal_row is not None:
            temporal_row.hide()

    def _configure_analysis_mode_options(self):
        content_widget = getattr(self, "analysisSectionContentWidget", self.analysisWorkflowGroupBox)
        content_layout = content_widget.layout() if content_widget is not None else None

        row = QWidget(content_widget or self.analysisWorkflowGroupBox)
        row.setObjectName("analysisModeRow")
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        label = QLabel("Analysis", row)
        label.setObjectName("analysisModeLabel")
        layout.addWidget(label)

        combo = QComboBox(row)
        combo.setObjectName("analysisModeComboBox")
        combo.addItem("None")
        combo.addItem("Most frequent starting points")
        layout.addWidget(combo)

        button = QPushButton("Run analysis", row)
        button.setObjectName("runAnalysisButton")
        layout.addWidget(button)
        layout.addStretch(1)

        if content_layout is not None:
            content_layout.insertWidget(0, row)
        else:
            self.analysisWorkflowLayout.insertWidget(0, row)
        self.analysisModeLabel = label
        self.analysisModeComboBox = combo
        self.runAnalysisButton = button

    def _bind_dependencies(self, dependencies: DockWidgetDependencies) -> None:
        self.settings = dependencies.settings
        self.sync_controller = dependencies.sync_controller
        self.analysis_controller = dependencies.analysis_controller
        self.atlas_export_controller = dependencies.atlas_export_controller
        self.atlas_export_use_case = dependencies.atlas_export_use_case
        self.layer_gateway = dependencies.layer_gateway
        self.background_controller = dependencies.background_controller
        self.project_hygiene_service = dependencies.project_hygiene_service
        self.load_workflow = dependencies.load_workflow
        self.visual_apply = dependencies.visual_apply
        self.atlas_export_service = dependencies.atlas_export_service
        self.fetch_result_service = dependencies.fetch_result_service
        self.cache = dependencies.cache

    @staticmethod
    def _set_combo_value(combo_box, value, default_text) -> None:
        selected = default_text if value in (None, "") else str(value)
        index = combo_box.findText(selected)
        if index < 0:
            index = combo_box.findText(default_text)
        combo_box.setCurrentIndex(max(index, 0))

    @staticmethod
    def _set_bool_value(check_box, value, default: bool) -> None:
        if isinstance(value, str):
            check_box.setChecked(value.lower() in ("1", "true", "yes", "on"))
            return
        if value is None:
            check_box.setChecked(default)
            return
        check_box.setChecked(bool(value))

    @staticmethod
    def _set_int_value(spin_box, value, default: int) -> None:
        try:
            spin_box.setValue(int(value))
        except (TypeError, ValueError):
            spin_box.setValue(int(default))

    @staticmethod
    def _set_combo_data_value(combo_box, value, default: str) -> None:
        target = value if value not in (None, "") else default
        index = combo_box.findData(target)
        if index < 0:
            index = combo_box.findData(default)
        if index < 0:
            index = 0
        combo_box.setCurrentIndex(index)

    @staticmethod
    def _set_float_value(spin_box, value, default: float) -> None:
        try:
            spin_box.setValue(float(value))
        except (TypeError, ValueError):
            spin_box.setValue(float(default))

    def _set_atlas_target_aspect_ratio_value(self, value) -> None:
        try:
            aspect_ratio = float(value)
        except (TypeError, ValueError):
            aspect_ratio = BUILTIN_ATLAS_MAP_TARGET_ASPECT_RATIO
        if aspect_ratio <= 0:
            aspect_ratio = BUILTIN_ATLAS_MAP_TARGET_ASPECT_RATIO
        self.atlasTargetAspectRatioSpinBox.setValue(aspect_ratio)

    def _default_output_path(self) -> str:
        return os.path.join(os.path.expanduser("~"), "qfit_activities.gpkg")

    def _default_atlas_pdf_path(self) -> str:
        return os.path.join(os.path.expanduser("~"), "qfit_atlas.pdf")

    def _load_settings(self):
        load_bindings(build_dock_settings_bindings(self), self.settings)
        self.authCodeLineEdit.setText("")
        self._sync_background_style_fields(self.backgroundPresetComboBox.currentText(), force=False)

        self._update_last_sync_summary()

    def _save_settings(self):
        save_bindings(build_dock_settings_bindings(self), self.settings)


    def _set_default_dates(self):
        if not self.dateFromEdit.date().isValid():
            self.dateFromEdit.setDate(QDate.currentDate().addYears(-1))
        if not self.dateToEdit.date().isValid():
            self.dateToEdit.setDate(QDate.currentDate())

    def on_background_preset_changed(self, preset_name):
        self._sync_background_style_fields(preset_name, force=True)
        self._workflow_section_coordinator.update_mapbox_advanced_visibility(preset_name)

    def on_load_background_clicked(self):
        self._save_settings()
        try:
            request = self.background_controller.build_load_request(
                enabled=self.backgroundMapCheckBox.isChecked(),
                preset_name=self.backgroundPresetComboBox.currentText(),
                access_token=self._mapbox_access_token(),
                style_owner=self.mapboxStyleOwnerLineEdit.text().strip(),
                style_id=self.mapboxStyleIdLineEdit.text().strip(),
                tile_mode=self.tileModeComboBox.currentText(),
            )
            result = self.background_controller.load_background_request(request)
            self.background_layer = result.layer
        except (MapboxConfigError, RuntimeError) as exc:
            self._show_error("Background map failed", str(exc))
            self._set_status("Background map could not be updated")
            return

        self._set_status(result.status)

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
            authorize_request = self.sync_controller.build_authorize_request(
                client_id=self.clientIdLineEdit.text().strip(),
                client_secret=self.clientSecretLineEdit.text().strip(),
                refresh_token=self.refreshTokenLineEdit.text().strip(),
                cache=self.cache,
                redirect_uri=self._redirect_uri(),
            )
            url = self.sync_controller.build_authorize_url(authorize_request)
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
            exchange_request = self.sync_controller.build_exchange_code_request(
                client_id=self.clientIdLineEdit.text().strip(),
                client_secret=self.clientSecretLineEdit.text().strip(),
                refresh_token=self.refreshTokenLineEdit.text().strip(),
                cache=self.cache,
                authorization_code=authorization_code,
                redirect_uri=self._redirect_uri(),
            )
            payload = self.sync_controller.exchange_code_for_tokens(exchange_request)
            refresh_token = payload["refresh_token"]
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

        self._start_fetch(
            detailed_route_strategy=self.detailedRouteStrategyComboBox.currentText(),
            status_text="Fetching activities from Strava…",
        )

    def on_backfill_missing_detailed_routes_clicked(self):
        if self._fetch_task is not None:
            return

        self._start_fetch(
            use_detailed_streams=True,
            detailed_route_strategy=DETAILED_ROUTE_STRATEGY_MISSING,
            status_text="Backfilling missing detailed routes from Strava…",
        )

    def _start_fetch(self, detailed_route_strategy, status_text, use_detailed_streams=None):
        self._save_settings()
        advanced_fetch_enabled = self.advancedFetchGroupBox.isChecked()
        if use_detailed_streams is None:
            use_detailed_streams = self.detailedStreamsCheckBox.isChecked() if advanced_fetch_enabled else False
        per_page = self.perPageSpinBox.value() if advanced_fetch_enabled else 200
        max_pages = self.maxPagesSpinBox.value() if advanced_fetch_enabled else 0
        max_detailed_activities = (
            self.maxDetailedActivitiesSpinBox.value()
            if advanced_fetch_enabled or use_detailed_streams
            else 25
        )
        try:
            fetch_request = self.sync_controller.build_fetch_task_request(
                client_id=self.clientIdLineEdit.text().strip(),
                client_secret=self.clientSecretLineEdit.text().strip(),
                refresh_token=self.refreshTokenLineEdit.text().strip(),
                cache=self.cache,
                per_page=per_page,
                max_pages=max_pages,
                use_detailed_streams=use_detailed_streams,
                max_detailed_activities=max_detailed_activities,
                detailed_route_strategy=detailed_route_strategy,
                on_finished=self._on_fetch_finished,
            )
            self._fetch_task = self.sync_controller.build_fetch_task(fetch_request)
        except ProviderError as exc:
            self._show_error("Strava import failed", str(exc))
            self._set_status("Strava fetch failed")
            return

        self._set_fetch_running(True)
        self._set_status(status_text)
        QgsApplication.taskManager().addTask(self._fetch_task)

    def _set_fetch_running(self, running):
        """Toggle UI state while a background fetch is in progress."""
        self.refreshButton.setText("Cancel" if running else "Fetch activities")
        self.backfillMissingDetailedRoutesButton.setEnabled(not running)
        self.exchangeCodeButton.setEnabled(not running)
        self.openAuthorizeButton.setEnabled(not running)

    def _on_fetch_finished(self, activities, error, cancelled, provider):
        """Called on the main thread when the background fetch completes."""
        self._fetch_task = None
        self._set_fetch_running(False)

        fetch_request = self.fetch_result_service.build_request(
            activities=activities,
            error=error,
            cancelled=cancelled,
            provider=provider,
        )
        result = self.fetch_result_service.build_result_request(fetch_request)

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
        if self._store_task is not None:
            self._set_status("Store already in progress...")
            return

        self._save_settings()
        try:
            request = self.load_workflow.build_write_request(
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

        self._store_task = build_store_task(
            self.load_workflow,
            request,
            on_finished=self._handle_store_task_finished,
        )
        self.loadButton.setEnabled(False)
        self.loadButton.setText("Store in progress...")
        self._set_status("Store started...")
        QgsApplication.taskManager().addTask(self._store_task)

    def _handle_store_task_finished(self, result, error_message, cancelled):
        self._store_task = None
        self.loadButton.setEnabled(True)
        self.loadButton.setText("Store activities")

        if cancelled:
            self._set_status("Store cancelled")
            return
        if error_message:
            _msg = "GeoPackage export failed"
            self._show_error(_msg, error_message)
            self._set_status(_msg)
            return
        if result is None:
            self._set_status("GeoPackage export failed")
            return

        self.output_path = result.output_path
        self._update_stored_activities_summary(result.total_stored)
        self._set_status(result.status)

    def on_load_layers_clicked(self):
        """Load an existing GeoPackage into QGIS without fetching from Strava."""
        self._save_settings()
        try:
            request = self.load_workflow.build_load_existing_request(
                self.outputPathLineEdit.text().strip(),
            )
            result = self.load_workflow.load_existing_request(request)
        except LoadWorkflowError as exc:
            self._show_error("GeoPackage not found", str(exc))
            return
        except (RuntimeError, OSError) as exc:
            _msg = "Load activity layers failed"
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

        self._update_loaded_activities_summary(result.total_stored)
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
            "Clear database",
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

        try:
            request = self.load_workflow.build_clear_database_request(
                output_path=output_path,
                layers=[
                    self.activities_layer,
                    self.starts_layer,
                    self.points_layer,
                    self.atlas_layer,
                ],
            )
            result = self.load_workflow.clear_database_request(request)
        except LoadWorkflowError as exc:
            self._show_error("No database path", str(exc))
            return
        except (RuntimeError, OSError) as exc:
            self._show_error("Could not delete database", str(exc))
            self._set_status("Failed to delete the GeoPackage file")
            return

        self.activities_layer = None
        self.starts_layer = None
        self.points_layer = None
        self.atlas_layer = None
        self._clear_analysis_layer()
        self.activities = []
        self.output_path = None
        self.last_fetch_context = {}

        self._update_cleared_activities_summary()
        self._set_status(result.status)

    def on_apply_filters_clicked(self):
        self._dispatch_dock_action(ApplyVisualizationAction)

    def on_run_analysis_clicked(self):
        self._dispatch_dock_action(RunAnalysisAction)

    def _dispatch_dock_action(self, action_type):
        action = self._build_visual_workflow_action(action_type)
        if not action.layers.has_any():
            return

        result = self._dock_action_dispatcher.dispatch(action)
        if result.unsupported_reason:
            self._set_status(result.unsupported_reason)
            return
        if result.background_error:
            self._show_error("Background map failed", result.background_error)
        if result.background_layer is not None:
            self.background_layer = result.background_layer
        if result.status:
            self._set_status(result.status)

    def _build_visual_workflow_action(self, action_type):
        selection_state = self._current_activity_selection_state()

        return action_type(
            layers=LayerRefs(
                activities=self.activities_layer,
                starts=self.starts_layer,
                points=self.points_layer,
                atlas=self.atlas_layer,
            ),
            selection_state=selection_state,
            style_preset=self.stylePresetComboBox.currentText(),
            temporal_mode=DEFAULT_TEMPORAL_MODE_LABEL,
            background_config=BackgroundConfig(
                enabled=self.backgroundMapCheckBox.isChecked(),
                preset_name=self.backgroundPresetComboBox.currentText(),
                access_token=self._mapbox_access_token(),
                style_owner=self.mapboxStyleOwnerLineEdit.text().strip(),
                style_id=self.mapboxStyleIdLineEdit.text().strip(),
                tile_mode=self.tileModeComboBox.currentText(),
            ),
            apply_subset_filters=True,
            analysis_mode=self.analysisModeComboBox.currentText(),
            starts_layer=self.starts_layer,
        )

    def _run_selected_analysis(self, analysis_mode, starts_layer, selection_state=None):
        request = self.analysis_controller.build_request(
            analysis_mode=analysis_mode,
            activities_layer=getattr(self, "activities_layer", None),
            starts_layer=starts_layer,
            points_layer=getattr(self, "points_layer", None),
            selection_state=selection_state,
        )
        result = self.analysis_controller.run_request(request)
        if result.layer is None:
            return result.status

        QgsProject.instance().addMapLayer(result.layer, False)
        QgsProject.instance().layerTreeRoot().insertLayer(0, result.layer)
        self.analysis_layer = result.layer
        return result.status

    def _apply_visual_configuration(self, apply_subset_filters):
        action = replace(
            self._build_visual_workflow_action(ApplyVisualizationAction),
            apply_subset_filters=apply_subset_filters,
        )
        result = self._dock_action_dispatcher.dispatch(action)
        if result.background_error:
            self._show_error("Background map failed", result.background_error)
        if result.background_layer is not None:
            self.background_layer = result.background_layer
        return result.status

    def _apply_analysis_configuration(
        self,
        analysis_mode=None,
        starts_layer=None,
        selection_state=None,
    ):
        self._clear_analysis_layer()

        current_mode = analysis_mode or self.analysisModeComboBox.currentText()
        current_starts_layer = (
            starts_layer if starts_layer is not None else getattr(self, "starts_layer", None)
        )
        return self._run_selected_analysis(
            current_mode,
            current_starts_layer,
            selection_state or self._current_activity_selection_state(),
        )

    def _clear_analysis_layer(self):
        project = QgsProject.instance()
        if self.analysis_layer is not None:
            try:
                project.removeMapLayer(self.analysis_layer.id())
            except RuntimeError:
                logger.debug("Failed to remove analysis layer", exc_info=True)
            self.analysis_layer = None

        analysis_layer_names = {
            FREQUENT_STARTING_POINTS_LAYER_NAME,
            ACTIVITY_HEATMAP_LAYER_NAME,
        }
        for layer in tuple(project.mapLayers().values()):
            if layer.name() not in analysis_layer_names:
                continue
            try:
                project.removeMapLayer(layer.id())
            except RuntimeError:
                logger.debug("Failed to remove stale analysis layer", exc_info=True)

    def _current_activity_preview_request(self):
        return ActivityPreviewRequest(
            activities=self.activities,
            activity_type=self.activityTypeComboBox.currentText() or "All",
            date_from=self.dateFromEdit.date().toString("yyyy-MM-dd") if self.dateFromEdit.date().isValid() else None,
            date_to=self.dateToEdit.date().toString("yyyy-MM-dd") if self.dateToEdit.date().isValid() else None,
            min_distance_km=self.minDistanceSpinBox.value(),
            max_distance_km=self.maxDistanceSpinBox.value(),
            search_text=self.activitySearchLineEdit.text().strip(),
            detailed_route_filter=self.detailedRouteStatusComboBox.currentData(),
            sort_label=self.previewSortComboBox.currentText() or DEFAULT_SORT_LABEL,
        )

    def _current_activity_selection_state(self):
        return build_activity_selection_state(self._current_activity_preview_request())

    def _current_activity_query(self):
        return self._current_activity_selection_state().query

    def _refresh_activity_preview(self):
        preview = build_activity_preview(self._current_activity_preview_request())
        self.querySummaryLabel.setText(preview.query_summary_text)
        self.activityPreviewPlainTextEdit.setPlainText(preview.preview_text)
        return preview.fetched_activities

    def _update_cleared_activities_summary(self):
        self.countLabel.setText(build_cleared_activities_summary())

    def _update_last_sync_summary(self):
        summary = build_last_sync_summary(
            last_sync_date=self.settings.get("last_sync_date", None),
        )
        if summary:
            self.countLabel.setText(summary)

    def _update_loaded_activities_summary(self, total_activities):
        self.countLabel.setText(
            build_loaded_activities_summary(
                total_activities=total_activities,
                last_sync_date=self.settings.get("last_sync_date", "unknown"),
            )
        )

    def _update_stored_activities_summary(self, total_activities):
        self.countLabel.setText(
            build_stored_activities_summary(
                total_activities=total_activities,
                last_sync_date=self.settings.get("last_sync_date", date.today().isoformat()),
            )
        )

    def _filtered_activities(self):
        return filter_activities(self.activities, self._current_activity_selection_state().query)


    def _redirect_uri(self):
        return self.redirectUriLineEdit.text().strip() or StravaProvider.DEFAULT_REDIRECT_URI

    def _mapbox_access_token(self):
        return (self.settings.get("mapbox_access_token", "") or "").strip()

    def _qdate_to_date(self, value):
        return date(value.year(), value.month(), value.day())

    def _apply_activity_type_options(self, result: ActivityTypeOptionsResult) -> None:
        self.activityTypeComboBox.clear()
        for value in result.options:
            self.activityTypeComboBox.addItem(value)
        index = self.activityTypeComboBox.findText(result.selected_value)
        self.activityTypeComboBox.setCurrentIndex(max(index, 0))

    def _populate_activity_types(self):
        self._apply_activity_type_options(
            build_activity_type_options_from_activities(
                self.activities,
                current_value=self.activityTypeComboBox.currentText() or "All",
            )
        )

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
            result = build_activity_type_options_from_records(
                self.activities_layer.getFeatures(),
                field_names,
                current_value=current_value,
            )
        except (RuntimeError, KeyError):
            logger.debug("Failed to populate activity types from layer", exc_info=True)
            return
        if result is None:
            return
        self._apply_activity_type_options(result)


    def _update_connection_status(self):
        self.connectionStatusLabel.setText(
            build_strava_connection_status(
                client_id=self.clientIdLineEdit.text(),
                client_secret=self.clientSecretLineEdit.text(),
                refresh_token=self.refreshTokenLineEdit.text(),
            )
        )

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

        export_command = self.atlas_export_use_case.build_command(
            atlas_layer=self.atlas_layer,
            selection_state=self._current_activity_selection_state(),
            output_path=self.atlasPdfPathLineEdit.text().strip(),
            on_finished=self._on_atlas_export_finished,
            pre_export_tile_mode=self.tileModeComboBox.currentText(),
            preset_name=self.backgroundPresetComboBox.currentText(),
            access_token=self._mapbox_access_token(),
            style_owner=self.mapboxStyleOwnerLineEdit.text().strip(),
            style_id=self.mapboxStyleIdLineEdit.text().strip(),
            background_enabled=self.backgroundMapCheckBox.isChecked(),
            profile_plot_style=build_native_profile_plot_style_from_settings(self.settings),
        )
        prepared_export = self.atlas_export_use_case.prepare_export(export_command)
        if prepared_export.path_changed:
            self.atlasPdfPathLineEdit.setText(prepared_export.output_path)
        if not prepared_export.is_ready:
            if prepared_export.pdf_status is not None:
                self._set_atlas_pdf_status(prepared_export.pdf_status)
            if prepared_export.main_status is not None:
                self._set_status(prepared_export.main_status)
            self._show_error(prepared_export.error_title, prepared_export.error_message)
            return

        self._save_settings()
        self._atlas_export_task = self.atlas_export_use_case.start_export(
            prepared_export,
            export_command,
        )

        self._set_atlas_export_running(True)
        self._set_atlas_pdf_status(
            f"Exporting atlas ({self.atlas_layer.featureCount()} pages)…"
        )
        self._set_status("Generating atlas PDF…")

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

        result = self.atlas_export_use_case.finish_export(output_path, error, cancelled, page_count)
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
