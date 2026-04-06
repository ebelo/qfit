import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import MagicMock, patch

from tests import _path  # noqa: F401

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
REPO_ROOT = Path(__file__).resolve().parents[1]

try:
    from qgis.core import QgsApplication, QgsLayoutExporter, QgsProject, QgsRectangle, QgsVectorLayer
    from qgis.PyQt.QtCore import QDate, Qt
    from qgis.PyQt.QtGui import QImage

    from qfit.activities.domain.activity_query import ActivityQuery, build_subset_string
    from qfit.atlas.export_task import (
        BUILTIN_ATLAS_MAP_TARGET_ASPECT_RATIO,
        PAGE_HEIGHT_MM,
        PAGE_WIDTH_MM,
        PROFILE_CHART_H,
        PROFILE_CHART_Y,
        PROFILE_W,
        PROFILE_X,
        _PROFILE_PICTURE_ID,
        _apply_page_profile_payload,
        _build_page_profile_payload,
        _normalize_extent_to_aspect_ratio,
        build_atlas_layout,
    )
    from qfit.atlas.profile_item import build_profile_item_adapter
    from qfit.credential_store import InMemoryCredentialStore
    from qfit.gpkg_writer import GeoPackageWriter
    from qfit.layer_manager import LayerManager
    from qfit.mapbox_config import TILE_MODE_RASTER
    from qfit.activities.domain.models import Activity
    from qfit.qfit_dockwidget import QfitDockWidget
    from qfit.settings_service import SettingsService
    from qfit.ui.dockwidget_dependencies import build_dockwidget_dependencies
    from qfit.ui.workflow_section_coordinator import WorkflowSectionCoordinator
    from qfit.visual_apply import VisualApplyService

    QGIS_AVAILABLE = True
    QGIS_IMPORT_ERROR = None
except Exception as exc:  # pragma: no cover - exercised only when QGIS is unavailable
    QgsApplication = None
    QgsLayoutExporter = None
    QgsProject = None
    QgsRectangle = None
    QgsVectorLayer = None
    QDate = None
    QImage = None
    Qt = None
    ActivityQuery = None
    build_subset_string = None
    GeoPackageWriter = None
    LayerManager = None
    TILE_MODE_RASTER = None
    Activity = None
    QfitDockWidget = None
    build_dockwidget_dependencies = None
    QGIS_AVAILABLE = False
    QGIS_IMPORT_ERROR = exc


class _FakeCanvas:
    def __init__(self):
        self.destination_crs_authid = None
        self.last_extent = None
        self.refresh_count = 0

    def setDestinationCrs(self, crs):
        self.destination_crs_authid = crs.authid()

    def setExtent(self, extent):
        self.last_extent = (
            extent.xMinimum(),
            extent.yMinimum(),
            extent.xMaximum(),
            extent.yMaximum(),
        )

    def extent(self):
        if self.last_extent is None:
            return None

        class _Extent:
            def __init__(self, vals):
                self._vals = vals

            def xMinimum(self):
                return self._vals[0]

            def yMinimum(self):
                return self._vals[1]

            def xMaximum(self):
                return self._vals[2]

            def yMaximum(self):
                return self._vals[3]

        return _Extent(self.last_extent)

    def refresh(self):
        self.refresh_count += 1


class _FakeIface:
    def __init__(self):
        self._canvas = _FakeCanvas()
        self._main_window = None

    def mapCanvas(self):
        return self._canvas

    def mainWindow(self):
        return self._main_window


class _FakeQSettings:
    def __init__(self, data=None):
        self._data = data or {}

    def value(self, key, default=None):
        return self._data.get(key, default)

    def setValue(self, key, value):
        self._data[key] = value

    def remove(self, key):
        self._data.pop(key, None)


