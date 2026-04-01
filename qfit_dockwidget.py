import logging
import os
from datetime import date

logger = logging.getLogger(__name__)

from qgis.core import QgsApplication, QgsProject
from qgis.PyQt import uic
from qgis.PyQt.QtCore import QDate, Qt, QUrl
from qgis.PyQt.QtGui import QDesktopServices
from qgis.PyQt.QtWidgets import QApplication, QFileDialog, QDockWidget, QMessageBox, QToolButton, QVBoxLayout, QWidget

from .activities.domain.activity_classification import ordered_canonical_activity_labels
from .activities.domain.activity_query import (
    DEFAULT_SORT_LABEL,
    SORT_OPTIONS,
    ActivityQuery,
    build_preview_lines,
    filter_activities,
    format_summary_text,
    sort_activities,
    summarize_activities,
)
from .atlas.export_controller import AtlasExportValidationError
from .activities.application.load_workflow import LoadWorkflowError
from .atlas.export_service import (
    AtlasExportResult,
    AtlasExportService,
)
from .contextual_help import ContextualHelpBinder, build_dock_help_entries
from .mapbox_config import (
    DEFAULT_BACKGROUND_PRESET,
    TILE_MODE_RASTER,
    TILE_MODES,
    MapboxConfigError,
    background_preset_names,
    preset_requires_custom_style,
)
from .visual_apply import BackgroundConfig, LayerRefs
from .atlas.export_task import BUILTIN_ATLAS_MAP_TARGET_ASPECT_RATIO
from .providers.domain.provider import ProviderError
from .providers.infrastructure.strava_provider import StravaProvider
from .temporal_config import DEFAULT_TEMPORAL_MODE_LABEL, temporal_mode_labels
from .ui.dockwidget_dependencies import DockWidgetDependencies, build_dockwidget_dependencies
from .ui_settings_binding import UIFieldBinding, load_bindings, save_bindings

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
        self.last_fetch_context = {}
        self._fetch_task = None
        self._atlas_export_task = None
        self._dependencies = dependencies or build_dockwidget_dependencies(iface)
        self._bind_dependencies(self._dependencies)
        self.setupUi(self)
        self.setFeatures(self.DEFAULT_DOCK_FEATURES)
        self.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self._configure_starting_sections()
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

    def _configure_starting_sections(self):
        """Hide inline credential entry and start the dock at fetch/import.

        Strava credentials now live in the separate Configuration dialog, so
        the main Activities dock should begin with fetching rather than an
        embedded OAuth/setup flow.
        """
        self.workflowLabel.setText("Workflow: Fetch & store → Visualize → Analyze → Publish")
        self.credentialsGroupBox.hide()
        self.activitiesGroupBox.setTitle("")
        self.activitiesIntroLabel.setText(
            "Fetch your activities from Strava using the credentials saved in qfit → Configuration. "
            "Store or clear the local GeoPackage here too. Filters are applied later in the Visualize step — no re-fetch needed."
        )
        self._move_store_section_under_fetch()
        self._move_load_layers_to_visualize()
        self.outputGroupBox.setTitle("Store / database")
        self.publishGroupBox.setCheckable(False)
        self.publishSettingsWidget.setVisible(True)
        self._install_collapsible_section(self.activitiesGroupBox, "activitiesGroupLayout", "1. Fetch and store activities", "activities")
        self._install_collapsible_section(self.styleGroupBox, "styleGroupLayout", "2. Visualize", "style")
        self._install_collapsible_section(self.analysisWorkflowGroupBox, "analysisWorkflowLayout", "3. Analyze", "analysis")
        self._install_collapsible_section(self.publishGroupBox, "publishGroupLayout", "4. Publish / atlas", "publish")
        self.mapboxAccessTokenLabel.hide()
        self.mapboxAccessTokenLineEdit.hide()

    def _install_collapsible_section(self, group_box, layout_attr: str, title: str, key: str):
        layout = getattr(self, layout_attr, None)
        toggle_attr = f"{key}SectionToggleButton"
        content_attr = f"{key}SectionContentWidget"
        if layout is None or hasattr(self, toggle_attr):
            return

        group_box.setTitle("")

        content_widget = QWidget(group_box)
        content_widget.setObjectName(f"{key}SectionContentWidget")
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(layout.spacing())

        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            child_layout = item.layout()
            spacer = item.spacerItem()
            if widget is not None:
                content_layout.addWidget(widget)
            elif child_layout is not None:
                content_layout.addLayout(child_layout)
            elif spacer is not None:
                content_layout.addItem(spacer)

        toggle = QToolButton(group_box)
        toggle.setObjectName(f"{key}SectionToggleButton")
        toggle.setText(title)
        toggle.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        toggle.setArrowType(Qt.DownArrow)
        toggle.setCheckable(True)
        toggle.setChecked(True)
        toggle.setStyleSheet("QToolButton { border: none; font-weight: bold; }")
        toggle.toggled.connect(lambda expanded, key=key: self._set_section_expanded(key, expanded))

        setattr(self, toggle_attr, toggle)
        setattr(self, content_attr, content_widget)
        layout.addWidget(toggle)
        layout.addWidget(content_widget)

    def _set_section_expanded(self, key: str, expanded: bool):
        toggle = getattr(self, f"{key}SectionToggleButton", None)
        content = getattr(self, f"{key}SectionContentWidget", None)
        if toggle is not None:
            toggle.setArrowType(Qt.DownArrow if expanded else Qt.RightArrow)
        if content is not None:
            content.setVisible(expanded)

    def _move_store_section_under_fetch(self):
        outer_layout = getattr(self, "verticalLayout", None)
        activities_layout = getattr(self, "activitiesGroupLayout", None)
        if outer_layout is None or activities_layout is None:
            return
        if self.outputGroupBox.parent() is self.activitiesGroupBox:
            return
        outer_layout.removeWidget(self.outputGroupBox)
        self.outputGroupBox.setParent(self.activitiesGroupBox)
        activities_layout.addWidget(self.outputGroupBox)

    def _move_load_layers_to_visualize(self):
        output_layout = getattr(self, "outputGroupLayout", None)
        style_layout = getattr(self, "styleGroupLayout", None)
        if output_layout is None or style_layout is None:
            return
        if self.loadLayersButton.parent() is self.styleGroupBox:
            return
        output_layout.removeWidget(self.loadLayersButton)
        self.loadLayersButton.setParent(self.styleGroupBox)
        style_layout.insertWidget(0, self.loadLayersButton)

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

    def _bind_dependencies(self, dependencies: DockWidgetDependencies) -> None:
        self.settings = dependencies.settings
        self.sync_controller = dependencies.sync_controller
        self.atlas_export_controller = dependencies.atlas_export_controller
        self.layer_gateway = dependencies.layer_gateway
        self.background_controller = dependencies.background_controller
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

    def _settings_bindings(self) -> list[UIFieldBinding]:
        default_style_preset = "By activity type"
        return [
            UIFieldBinding("client_id", "", lambda: self.clientIdLineEdit.text().strip(), self.clientIdLineEdit.setText),
            UIFieldBinding("client_secret", "", lambda: self.clientSecretLineEdit.text().strip(), self.clientSecretLineEdit.setText),
            UIFieldBinding(
                "redirect_uri",
                StravaProvider.DEFAULT_REDIRECT_URI,
                lambda: self.redirectUriLineEdit.text().strip(),
                self.redirectUriLineEdit.setText,
            ),
            UIFieldBinding("refresh_token", "", lambda: self.refreshTokenLineEdit.text().strip(), self.refreshTokenLineEdit.setText),
            UIFieldBinding("output_path", self._default_output_path(), lambda: self.outputPathLineEdit.text().strip(), self.outputPathLineEdit.setText),
            UIFieldBinding("per_page", 200, lambda: self.perPageSpinBox.value(), lambda value: self._set_int_value(self.perPageSpinBox, value, 200)),
            UIFieldBinding("max_pages", 0, lambda: self.maxPagesSpinBox.value(), lambda value: self._set_int_value(self.maxPagesSpinBox, value, 0)),
            UIFieldBinding(
                "use_detailed_streams",
                False,
                lambda: self.detailedStreamsCheckBox.isChecked(),
                lambda value: self._set_bool_value(self.detailedStreamsCheckBox, value, False),
            ),
            UIFieldBinding(
                "max_detailed_activities",
                25,
                lambda: self.maxDetailedActivitiesSpinBox.value(),
                lambda value: self._set_int_value(self.maxDetailedActivitiesSpinBox, value, 25),
            ),
            UIFieldBinding(
                "write_activity_points",
                False,
                lambda: self.writeActivityPointsCheckBox.isChecked(),
                lambda value: self._set_bool_value(self.writeActivityPointsCheckBox, value, False),
            ),
            UIFieldBinding(
                "point_sampling_stride",
                5,
                lambda: self.pointSamplingStrideSpinBox.value(),
                lambda value: self._set_int_value(self.pointSamplingStrideSpinBox, value, 5),
            ),
            UIFieldBinding(
                "activity_search_text",
                "",
                lambda: self.activitySearchLineEdit.text().strip(),
                self.activitySearchLineEdit.setText,
            ),
            UIFieldBinding(
                "max_distance_km",
                0.0,
                lambda: self.maxDistanceSpinBox.value(),
                lambda value: self._set_float_value(self.maxDistanceSpinBox, value, 0.0),
            ),
            UIFieldBinding(
                "detailed_only",
                False,
                lambda: self.detailedOnlyCheckBox.isChecked(),
                lambda value: self._set_bool_value(self.detailedOnlyCheckBox, value, False),
            ),
            UIFieldBinding(
                "use_background_map",
                False,
                lambda: self.backgroundMapCheckBox.isChecked(),
                lambda value: self._set_bool_value(self.backgroundMapCheckBox, value, False),
            ),
            UIFieldBinding(
                "mapbox_style_owner",
                "mapbox",
                lambda: self.mapboxStyleOwnerLineEdit.text().strip(),
                self.mapboxStyleOwnerLineEdit.setText,
            ),
            UIFieldBinding(
                "mapbox_style_id",
                "",
                lambda: self.mapboxStyleIdLineEdit.text().strip(),
                self.mapboxStyleIdLineEdit.setText,
            ),
            UIFieldBinding(
                "atlas_margin_percent",
                8.0,
                lambda: self.atlasMarginPercentSpinBox.value(),
                lambda value: self._set_float_value(self.atlasMarginPercentSpinBox, value, 8.0),
            ),
            UIFieldBinding(
                "atlas_min_extent_degrees",
                0.01,
                lambda: self.atlasMinExtentSpinBox.value(),
                lambda value: self._set_float_value(self.atlasMinExtentSpinBox, value, 0.01),
            ),
            UIFieldBinding(
                "atlas_target_aspect_ratio",
                BUILTIN_ATLAS_MAP_TARGET_ASPECT_RATIO,
                lambda: self.atlasTargetAspectRatioSpinBox.value(),
                self._set_atlas_target_aspect_ratio_value,
            ),
            UIFieldBinding(
                "atlas_pdf_path",
                self._default_atlas_pdf_path(),
                lambda: self.atlasPdfPathLineEdit.text().strip(),
                self.atlasPdfPathLineEdit.setText,
            ),
            UIFieldBinding(
                "temporal_mode",
                DEFAULT_TEMPORAL_MODE_LABEL,
                lambda: self.temporalModeComboBox.currentText(),
                lambda value: self._set_combo_value(self.temporalModeComboBox, value, DEFAULT_TEMPORAL_MODE_LABEL),
            ),
            UIFieldBinding(
                "background_preset",
                DEFAULT_BACKGROUND_PRESET,
                lambda: self.backgroundPresetComboBox.currentText(),
                lambda value: self._set_combo_value(self.backgroundPresetComboBox, value, DEFAULT_BACKGROUND_PRESET),
            ),
            UIFieldBinding(
                "tile_mode",
                TILE_MODE_RASTER,
                lambda: self.tileModeComboBox.currentText(),
                lambda value: self._set_combo_value(self.tileModeComboBox, value, TILE_MODE_RASTER),
            ),
            UIFieldBinding(
                "preview_sort",
                DEFAULT_SORT_LABEL,
                lambda: self.previewSortComboBox.currentText(),
                lambda value: self._set_combo_value(self.previewSortComboBox, value, DEFAULT_SORT_LABEL),
            ),
            UIFieldBinding(
                "style_preset",
                default_style_preset,
                lambda: self.stylePresetComboBox.currentText(),
                lambda value: self._set_combo_value(self.stylePresetComboBox, value, default_style_preset),
            ),
        ]

    def _load_settings(self):
        load_bindings(self._settings_bindings(), self.settings)
        self.authCodeLineEdit.setText("")
        self._sync_background_style_fields(self.backgroundPresetComboBox.currentText(), force=False)

        last_sync = self.settings.get("last_sync_date", None)
        if last_sync:
            self.countLabel.setText(f"Last sync: {last_sync}")

    def _save_settings(self):
        save_bindings(self._settings_bindings(), self.settings)


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
                access_token=self._mapbox_access_token(),
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

        self._save_settings()
        try:
            fetch_request = self.sync_controller.build_fetch_task_request(
                client_id=self.clientIdLineEdit.text().strip(),
                client_secret=self.clientSecretLineEdit.text().strip(),
                refresh_token=self.refreshTokenLineEdit.text().strip(),
                cache=self.cache,
                per_page=self.perPageSpinBox.value(),
                max_pages=self.maxPagesSpinBox.value(),
                use_detailed_streams=self.detailedStreamsCheckBox.isChecked(),
                max_detailed_activities=self.maxDetailedActivitiesSpinBox.value(),
                on_finished=self._on_fetch_finished,
            )
            self._fetch_task = self.sync_controller.build_fetch_task(fetch_request)
        except ProviderError as exc:
            self._show_error("Strava import failed", str(exc))
            self._set_status("Strava fetch failed")
            return

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
            result = self.load_workflow.write_database_request(request)
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
        last_sync = self.settings.get("last_sync_date", date.today().isoformat())
        self.countLabel.setText(
            "{total} activities stored in database (last sync: {sync_date})".format(
                total=result.total_stored, sync_date=last_sync,
            )
        )
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
        self.activities = []
        self.output_path = None
        self.last_fetch_context = {}

        self.countLabel.setText("Activities fetched: 0")
        self._set_status(result.status)

    def on_apply_filters_clicked(self):
        has_layers = any(layer is not None for layer in [self.activities_layer, self.starts_layer, self.points_layer, self.atlas_layer])
        if not has_layers:
            return

        self._save_settings()
        status = self._apply_visual_configuration(apply_subset_filters=True)
        if status:
            self._set_status(status)

    def _apply_visual_configuration(self, apply_subset_filters):
        filtered_activities = self._filtered_activities()
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
            access_token=self._mapbox_access_token(),
            style_owner=self.mapboxStyleOwnerLineEdit.text().strip(),
            style_id=self.mapboxStyleIdLineEdit.text().strip(),
            tile_mode=self.tileModeComboBox.currentText(),
        )

        request = self.visual_apply.build_request(
            layers=layers,
            query=query,
            style_preset=self.stylePresetComboBox.currentText(),
            temporal_mode=self.temporalModeComboBox.currentText(),
            background_config=bg_config,
            apply_subset_filters=apply_subset_filters,
            filtered_count=len(filtered_activities),
        )
        result = self.visual_apply.apply_request(request)

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
            self.querySummaryLabel.setText("Fetch activities to preview your latest synced activities.")
            self.activityPreviewPlainTextEdit.setPlainText("")
            return []

        fetched_activities = sort_activities(self.activities, DEFAULT_SORT_LABEL)
        summary = summarize_activities(fetched_activities)

        query_summary = format_summary_text(summary)
        filtered_count = len(self._filtered_activities())
        if filtered_count != len(self.activities):
            query_summary = (
                f"{query_summary}\n"
                f"Visualize filters currently match {filtered_count} activities."
            )
        self.querySummaryLabel.setText(query_summary)

        preview_lines = build_preview_lines(fetched_activities, limit=10)
        if len(fetched_activities) > len(preview_lines):
            preview_lines.append("… and {count} more".format(count=len(fetched_activities) - len(preview_lines)))
        self.activityPreviewPlainTextEdit.setPlainText("\n".join(preview_lines))
        return fetched_activities

    def _filtered_activities(self):
        return filter_activities(self.activities, self._current_activity_query())


    def _redirect_uri(self):
        return self.redirectUriLineEdit.text().strip() or StravaProvider.DEFAULT_REDIRECT_URI

    def _mapbox_access_token(self):
        return (self.settings.get("mapbox_access_token", "") or "").strip()

    def _qdate_to_date(self, value):
        return date(value.year(), value.month(), value.day())

    def _populate_activity_types(self):
        current_value = self.activityTypeComboBox.currentText() or "All"
        values = sorted(
            ordered_canonical_activity_labels(
                (getattr(activity, "activity_type", None), getattr(activity, "sport_type", None))
                for activity in self.activities
            )
        )
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
            if not any(name in field_names for name in ("activity_type", "sport_type")):
                return
            values = sorted(
                ordered_canonical_activity_labels(
                    (
                        feature["activity_type"] if "activity_type" in field_names else None,
                        feature["sport_type"] if "sport_type" in field_names else None,
                    )
                    for feature in self.activities_layer.getFeatures()
                )
            )
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
            message = "Strava connection: app credentials saved; add a refresh token in Configuration to fetch activities"
        else:
            message = "Strava connection: open qfit → Configuration to add your Strava credentials"
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

        prereq_error = self.atlas_export_service.check_pdf_export_prerequisites()
        if prereq_error is not None:
            self._set_atlas_pdf_status("Atlas PDF export unavailable.")
            self._set_status("Atlas PDF export unavailable.")
            self._show_error("Atlas PDF export unavailable", prereq_error)
            return

        self._save_settings()

        pre_export_tile_mode = self.tileModeComboBox.currentText()
        export_request = self.atlas_export_service.build_request(
            atlas_layer=self.atlas_layer,
            output_path=output_path,
            on_finished=self._on_atlas_export_finished,
            pre_export_tile_mode=pre_export_tile_mode,
            preset_name=self.backgroundPresetComboBox.currentText(),
            access_token=self._mapbox_access_token(),
            style_owner=self.mapboxStyleOwnerLineEdit.text().strip(),
            style_id=self.mapboxStyleIdLineEdit.text().strip(),
            background_enabled=self.backgroundMapCheckBox.isChecked(),
        )
        self.atlas_export_service.prepare_basemap_for_export(export_request)

        self._set_atlas_export_running(True)
        self._set_atlas_pdf_status(
            f"Exporting atlas ({self.atlas_layer.featureCount()} pages)…"
        )
        self._set_status("Generating atlas PDF…")

        self._atlas_export_task = self.atlas_export_service.build_task(export_request)
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