@unittest.skipUnless(
    QGIS_AVAILABLE,
    "PyQGIS is not available in this environment: {error}".format(error=QGIS_IMPORT_ERROR),
)
class QgisSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        QgsApplication.setPrefixPath("/usr", True)
        cls.qgs = QgsApplication([], False)
        cls.qgs.initQgis()

    @classmethod
    def tearDownClass(cls):
        QgsProject.instance().clear()
        cls.qgs.exitQgis()

    def setUp(self):
        QgsProject.instance().clear()
        self.iface = _FakeIface()
        self.layer_manager = LayerManager(self.iface)

    def tearDown(self):
        QgsProject.instance().clear()

    def test_dock_widget_uses_injected_dependencies_without_rebuilding_defaults(self):
        dependencies = build_dockwidget_dependencies(self.iface)

        with patch(
            "qfit.qfit_dockwidget.build_dockwidget_dependencies",
            side_effect=AssertionError("default dependency factory should not run"),
        ):
            dock = QfitDockWidget(self.iface, dependencies=dependencies)
        try:
            self.assertIs(dock._dependencies, dependencies)
            self.assertIs(dock.settings, dependencies.settings)
            self.assertIs(dock.sync_controller, dependencies.sync_controller)
            self.assertIs(dock.atlas_export_controller, dependencies.atlas_export_controller)
            self.assertIs(dock.layer_gateway, dependencies.layer_gateway)
            self.assertIs(dock.background_controller, dependencies.background_controller)
            self.assertIs(dock.load_workflow, dependencies.load_workflow)
            self.assertIs(dock.visual_apply, dependencies.visual_apply)
            self.assertIs(dock.atlas_export_service, dependencies.atlas_export_service)
            self.assertIs(dock.fetch_result_service, dependencies.fetch_result_service)
            self.assertIs(dock.cache, dependencies.cache)
        finally:
            dock.close()
            dock.deleteLater()

    def test_dock_widget_contextual_help_smoke(self):
        dock = QfitDockWidget(self.iface)
        try:
            from qgis.PyQt.QtWidgets import QComboBox, QLabel, QWidget

            self.assertEqual(dock.maxDetailedActivitiesLabel.text(), "Max new detailed routes this run")
            self.assertEqual(dock.pointSamplingStrideLabel.text(), "Keep every Nth point")
            self.assertEqual(dock.temporalModeLabel.text(), "Temporal timestamps")
            self.assertEqual(dock.workflowLabel.text(), "Workflow: Fetch & store → Visualize → Analyze → Publish")
            self.assertFalse(dock.credentialsGroupBox.isVisible())
            self.assertTrue(bool(dock.features() & dock.DockWidgetMovable))
            self.assertTrue(bool(dock.features() & dock.DockWidgetFloatable))
            self.assertEqual(dock.activitiesGroupBox.title(), "")
            self.assertEqual(dock.activitiesSectionToggleButton.text(), "1. Fetch and store activities")
            self.assertTrue(dock.activitiesSectionToggleButton.isChecked())
            self.assertEqual(dock.activitiesSectionToggleButton.arrowType(), Qt.DownArrow)
            self.assertFalse(dock.activitiesSectionContentWidget.isHidden())
            self.assertFalse(dock.mapboxAccessTokenLabel.isVisible())
            self.assertFalse(dock.mapboxAccessTokenLineEdit.isVisible())
            self.assertEqual(dock.refreshButton.text(), "Fetch activities")
            self.assertEqual(dock.loadButton.text(), "Store activities")
            self.assertEqual(dock.loadLayersButton.text(), "Load activity layers")
            self.assertEqual(dock.clearDatabaseButton.text(), "Clear database")
            self.assertEqual(dock.applyFiltersButton.text(), "Apply current filters to loaded layers")
            self.assertFalse(dock.backgroundHelpLabel.isVisible())
            self.assertFalse(dock.analysisHelpLabel.isVisible())
            self.assertFalse(dock.publishHelpLabel.isVisible())
            self.assertFalse(dock.temporalHelpLabel.isVisible())
            self.assertEqual(dock.outputGroupBox.title(), "Store / database")
            self.assertEqual(dock.outputGroupBox.parent(), dock.activitiesSectionContentWidget)
            self.assertGreater(dock.activitiesSectionContentWidget.layout().indexOf(dock.outputGroupBox), dock.activitiesSectionContentWidget.layout().indexOf(dock.previewGroupBox))
            self.assertEqual(dock.styleGroupBox.title(), "")
            self.assertEqual(dock.styleSectionToggleButton.text(), "2. Visualize")
            self.assertEqual(dock.styleSectionToggleButton.arrowType(), Qt.DownArrow)
            self.assertFalse(dock.styleSectionContentWidget.isHidden())
            self.assertEqual(dock.loadLayersButton.parent(), dock.styleSectionContentWidget)
            self.assertLess(dock.styleSectionContentWidget.layout().indexOf(dock.loadLayersButton), dock.styleSectionContentWidget.layout().indexOf(dock.backgroundGroupBox))
            self.assertEqual(dock.analysisWorkflowGroupBox.title(), "")
            self.assertEqual(dock.analysisSectionToggleButton.text(), "3. Analyze")
            self.assertFalse(dock.analysisSectionContentWidget.isHidden())
            self.assertEqual(dock.analysisWorkflowLayout.spacing(), 6)
            temporal_mode_layout = dock.temporalModeLabel.parentWidget().layout()
            self.assertEqual(temporal_mode_layout.spacing(), 6)
            self.assertGreaterEqual(dock.temporalModeComboBox.minimumContentsLength(), 10)
            self.assertGreaterEqual(dock.temporalHelpLabel.margin(), 2)
            self.assertEqual(dock.publishGroupBox.title(), "")
            self.assertEqual(dock.publishSectionToggleButton.text(), "4. Publish / atlas")
            self.assertFalse(dock.publishSectionContentWidget.isHidden())
            self.assertTrue(dock.publishSettingsWidget.parent() is dock.publishSectionContentWidget or dock.publishSettingsWidget.isVisible())
            self.assertEqual(dock.tileModeComboBox.currentText(), TILE_MODE_RASTER)
            self.assertAlmostEqual(
                dock.atlasTargetAspectRatioSpinBox.value(),
                BUILTIN_ATLAS_MAP_TARGET_ASPECT_RATIO,
                places=3,
            )
            self.assertEqual(dock.detailedRouteStrategyComboBox.currentText(), "Missing routes only")
            self.assertIsNotNone(dock.findChild(QLabel, "detailedRouteStrategyComboBoxContextHelpLabel"))
            self.assertIsNotNone(dock.findChild(QWidget, "detailedRouteStrategyComboBoxHelpField"))
            self.assertIsNotNone(dock.findChild(QLabel, "maxDetailedActivitiesSpinBoxContextHelpLabel"))
            self.assertIsNotNone(dock.findChild(QWidget, "maxDetailedActivitiesSpinBoxHelpField"))
            temporal_helper = dock.findChild(QLabel, "temporalModeComboBoxContextHelpLabel")
            self.assertIsNotNone(temporal_helper)
            self.assertEqual(temporal_helper.parentWidget(), dock.temporalModeLabel.parentWidget())
            dock.activitiesSectionToggleButton.click()
            self.assertFalse(dock.activitiesSectionToggleButton.isChecked())
            self.assertEqual(dock.activitiesSectionToggleButton.arrowType(), Qt.RightArrow)
            self.assertTrue(dock.activitiesSectionContentWidget.isHidden())
            dock.styleSectionToggleButton.click()
            self.assertTrue(dock.styleSectionContentWidget.isHidden())
            dock.analysisSectionToggleButton.click()
            self.assertTrue(dock.analysisSectionContentWidget.isHidden())
            dock.publishSectionToggleButton.click()
            self.assertTrue(dock.publishSectionContentWidget.isHidden())
        finally:
            dock.close()
            dock.deleteLater()

    def test_workflow_section_coordinator_updates_visibility_rules(self):
        dock = QfitDockWidget(self.iface)
        try:
            coordinator = WorkflowSectionCoordinator(dock)

            coordinator.update_detailed_fetch_visibility(False)
            self.assertTrue(dock.detailedRouteStrategyLabel.isHidden())
            self.assertTrue(dock.maxDetailedActivitiesSpinBox.isHidden())

            coordinator.update_detailed_fetch_visibility(True)
            self.assertFalse(dock.detailedRouteStrategyLabel.isHidden())
            self.assertFalse(dock.maxDetailedActivitiesSpinBox.isHidden())

            coordinator.update_point_sampling_visibility(False)
            self.assertTrue(dock.pointSamplingStrideSpinBox.isHidden())
            coordinator.update_point_sampling_visibility(True)
            self.assertFalse(dock.pointSamplingStrideSpinBox.isHidden())

            coordinator.update_advanced_fetch_visibility(False)
            self.assertTrue(dock.advancedFetchSettingsWidget.isHidden())
            coordinator.update_advanced_fetch_visibility(True)
            self.assertFalse(dock.advancedFetchSettingsWidget.isHidden())

            coordinator.update_mapbox_advanced_visibility("Outdoor")
            self.assertTrue(dock.mapboxStyleOwnerLineEdit.isHidden())
            coordinator.update_mapbox_advanced_visibility("Custom")
            self.assertFalse(dock.mapboxStyleOwnerLineEdit.isHidden())
            self.assertFalse(dock.mapboxStyleIdLineEdit.isHidden())
        finally:
            dock.close()
            dock.deleteLater()

    def test_dock_widget_round_trips_settings_through_canonical_binding_table(self):
        settings = SettingsService(
            qsettings=_FakeQSettings(),
            credential_store=InMemoryCredentialStore(),
        )
        dependencies = replace(
            build_dockwidget_dependencies(self.iface),
            settings=settings,
        )

        dock = QfitDockWidget(self.iface, dependencies=dependencies)
        try:
            preview_sort_text = dock.previewSortComboBox.itemText(
                1 if dock.previewSortComboBox.count() > 1 else 0
            )
            style_preset_text = dock.stylePresetComboBox.itemText(
                1 if dock.stylePresetComboBox.count() > 1 else 0
            )
            temporal_mode_text = dock.temporalModeComboBox.itemText(
                1 if dock.temporalModeComboBox.count() > 1 else 0
            )
            background_preset_text = dock.backgroundPresetComboBox.itemText(
                1 if dock.backgroundPresetComboBox.count() > 1 else 0
            )

            dock.clientIdLineEdit.setText("client-123")
            dock.outputPathLineEdit.setText("/tmp/roundtrip.gpkg")
            dock.perPageSpinBox.setValue(123)
            dock.detailedStreamsCheckBox.setChecked(True)
            dock.detailedRouteStrategyComboBox.setCurrentText("Recent fetch only")
            dock.backgroundMapCheckBox.setChecked(True)
            dock.backgroundPresetComboBox.setCurrentText(background_preset_text)
            dock.previewSortComboBox.setCurrentText(preview_sort_text)
            dock.stylePresetComboBox.setCurrentText(style_preset_text)
            dock.temporalModeComboBox.setCurrentText(temporal_mode_text)
            dock.atlasTargetAspectRatioSpinBox.setValue(1.75)
            dock.atlasPdfPathLineEdit.setText("/tmp/roundtrip.pdf")

            dock._save_settings()

            self.assertEqual(settings.get("client_id"), "client-123")
            self.assertEqual(settings.get("output_path"), "/tmp/roundtrip.gpkg")
            self.assertEqual(int(settings.get("per_page")), 123)
            self.assertTrue(settings.get_bool("use_detailed_streams"))
            self.assertEqual(settings.get("detailed_route_strategy"), "Recent fetch only")
            self.assertTrue(settings.get_bool("use_background_map"))
            self.assertEqual(settings.get("background_preset"), background_preset_text)
            self.assertEqual(settings.get("preview_sort"), preview_sort_text)
            self.assertEqual(settings.get("style_preset"), style_preset_text)
            self.assertEqual(settings.get("temporal_mode"), temporal_mode_text)
            self.assertAlmostEqual(float(settings.get("atlas_target_aspect_ratio")), 1.75, places=2)
            self.assertEqual(settings.get("atlas_pdf_path"), "/tmp/roundtrip.pdf")
        finally:
            dock.close()
            dock.deleteLater()

        dock_reloaded = QfitDockWidget(self.iface, dependencies=dependencies)
        try:
            self.assertEqual(dock_reloaded.clientIdLineEdit.text(), "client-123")
            self.assertEqual(dock_reloaded.outputPathLineEdit.text(), "/tmp/roundtrip.gpkg")
            self.assertEqual(dock_reloaded.perPageSpinBox.value(), 123)
            self.assertTrue(dock_reloaded.detailedStreamsCheckBox.isChecked())
            self.assertEqual(dock_reloaded.detailedRouteStrategyComboBox.currentText(), "Recent fetch only")
            self.assertTrue(dock_reloaded.backgroundMapCheckBox.isChecked())
            self.assertEqual(dock_reloaded.backgroundPresetComboBox.currentText(), background_preset_text)
            self.assertEqual(dock_reloaded.previewSortComboBox.currentText(), preview_sort_text)
            self.assertEqual(dock_reloaded.stylePresetComboBox.currentText(), style_preset_text)
            self.assertEqual(dock_reloaded.temporalModeComboBox.currentText(), temporal_mode_text)
            self.assertAlmostEqual(dock_reloaded.atlasTargetAspectRatioSpinBox.value(), 1.75, places=2)
            self.assertEqual(dock_reloaded.atlasPdfPathLineEdit.text(), "/tmp/roundtrip.pdf")
        finally:
            dock_reloaded.close()
            dock_reloaded.deleteLater()

    def test_generate_atlas_pdf_shows_clear_error_when_pypdf_is_missing(self):
        dock = QfitDockWidget(self.iface)
        try:
            dock.atlas_layer = MagicMock()
            dock.atlas_layer.featureCount.return_value = 3
            dock.atlasPdfPathLineEdit.setText("/tmp/qfit-atlas.pdf")

            from qfit.atlas.export_use_case import PrepareAtlasPdfExportResult

            dock.atlas_export_use_case.prepare_export = MagicMock(
                return_value=PrepareAtlasPdfExportResult(
                    output_path="/tmp/qfit-atlas.pdf",
                    error_title="Atlas PDF export unavailable",
                    error_message="Atlas PDF export requires the 'pypdf' runtime.",
                    pdf_status="Atlas PDF export unavailable.",
                    main_status="Atlas PDF export unavailable.",
                )
            )
            dock._save_settings = MagicMock()
            dock._show_error = MagicMock()

            dock.on_generate_atlas_pdf_clicked()

            dock._show_error.assert_called_once_with(
                "Atlas PDF export unavailable",
                "Atlas PDF export requires the 'pypdf' runtime.",
            )
            dock._save_settings.assert_not_called()
            self.assertIsNone(dock._atlas_export_task)
            self.assertEqual(dock.atlasPdfStatusLabel.text(), "Atlas PDF export unavailable.")
            self.assertEqual(dock.statusLabel.text(), "Atlas PDF export unavailable.")
        finally:
            dock.close()
            dock.deleteLater()

    def test_generate_atlas_pdf_passes_profile_plot_style_from_settings(self):
        dock = QfitDockWidget(self.iface)
        try:
            fake_task = MagicMock(name="atlas_export_task")
            dock.atlas_layer = MagicMock()
            dock.atlas_layer.featureCount.return_value = 3
            dock.atlasPdfPathLineEdit.setText("/tmp/qfit-atlas.pdf")

            prepared_export = MagicMock(name="prepared_export")
            prepared_export.is_ready = True
            prepared_export.path_changed = False
            dock.atlas_export_use_case.prepare_export = MagicMock(return_value=prepared_export)
            dock.atlas_export_use_case.start_export = MagicMock(return_value=fake_task)
            dock._save_settings = MagicMock()

            with (
                patch("qfit.qfit_dockwidget.build_native_profile_plot_style_from_settings", return_value="style-override") as build_style,
                patch("qfit.qfit_dockwidget.QgsApplication.taskManager") as task_manager,
            ):
                task_manager.return_value.addTask = MagicMock()

                dock.on_generate_atlas_pdf_clicked()

            build_style.assert_called_once_with(dock.settings)
            export_command = dock.atlas_export_use_case.prepare_export.call_args.args[0]
            self.assertEqual(export_command.profile_plot_style, "style-override")
            dock.atlas_export_use_case.start_export.assert_called_once_with(prepared_export)
            task_manager.return_value.addTask.assert_called_once_with(fake_task)
        finally:
            dock.close()
            dock.deleteLater()

    def test_refresh_clicked_builds_fetch_task_via_sync_controller(self):
        dock = QfitDockWidget(self.iface)
        try:
            fake_task = MagicMock(name="fetch_task")
            dock._save_settings = MagicMock()
            dock.sync_controller.build_fetch_task_request = MagicMock(return_value="fetch-request")
            dock.sync_controller.build_fetch_task = MagicMock(return_value=fake_task)

            with patch("qfit.qfit_dockwidget.QgsApplication.taskManager") as task_manager:
                task_manager.return_value.addTask = MagicMock()
                dock.detailedRouteStrategyComboBox.setCurrentText("Recent fetch only")
                dock.on_refresh_clicked()

            dock.sync_controller.build_fetch_task_request.assert_called_once()
            self.assertEqual(
                dock.sync_controller.build_fetch_task_request.call_args.kwargs["detailed_route_strategy"],
                "Recent fetch only",
            )
            dock.sync_controller.build_fetch_task.assert_called_once_with("fetch-request")
            task_manager.return_value.addTask.assert_called_once_with(fake_task)
            self.assertIs(dock._fetch_task, fake_task)
            self.assertEqual(dock.refreshButton.text(), "Cancel")
        finally:
            dock.close()
            dock.deleteLater()

    def test_detailed_route_controls_use_missing_route_wording(self):
        dock = QfitDockWidget(self.iface)
        try:
            self.assertEqual(
                dock.detailedStreamsCheckBox.text(),
                "Fetch detailed routes when available",
            )
            self.assertEqual(dock.detailedRouteStrategyLabel.text(), "Detailed route strategy")
            self.assertEqual(
                dock.maxDetailedActivitiesLabel.text(),
                "Max new detailed routes this run",
            )
        finally:
            dock.close()
            dock.deleteLater()

    def test_open_authorize_clicked_builds_authorize_url_via_sync_controller(self):
        dock = QfitDockWidget(self.iface)
        try:
            dock._save_settings = MagicMock()
            dock.sync_controller.build_authorize_request = MagicMock(return_value="authorize-request")
            dock.sync_controller.build_authorize_url = MagicMock(return_value="https://strava.test/auth")

            with patch("qfit.qfit_dockwidget.QDesktopServices.openUrl", return_value=True) as open_url:
                dock.on_open_authorize_clicked()

            dock.sync_controller.build_authorize_request.assert_called_once()
            dock.sync_controller.build_authorize_url.assert_called_once_with("authorize-request")
            open_url.assert_called_once()
            self.assertIn("Strava authorization opened", dock.statusLabel.text())
        finally:
            dock.close()
            dock.deleteLater()

    def test_exchange_code_clicked_uses_sync_controller_exchange_workflow(self):
        dock = QfitDockWidget(self.iface)
        try:
            dock.authCodeLineEdit.setText("abc123")
            dock._save_settings = MagicMock()
            dock._update_connection_status = MagicMock()
            dock.sync_controller.build_exchange_code_request = MagicMock(return_value="exchange-request")
            dock.sync_controller.exchange_code_for_tokens = MagicMock(
                return_value={
                    "refresh_token": "rtok",
                    "athlete": {"firstname": "Ada", "lastname": "Lovelace"},
                }
            )

            dock.on_exchange_code_clicked()

            dock.sync_controller.build_exchange_code_request.assert_called_once()
            dock.sync_controller.exchange_code_for_tokens.assert_called_once_with("exchange-request")
            self.assertEqual(dock.refreshTokenLineEdit.text(), "rtok")
            self.assertEqual(dock.authCodeLineEdit.text(), "")
            dock._update_connection_status.assert_called_once()
            self.assertIn("Ada Lovelace", dock.statusLabel.text())
        finally:
            dock.close()
            dock.deleteLater()

    def test_load_background_clicked_uses_structured_background_workflow(self):
        dock = QfitDockWidget(self.iface)
        try:
            fake_layer = MagicMock(name="background_layer")
            dock._save_settings = MagicMock()
            dock.backgroundMapCheckBox.setChecked(True)
            dock.background_controller.build_load_request = MagicMock(return_value="background-request")
            dock.background_controller.load_background_request = MagicMock(
                return_value=MagicMock(
                    layer=fake_layer,
                    status="Background map loaded below the qfit activity layers",
                )
            )

            dock.on_load_background_clicked()

            dock.background_controller.build_load_request.assert_called_once()
            dock.background_controller.load_background_request.assert_called_once_with(
                "background-request"
            )
            self.assertIs(dock.background_layer, fake_layer)
            self.assertEqual(
                dock.statusLabel.text(),
                "Background map loaded below the qfit activity layers",
            )
        finally:
            dock.close()
            dock.deleteLater()

    def test_fetch_preview_shows_fetched_count_even_when_visualize_filters_match_zero(self):
        dock = QfitDockWidget(self.iface)
        try:
            dock.activities = [Activity(**payload) for payload in self._sample_activities()]
            dock._populate_activity_types()
            dock.dateFromEdit.setDate(QDate(2030, 1, 1))

            dock._refresh_activity_preview()

            self.assertIn("2 activities", dock.querySummaryLabel.text())
            self.assertIn("Visualize filters currently match 0 activities.", dock.querySummaryLabel.text())
            preview_text = dock.activityPreviewPlainTextEdit.toPlainText()
            self.assertIn("Lunch Run", preview_text)
            self.assertIn("Morning Ride", preview_text)
        finally:
            dock.close()
            dock.deleteLater()

    def test_background_layer_source_uses_high_dpi_xyz_uri(self):
        background = self.layer_manager.ensure_background_layer(True, "Outdoor", "test-token")
        self.assertTrue(background.isValid())
        self.assertIn("tiles/512/{z}/{x}/{y}?access_token=", background.source())
        self.assertIn("tilePixelRatio=2", background.source())

    def test_apply_filters_path_does_not_update_background_layer(self):
        self.assertFalse(VisualApplyService.should_update_background(True))
        self.assertTrue(VisualApplyService.should_update_background(False))

    def test_apply_filters_updates_activity_subset_string(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = str(Path(temp_dir) / "qfit-filters.gpkg")
            GeoPackageWriter(
                output_path,
                write_activity_points=True,
                point_stride=2,
                atlas_margin_percent=10,
                atlas_min_extent_degrees=0.01,
                atlas_target_aspect_ratio=1.5,
            ).write_activities(self._sample_activities(), sync_metadata={"provider": "strava"})

            activities_layer, _starts_layer, _points_layer, _atlas_layer = (
                self.layer_manager.load_output_layers(output_path)
            )
            self.layer_manager.apply_filters(
                activities_layer,
                activity_type="Run",
                date_from="2026-03-21",
                date_to="2026-03-21",
                min_distance_km=5,
                max_distance_km=10,
                search_text="Run",
                detailed_only=True,
            )

            self.assertEqual(
                activities_layer.subsetString(),
                build_subset_string(
                    ActivityQuery(
                        activity_type="Run",
                        date_from="2026-03-21",
                        date_to="2026-03-21",
                        min_distance_km=5,
                        max_distance_km=10,
                        search_text="Run",
                        detailed_only=True,
                    )
                ),
            )

    def test_headless_qgis_smoke_covers_write_load_crs_temporal_and_background_order(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = str(Path(temp_dir) / "qfit-smoke.gpkg")
            result = GeoPackageWriter(
                output_path,
                write_activity_points=True,
                point_stride=2,
                atlas_margin_percent=10,
                atlas_min_extent_degrees=0.01,
                atlas_target_aspect_ratio=1.5,
            ).write_activities(self._sample_activities(), sync_metadata={"provider": "strava"})

            self.assertEqual(result["track_count"], 2)
            self.assertEqual(result["start_count"], 2)
            self.assertGreaterEqual(result["point_count"], 4)
            self.assertEqual(result["atlas_count"], 2)
            self.assertEqual(result["document_summary_count"], 1)
            self.assertEqual(result["cover_highlight_count"], 6)
            self.assertEqual(result["page_detail_item_count"], 11)
            self.assertEqual(result["profile_sample_count"], 8)
            self.assertEqual(result["toc_count"], 2)

            document_summary_layer = QgsVectorLayer(
                f"{output_path}|layername=atlas_document_summary",
                "qfit atlas document summary",
                "ogr",
            )
            self.assertTrue(document_summary_layer.isValid())
            self.assertEqual(document_summary_layer.featureCount(), 1)
            document_summary_feature = next(document_summary_layer.getFeatures())
            self.assertEqual(document_summary_feature["activity_count"], 2)
            self.assertEqual(document_summary_feature["date_range_label"], "2026-03-20 → 2026-03-21")
            self.assertEqual(document_summary_feature["total_distance_label"], "35.3 km")
            self.assertIn("2 activities · 2026-03-20 → 2026-03-21 · 35.3 km · 1h 50m · ↑ 405 m", document_summary_feature["cover_summary"])

            cover_highlight_layer = QgsVectorLayer(
                f"{output_path}|layername=atlas_cover_highlights",
                "qfit atlas cover highlights",
                "ogr",
            )
            self.assertTrue(cover_highlight_layer.isValid())
            self.assertEqual(cover_highlight_layer.featureCount(), 6)
            cover_highlight_feature = next(cover_highlight_layer.getFeatures())
            self.assertEqual(cover_highlight_feature["highlight_key"], "activity_count")
            self.assertEqual(cover_highlight_feature["highlight_value"], "2 activities")

            page_detail_layer = QgsVectorLayer(
                f"{output_path}|layername=atlas_page_detail_items",
                "qfit atlas page detail items",
                "ogr",
            )
            self.assertTrue(page_detail_layer.isValid())
            self.assertEqual(page_detail_layer.featureCount(), 11)
            page_detail_features = list(page_detail_layer.getFeatures())
            self.assertEqual(page_detail_features[0]["detail_key"], "distance")
            self.assertEqual(page_detail_features[0]["detail_value"], "25.2 km")
            self.assertEqual(page_detail_features[-1]["detail_key"], "profile_summary")

            profile_layer = QgsVectorLayer(
                f"{output_path}|layername=atlas_profile_samples",
                "qfit atlas profile samples",
                "ogr",
            )
            self.assertTrue(profile_layer.isValid())
            self.assertEqual(profile_layer.featureCount(), 8)
            profile_features = list(profile_layer.getFeatures())
            self.assertEqual(profile_features[0]["distance_label"], "0.0 km")
            self.assertEqual(profile_features[-1]["profile_point_ratio"], 1.0)

            toc_layer = QgsVectorLayer(
                f"{output_path}|layername=atlas_toc_entries",
                "qfit atlas toc entries",
                "ogr",
            )
            self.assertTrue(toc_layer.isValid())
            self.assertEqual(toc_layer.featureCount(), 2)
            toc_feature = next(toc_layer.getFeatures())
            self.assertEqual(toc_feature["page_number"], 1)
            self.assertEqual(toc_feature["toc_entry_label"], "1. 2026-03-20 · Morning Ride · 25.2 km · 1h 00m")

            background = self.layer_manager.ensure_background_layer(True, "Outdoor", "test-token")
            background_name = background.name()
            self.assertTrue(background.isValid())

            activities_layer, starts_layer, points_layer, atlas_layer = self.layer_manager.load_output_layers(output_path)
            self.layer_manager.apply_style(
                activities_layer,
                starts_layer,
                points_layer,
                atlas_layer,
                "By activity type",
                background_preset_name="Satellite",
            )

            self.assertTrue(activities_layer.isValid())
            self.assertTrue(starts_layer.isValid())
            self.assertTrue(points_layer.isValid())
            self.assertTrue(atlas_layer.isValid())
            self.assertEqual(activities_layer.featureCount(), 2)
            self.assertEqual(starts_layer.featureCount(), 2)
            self.assertGreaterEqual(points_layer.featureCount(), 4)
            self.assertEqual(atlas_layer.featureCount(), 2)

            renderer = activities_layer.renderer()
            self.assertEqual(renderer.classAttribute(), "sport_type")
            categories = {category.value(): category for category in renderer.categories()}
            self.assertEqual(set(categories), {"Ride", "Run"})
            self.assertEqual(round(activities_layer.opacity(), 2), 0.95)

            ride_symbol = categories["Ride"].symbol()
            run_symbol = categories["Run"].symbol()
            self.assertEqual(ride_symbol.symbolLayerCount(), 2)
            self.assertEqual(run_symbol.symbolLayerCount(), 2)
            self.assertEqual(ride_symbol.symbolLayer(0).color().name().upper(), "#FFFFFF")
            self.assertEqual(run_symbol.symbolLayer(0).color().name().upper(), "#FFFFFF")
            self.assertEqual(ride_symbol.symbolLayer(1).color().name().upper(), "#FF8E16")
            self.assertEqual(run_symbol.symbolLayer(1).color().name().upper(), "#DE3F3F")

            self.assertEqual(QgsProject.instance().crs().authid(), "EPSG:3857")
            self.assertEqual(self.iface.mapCanvas().destination_crs_authid, "EPSG:3857")
            self.assertIsNotNone(self.iface.mapCanvas().last_extent)
            self.assertGreaterEqual(self.iface.mapCanvas().refresh_count, 1)

            temporal_summary = self.layer_manager.apply_temporal_configuration(
                activities_layer,
                starts_layer,
                points_layer,
                atlas_layer,
                "Local activity time",
            )
            self.assertIn("activity tracks (LOCAL)", temporal_summary)
            self.assertIn("activity points (LOCAL)", temporal_summary)
            self.assertTrue(activities_layer.temporalProperties().isActive())
            self.assertEqual(
                activities_layer.temporalProperties().startExpression(),
                'to_datetime("start_date_local")',
            )
            self.assertTrue(points_layer.temporalProperties().isActive())
            self.assertEqual(
                points_layer.temporalProperties().startExpression(),
                'to_datetime("point_timestamp_local")',
            )

            atlas_feature = next(atlas_layer.getFeatures())
            self.assertEqual(atlas_feature["page_number"], 1)
            self.assertTrue(atlas_feature["page_name"])
            self.assertEqual(atlas_feature["profile_available"], 1)
            self.assertTrue(atlas_feature["profile_distance_label"])
            self.assertGreater(float(atlas_feature["extent_width_m"]), 0)
            self.assertGreater(float(atlas_feature["extent_height_m"]), 0)

            layer_order = self._layer_order()
            self.assertEqual(layer_order[-1], background_name)
            self.assertEqual(layer_order[:-1], [
                "qfit atlas pages",
                "qfit activity points",
                "qfit activity starts",
                "qfit activities",
            ])

            self.layer_manager.ensure_background_layer(False, "Outdoor", "test-token")
            self.assertNotIn(background_name, self._layer_order())

    def test_heatmap_preset_renderer_and_layer_visibility(self):
        """Heatmap preset must produce a density-based renderer and suppress other layers."""
        from qgis.core import QgsHeatmapRenderer, QgsUnitTypes

        with tempfile.TemporaryDirectory() as tmp:
            output_path = self._write_sample_gpkg(tmp)
            activities_layer, starts_layer, points_layer, atlas_layer = (
                self.layer_manager.load_output_layers(output_path)
            )

            self.layer_manager.apply_style(
                activities_layer,
                starts_layer,
                points_layer,
                atlas_layer,
                "Heatmap",
            )

            # Points layer carries the heatmap renderer
            renderer = points_layer.renderer()
            self.assertIsInstance(renderer, QgsHeatmapRenderer)
            self.assertEqual(renderer.radius(), 12)
            self.assertEqual(renderer.radiusUnit(), QgsUnitTypes.RenderMillimeters)
            self.assertEqual(renderer.renderQuality(), 2)
            self.assertIsNotNone(renderer.colorRamp())
            self.assertEqual(renderer.colorRamp().color1().alpha(), 0)
            self.assertTrue(renderer.colorRamp().stops(), "Heatmap ramp should include intermediate transparent/soft stops")
            self.assertEqual(round(points_layer.opacity(), 2), 0.75)

            # Tracks and start points must be fully hidden so they don't flatten the visual
            self.assertEqual(round(activities_layer.opacity(), 2), 0.0)
            self.assertEqual(round(starts_layer.opacity(), 2), 0.0)

    def test_heatmap_preset_falls_back_to_starts_layer(self):
        """When points_layer is None the heatmap should render on starts_layer."""
        from qgis.core import QgsHeatmapRenderer

        with tempfile.TemporaryDirectory() as tmp:
            output_path = self._write_sample_gpkg(tmp)
            activities_layer, starts_layer, _points_layer, atlas_layer = (
                self.layer_manager.load_output_layers(output_path)
            )

            self.layer_manager.apply_style(
                activities_layer,
                starts_layer,
                None,  # no points layer
                atlas_layer,
                "Heatmap",
            )

            self.assertIsInstance(starts_layer.renderer(), QgsHeatmapRenderer)
            self.assertEqual(round(starts_layer.opacity(), 2), 0.75)
            self.assertEqual(round(activities_layer.opacity(), 2), 0.0)

    def test_offscreen_profile_chart_export_contains_rendered_curve(self):
        """Bound profile exports should differ visibly from the same chart when cleared."""
        script = textwrap.dedent(
            """
            import os
            import sys
            import tempfile
            from pathlib import Path

            os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
            sys.path.insert(0, "/home/ebelo/.openclaw/workspace")

            from qgis.core import QgsApplication, QgsLayoutExporter, QgsProject, QgsRectangle
            from qgis.PyQt.QtGui import QImage

            from qfit.atlas.export_task import (
                BUILTIN_ATLAS_MAP_TARGET_ASPECT_RATIO,
                PAGE_HEIGHT_MM,
                PAGE_WIDTH_MM,
                PROFILE_CHART_H,
                PROFILE_CHART_Y,
                PROFILE_W,
                PROFILE_X,
                _PROFILE_PICTURE_ID,
                _apply_page_profile_payload,
                _build_page_profile_payload,
                _normalize_extent_to_aspect_ratio,
                build_atlas_layout,
            )
            from qfit.atlas.profile_item import build_profile_item_adapter
            from qfit.gpkg_writer import GeoPackageWriter
            from qfit.layer_manager import LayerManager

            class _FakeCanvas:
                def __init__(self):
                    self.last_extent = None
                def setDestinationCrs(self, crs):
                    pass
                def setExtent(self, extent):
                    self.last_extent = extent
                def extent(self):
                    return self.last_extent
                def refresh(self):
                    pass

            class _FakeIface:
                def __init__(self):
                    self._canvas = _FakeCanvas()
                def mapCanvas(self):
                    return self._canvas

            def count_changed_pixels(bound_path, blank_path):
                bound = QImage(bound_path)
                blank = QImage(blank_path)
                if bound.isNull() or blank.isNull() or bound.size() != blank.size():
                    raise RuntimeError("Failed to load exported profile smoke-test images")

                scale_x = bound.width() / PAGE_WIDTH_MM
                scale_y = bound.height() / PAGE_HEIGHT_MM
                x0 = int(PROFILE_X * scale_x)
                y0 = int(PROFILE_CHART_Y * scale_y)
                width = int(PROFILE_W * scale_x)
                height = int(PROFILE_CHART_H * scale_y)

                changed = 0
                for y in range(y0, y0 + height):
                    for x in range(x0, x0 + width):
                        a = bound.pixelColor(x, y)
                        b = blank.pixelColor(x, y)
                        delta = abs(a.red() - b.red()) + abs(a.green() - b.green()) + abs(a.blue() - b.blue())
                        if delta > 30:
                            changed += 1
                return changed

            app = QgsApplication([], False)
            app.initQgis()
            with tempfile.TemporaryDirectory() as tmp:
                    output_path = str(Path(tmp) / "qfit-profile-smoke.gpkg")
                    GeoPackageWriter(
                        output_path,
                        write_activity_points=True,
                        point_stride=1,
                        atlas_margin_percent=10,
                        atlas_min_extent_degrees=0.01,
                        atlas_target_aspect_ratio=1.0,
                    ).write_activities([
                        {
                            "source": "strava",
                            "source_activity_id": "profile-1",
                            "external_id": "strava-profile-1",
                            "name": "Profile Smoke Ride",
                            "activity_type": "Ride",
                            "sport_type": "Ride",
                            "start_date": "2026-03-22T07:00:00+00:00",
                            "start_date_local": "2026-03-22T08:00:00+01:00",
                            "timezone": "Europe/Zurich",
                            "distance_m": 30000,
                            "moving_time_s": 4200,
                            "elapsed_time_s": 4320,
                            "total_elevation_gain_m": 540,
                            "start_lat": 46.5000,
                            "start_lon": 6.6000,
                            "end_lat": 46.5900,
                            "end_lon": 6.7800,
                            "geometry_source": "stream",
                            "geometry_points": [
                                (46.5000, 6.6000),
                                (46.5080, 6.6180),
                                (46.5200, 6.6400),
                                (46.5340, 6.6650),
                                (46.5480, 6.6980),
                                (46.5600, 6.7240),
                                (46.5720, 6.7480),
                                (46.5900, 6.7800),
                            ],
                            "details_json": {
                                "stream_metrics": {
                                    "time": [0, 600, 1200, 1800, 2400, 3000, 3600, 4200],
                                    "distance": [0, 4200, 8600, 12800, 17200, 21400, 25600, 30000],
                                    "altitude": [410, 515, 470, 620, 560, 710, 650, 780],
                                    "moving": [True, True, True, True, True, True, True, True],
                                }
                            },
                        }
                    ], sync_metadata={"provider": "strava"})

                    layer_manager = LayerManager(_FakeIface())
                    QgsProject.instance().clear()
                    activities_layer, starts_layer, points_layer, atlas_layer = layer_manager.load_output_layers(output_path)
                    layer_manager.apply_style(
                        activities_layer,
                        starts_layer,
                        points_layer,
                        atlas_layer,
                        "By activity type",
                        background_preset_name="Satellite",
                    )

                    layout = build_atlas_layout(atlas_layer, project=QgsProject.instance())
                    atlas = layout.atlas()
                    atlas.beginRender()
                    atlas.updateFeatures()
                    try:
                        if not atlas.first():
                            raise RuntimeError("Atlas smoke test found no pages")

                        map_item = next(
                            item
                            for item in layout.items()
                            if callable(getattr(item, "setExtent", None)) and callable(getattr(item, "layers", None))
                        )
                        profile_item = next(
                            item for item in layout.items() if getattr(item, "id", lambda: None)() == _PROFILE_PICTURE_ID
                        )
                        profile_adapter = build_profile_item_adapter(profile_item)

                        current_feature = atlas.layout().reportContext().feature()
                        filterable_layers = []
                        for layer in map_item.layers():
                            try:
                                if layer.fields().indexOf("source_activity_id") >= 0:
                                    filterable_layers.append((layer, layer.subsetString()))
                            except Exception:
                                continue

                        profile_payload = _build_page_profile_payload(current_feature, filterable_layers)
                        _apply_page_profile_payload(profile_adapter, profile_payload)

                        extent = QgsRectangle(
                            float(current_feature["center_x_3857"]) - float(current_feature["extent_width_m"]) / 2.0,
                            float(current_feature["center_y_3857"]) - float(current_feature["extent_height_m"]) / 2.0,
                            float(current_feature["center_x_3857"]) + float(current_feature["extent_width_m"]) / 2.0,
                            float(current_feature["center_y_3857"]) + float(current_feature["extent_height_m"]) / 2.0,
                        )
                        map_item.setExtent(
                            _normalize_extent_to_aspect_ratio(extent, BUILTIN_ATLAS_MAP_TARGET_ASPECT_RATIO)
                        )
                        map_item.refresh()

                        exporter = QgsLayoutExporter(layout)
                        image_settings = QgsLayoutExporter.ImageExportSettings()
                        image_settings.dpi = 150
                        bound_path = str(Path(tmp) / "profile-bound.png")
                        blank_path = str(Path(tmp) / "profile-blank.png")
                        if exporter.exportToImage(bound_path, image_settings) != QgsLayoutExporter.Success:
                            raise RuntimeError("Bound profile image export failed")
                        profile_adapter.clear_profile()
                        if exporter.exportToImage(blank_path, image_settings) != QgsLayoutExporter.Success:
                            raise RuntimeError("Blank profile image export failed")

                        print(count_changed_pixels(bound_path, blank_path), flush=True)
                        os._exit(0)
                    finally:
                        atlas.endRender()
                        QgsProject.instance().clear()
            """
        )

        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
            env={**os.environ, "QT_QPA_PLATFORM": "offscreen"},
            timeout=180,
        )

        self.assertEqual(
            result.returncode,
            0,
            f"Profile smoke subprocess failed with code {result.returncode}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}",
        )
        changed_pixels = int(result.stdout.strip().splitlines()[-1])
        self.assertGreater(
            changed_pixels,
            80,
            f"Expected rendered profile content in exported chart, but only {changed_pixels} profile-chart pixels changed",
        )

    def _write_sample_gpkg(self, temp_dir):
        output_path = str(Path(temp_dir) / "qfit-heatmap-test.gpkg")
        GeoPackageWriter(
            output_path,
            write_activity_points=True,
            point_stride=2,
            atlas_margin_percent=10,
            atlas_min_extent_degrees=0.01,
            atlas_target_aspect_ratio=1.5,
        ).write_activities(self._sample_activities(), sync_metadata={"provider": "strava"})
        return output_path


    def _layer_order(self):
        names = []
        for child in QgsProject.instance().layerTreeRoot().children():
            layer = child.layer() if hasattr(child, "layer") else None
            if layer is not None:
                names.append(layer.name())
        return names

    def _sample_activities(self):
        return [
            {
                "source": "strava",
                "source_activity_id": "1001",
                "external_id": "strava-1001",
                "name": "Morning Ride",
                "activity_type": "Ride",
                "sport_type": "Ride",
                "start_date": "2026-03-20T07:00:00+00:00",
                "start_date_local": "2026-03-20T08:00:00+01:00",
                "timezone": "Europe/Zurich",
                "distance_m": 25200,
                "moving_time_s": 3600,
                "elapsed_time_s": 3900,
                "total_elevation_gain_m": 320,
                "start_lat": 46.5200,
                "start_lon": 6.6200,
                "end_lat": 46.5700,
                "end_lon": 6.7400,
                "geometry_source": "stream",
                "geometry_points": [
                    (46.5200, 6.6200),
                    (46.5350, 6.6550),
                    (46.5480, 6.7000),
                    (46.5700, 6.7400),
                ],
                "details_json": {
                    "stream_metrics": {
                        "time": [0, 1200, 2400, 3600],
                        "distance": [0, 8400, 16800, 25200],
                        "altitude": [450, 510, 480, 530],
                        "moving": [True, True, True, True],
                    }
                },
            },
            {
                "source": "strava",
                "source_activity_id": "1002",
                "external_id": "strava-1002",
                "name": "Lunch Run",
                "activity_type": "Run",
                "sport_type": "Run",
                "start_date": "2026-03-21T11:30:00+00:00",
                "start_date_local": "2026-03-21T12:30:00+01:00",
                "timezone": "Europe/Zurich",
                "distance_m": 10100,
                "moving_time_s": 3000,
                "elapsed_time_s": 3120,
                "total_elevation_gain_m": 85,
                "start_lat": 46.5100,
                "start_lon": 6.6000,
                "end_lat": 46.5250,
                "end_lon": 6.6300,
                "geometry_source": "stream",
                "geometry_points": [
                    (46.5100, 6.6000),
                    (46.5140, 6.6090),
                    (46.5190, 6.6200),
                    (46.5250, 6.6300),
                ],
                "details_json": {
                    "stream_metrics": {
                        "time": [0, 1000, 2000, 3000],
                        "distance": [0, 3300, 6700, 10100],
                        "altitude": [430, 445, 438, 452],
                        "moving": [True, True, True, True],
                    }
                },
            },
        ]


if __name__ == "__main__":
    unittest.main()
