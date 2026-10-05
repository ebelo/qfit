import os
import sqlite3
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from tests import _path  # noqa: F401
from tests.qgis_app import get_shared_qgis_app

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
REPO_ROOT = Path(__file__).resolve().parents[1]

# When Docker QGIS tests run, they set QFIT_REQUIRE_QGIS=1 so that import
# failures are hard errors instead of silent skips.  This prevents Qt 6
# enum-migration crashes from hiding behind a broad try/except guard.
_REQUIRE_QGIS = os.environ.get("QFIT_REQUIRE_QGIS") == "1"

if _REQUIRE_QGIS:
    # Several pure unit tests install fake qgis modules during collection so
    # they can import QGIS-facing code without a real QGIS runtime. Docker
    # smoke tests must not inherit those fakes; reset QGIS modules before
    # importing the real plugin stack.
    for module_name in list(sys.modules):
        if module_name == "qgis" or module_name.startswith("qgis."):
            sys.modules.pop(module_name, None)

try:
    from qgis.core import (
        QgsApplication,
        QgsCoordinateReferenceSystem,
        QgsCoordinateTransform,
        QgsFeature,
        QgsLayoutExporter,
        QgsMapRendererSequentialJob,
        QgsMapSettings,
        QgsProject,
        QgsRectangle,
        QgsVectorLayer,
    )
    from qgis.PyQt.QtCore import QDate, Qt, QTimer
    from qgis.PyQt.QtGui import QImage
    from qgis.PyQt.QtWidgets import QApplication, QFormLayout, QMessageBox

    from qfit.ui.qt_enum_compat import qt_class_enum_value, qt_enum_value

    from qfit.activities.domain.activity_query import ActivityQuery, build_subset_string
    from qfit.analysis.infrastructure.frequent_start_points_layer import (
        build_frequent_start_points_layer,
    )
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
    from qfit.configuration.infrastructure.credential_store import InMemoryCredentialStore
    from qfit.activities.infrastructure.geopackage.gpkg_writer import GeoPackageWriter
    from qfit.visualization.infrastructure.qgis_layer_gateway import (
        QgisLayerGateway as LayerManager,
    )
    from qfit.mapbox_config import TILE_MODE_RASTER
    from qfit.activities.domain.models import Activity
    from qfit.qfit_config_dialog import QfitConfigDialog
    from qfit.qfit_dockwidget import ApplyVisualizationAction, QfitDockWidget
    from qfit.ui.dockwidget.action_row import QT_BOX_LAYOUT_TOP_TO_BOTTOM
    from qfit.ui.application.local_first_control_visibility import (
        update_local_first_mapbox_custom_style_visibility,
        update_local_first_point_sampling_visibility,
    )
    from qfit.configuration.application.settings_service import SettingsService
    from qfit.ui.dockwidget_dependencies import build_dockwidget_dependencies
    from qfit.visualization.application.visual_apply import VisualApplyService
    from qfit.visualization.application.temporal_config import DEFAULT_TEMPORAL_MODE_LABEL

    QGIS_AVAILABLE = True
    QGIS_IMPORT_ERROR = None
except Exception as exc:
    if _REQUIRE_QGIS:
        # Inside Docker QGIS tests, import failures must crash, not skip.
        # This is what catches Qt 6 enum-migration issues that a broad
        # try/except would otherwise swallow into a silent skip.
        raise
    QgsApplication = None
    QgsCoordinateReferenceSystem = None
    QgsFeature = None
    QgsLayoutExporter = None
    QgsProject = None
    QgsRectangle = None
    QgsVectorLayer = None
    QDate = None
    QImage = None
    QFormLayout = None
    Qt = None
    ActivityQuery = None
    build_subset_string = None
    build_frequent_start_points_layer = None
    GeoPackageWriter = None
    LayerManager = None
    TILE_MODE_RASTER = None
    Activity = None
    QfitConfigDialog = None
    QfitDockWidget = None
    update_local_first_mapbox_custom_style_visibility = None
    update_local_first_point_sampling_visibility = None
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

    def get(self, key, default=None):
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
        cls.qgs = get_shared_qgis_app(QgsApplication)

    @classmethod
    def tearDownClass(cls):
        QgsProject.instance().clear()

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
            self.assertIs(dock.project_hygiene_service, dependencies.project_hygiene_service)
            self.assertIs(dock.load_workflow, dependencies.load_workflow)
            self.assertIs(dock.visual_apply, dependencies.visual_apply)
            self.assertIs(dock.atlas_export_service, dependencies.atlas_export_service)
            self.assertIs(dock.activity_workflow, dependencies.activity_workflow)
            self.assertIs(dock.cache, dependencies.cache)
        finally:
            dock.close()
            dock.deleteLater()

    def test_dock_widget_delegates_startup_to_coordinator(self):
        dependencies = build_dockwidget_dependencies(self.iface)

        with patch("qfit.qfit_dockwidget.DockStartupCoordinator") as startup_coordinator:
            startup_coordinator.return_value.run.return_value = MagicMock()
            dock = QfitDockWidget(self.iface, dependencies=dependencies)
        try:
            startup_coordinator.assert_called_once_with(dock)
            startup_coordinator.return_value.run.assert_called_once_with()
            self.assertFalse(hasattr(dock, "_workflow_section_coordinator"))
            self.assertIs(dock._dock_startup_coordinator, startup_coordinator.return_value)
            self.assertIs(dock._startup_result, startup_coordinator.return_value.run.return_value)
        finally:
            dock.close()
            dock.deleteLater()

    def _run_with_message_box_response(self, callback, response):
        """Click a real modal button; stop both timers even if the callback fails."""
        seen = []
        errors = []
        responder = QTimer()
        watchdog = QTimer()
        watchdog.setSingleShot(True)

        def respond():
            box = QApplication.activeModalWidget()
            if not isinstance(box, QMessageBox):
                return
            responder.stop()
            try:
                seen.append({
                    "title": box.windowTitle(), "text": box.text(),
                    "details": box.detailedText(), "buttons": box.standardButtons(),
                    "default": box.standardButton(box.defaultButton()),
                })
                button = box.button(response)
                if button is None:
                    raise AssertionError("Expected response button is missing")
                button.click()
            except Exception as exc:
                errors.append(str(exc))
                box.reject()

        def timeout():
            errors.append("Modal dialog did not complete within the test deadline")
            responder.stop()
            box = QApplication.activeModalWidget()
            if isinstance(box, QMessageBox):
                box.reject()

        responder.timeout.connect(respond)
        watchdog.timeout.connect(timeout)
        responder.start(10)
        watchdog.start(3000)
        try:
            callback()
        finally:
            responder.stop()
            watchdog.stop()
        self.assertEqual(errors, [])
        self.assertEqual(len(seen), 1)
        return seen[0]

    @staticmethod
    def _dialog_test_preflight():
        from qfit.providers.infrastructure.strava_bulk_archive import BulkArchivePreflight
        return BulkArchivePreflight(
            archive_fingerprint="synthetic-fingerprint", activity_count=1,
            referenced_file_count=1, summary_only_count=0, conflict_count=0,
            missing_file_count=0, unsupported_file_count=0,
            referenced_expanded_bytes=1024, format_counts={"gpx": 1},
        )

    def test_bulk_import_confirmation_real_dialog_yes_and_no(self):
        yes = qt_class_enum_value(QMessageBox, "StandardButton", "Yes")
        no = qt_class_enum_value(QMessageBox, "StandardButton", "No")
        for response in (no, yes):
            with self.subTest(response=response), tempfile.TemporaryDirectory() as temp_dir:
                dock = QfitDockWidget(self.iface)
                output_path = str(Path(temp_dir) / "not-created.gpkg")
                archive_path = str(Path(temp_dir) / "not-opened.zip")
                workflow = MagicMock()
                dock._bulk_archive_path = archive_path
                try:
                    with patch("qfit.qfit_dockwidget.QgsApplication.taskManager") as manager:
                        dialog = self._run_with_message_box_response(
                            lambda: dock._handle_bulk_preflight_finished(
                                workflow, output_path, self._dialog_test_preflight(), None, False,
                            ), response,
                        )
                    self.assertEqual(dialog["buttons"], yes | no)
                    self.assertEqual(dialog["default"], no)
                    self.assertEqual(dialog["title"], "Import Strava bulk export")
                    self.assertIn("Activities: 1", dialog["text"])
                    workflow.run.assert_not_called()
                    self.assertFalse(Path(output_path).exists())
                    if response == yes:
                        task = dock._bulk_import_task
                        manager.return_value.addTask.assert_called_once_with(task)
                        self.assertEqual(task._request.archive_path, archive_path)
                        self.assertEqual(task._request.output_path, output_path)
                        self.assertEqual(task._request.expected_archive_fingerprint, "synthetic-fingerprint")
                        self.assertEqual(dock._bulk_destination_path, output_path)
                    else:
                        manager.return_value.addTask.assert_not_called()
                        self.assertIsNone(dock._bulk_archive_path)
                        self.assertIsNone(dock._bulk_import_task)
                finally:
                    dock._bulk_import_task = None
                    dock.close()
                    dock.deleteLater()

    def test_clear_database_confirmation_real_dialog_yes_and_no(self):
        yes = qt_class_enum_value(QMessageBox, "StandardButton", "Yes")
        no = qt_class_enum_value(QMessageBox, "StandardButton", "No")
        for response in (no, yes):
            with self.subTest(response=response), tempfile.TemporaryDirectory() as temp_dir:
                output_path = self._write_sample_gpkg_without_points(temp_dir)
                before = Path(output_path).read_bytes()
                dock = QfitDockWidget(self.iface)
                workflow = MagicMock()
                workflow.clear_database_request.return_value = SimpleNamespace(status="Database cleared")
                try:
                    dock.outputPathLineEdit.setText(str(output_path))
                    with patch.object(dock, "_clear_database_workflow_service", return_value=workflow) as service:
                        dialog = self._run_with_message_box_response(
                            dock.on_clear_database_clicked, response,
                        )
                    self.assertEqual(dialog["buttons"], yes | no)
                    self.assertEqual(dialog["default"], no)
                    self.assertEqual(Path(output_path).read_bytes(), before)
                    if response == yes:
                        service.assert_called_once_with()
                        self.assertEqual(workflow.build_clear_database_request.call_args.kwargs["output_path"], str(output_path))
                        workflow.clear_database_request.assert_called_once_with(
                            workflow.build_clear_database_request.return_value,
                        )
                    else:
                        service.assert_not_called()
                        workflow.clear_database_request.assert_not_called()
                finally:
                    dock.close()
                    dock.deleteLater()

    def test_bulk_import_completion_real_dialog_preserves_stored_result(self):
        from qfit.activities.application.strava_bulk_import import StravaBulkImportResult
        ok = qt_class_enum_value(QMessageBox, "StandardButton", "Ok")
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = self._write_sample_gpkg_without_points(temp_dir)
            before = Path(output_path).read_bytes()
            dock = QfitDockWidget(self.iface)
            result = StravaBulkImportResult(
                preflight=self._dialog_test_preflight(), inserted=1, total_stored=1,
            )
            dock._bulk_destination_path = str(output_path)
            dock._bulk_import_task = object()
            dock._bulk_archive_path = "synthetic.zip"
            try:
                dialog = self._run_with_message_box_response(
                    lambda: dock._handle_bulk_import_finished(result, None, False), ok,
                )
                self.assertEqual(dialog["title"], "Strava bulk import complete")
                self.assertEqual(dialog["buttons"], ok)
                self.assertIn("Imported 1 activities: 1 inserted", dialog["text"])
                self.assertEqual(dialog["details"], result.private_diagnostic_report())
                self.assertEqual(dock.output_path, str(output_path))
                self.assertEqual(dock.runtime_state.stored_activity_count, 1)
                self.assertIsNone(dock._bulk_import_task)
                self.assertIsNone(dock._bulk_archive_path)
                self.assertIsNone(dock._bulk_destination_path)
                self.assertEqual(Path(output_path).read_bytes(), before)
            finally:
                dock.close()
                dock.deleteLater()

    def test_dock_widget_defaults_to_local_first_live_path(self):
        dock = QfitDockWidget(self.iface)
        try:
            self.assertTrue(dock._local_first_live_path_installed)
            self.assertEqual(
                dock._local_first_live_shell.objectName(),
                "qfitLocalFirstDockShell",
            )
            self.assertIs(
                dock._local_first_dock_composition.shell,
                dock._local_first_live_shell,
            )
            self.assertEqual(dock._local_first_live_shell.page_count(), 5)
            self.assertEqual(dock._local_first_live_shell.current_key(), "data")
            self.assertTrue(dock.scrollArea.isHidden())
            self.assertTrue(dock.summaryStatusLabel.isHidden())
            self.assertGreaterEqual(
                dock.outerLayout.indexOf(dock._local_first_live_shell),
                0,
            )
        finally:
            dock.close()
            dock.deleteLater()

    def test_live_dock_initializes_database_name_action_from_saved_settings(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = self._write_sample_gpkg_without_points(temp_dir)
            settings = SettingsService(
                qsettings=_FakeQSettings(),
                credential_store=InMemoryCredentialStore(),
            )
            for key in ("client_id", "client_secret", "refresh_token"):
                settings.set(key, "configured-test-value")
            settings.set("output_path", str(output_path))
            dependencies = replace(
                build_dockwidget_dependencies(self.iface), settings=settings,
            )
            dock = QfitDockWidget(self.iface, dependencies=dependencies)
            try:
                # No later runtime refresh or output-path edit should be needed.
                self.assertTrue(dock.refreshActivityNamesAction.isEnabled())
                self.assertEqual(dock.refreshActivityNamesAction.text(), "Refresh activity names…")
            finally:
                dock.close()
                dock.deleteLater()

    def test_live_dock_exposes_name_refresh_cancellation(self):
        from qfit.activities.application.activity_name_refresh_task import ActivityNameRefreshTask
        dock = QfitDockWidget(self.iface)
        task = ActivityNameRefreshTask(object(), "unused.gpkg")
        try:
            dock._runtime_store().begin_fetch(task)
            dock._refresh_local_first_dock_from_runtime()
            dock.resize(420, 900)
            dock.show()
            self.qgs.processEvents()
            dock._local_first_live_shell.show_page_key("settings")
            self.qgs.processEvents()
            self.assertTrue(dock.databaseActionsButton.isVisible())
            self.assertIn(dock.refreshActivityNamesAction, dock.databaseActionsMenu.actions())
            self.assertTrue(dock.refreshActivityNamesAction.isEnabled())
            self.assertEqual(dock.refreshActivityNamesAction.text(), "Cancel name refresh")
            self.assertFalse(hasattr(dock._local_first_dock_composition.sync_content, "names_button"))
            dock.refreshActivityNamesAction.trigger()
            self.assertTrue(task.isCanceled())
            self.assertIs(dock._fetch_task, task)
        finally:
            dock._runtime_store().clear_fetch()
            dock.close()
            dock.deleteLater()

    def test_narrow_dock_keeps_all_local_first_navigation_items_visible(self):
        dock = QfitDockWidget(self.iface)
        try:
            dock.resize(420, 900)
            dock.show()
            self.qgs.processEvents()

            shell = dock._local_first_live_shell
            items = shell.navigation_items()
            self.assertEqual(
                [item.text() for item in items],
                ["Data", "Map", "Analysis", "Atlas", "Settings"],
            )
            self.assertTrue(all(item.isVisible() for item in items))
            self.assertTrue(all(item.label().isVisible() for item in items))
            self.assertTrue(all(item.geometry().height() > 0 for item in items))
            self.assertEqual(shell.page_count(), 5)

            action_row = dock._local_first_dock_composition.sync_content.action_row
            action_row.set_responsive_width(320)
            self.assertEqual(action_row.property("responsiveMode"), "narrow")
            self.assertEqual(
                action_row.outer_layout().direction(),
                QT_BOX_LAYOUT_TOP_TO_BOTTOM,
            )
        finally:
            dock.close()
            dock.deleteLater()

    def test_dock_widget_contextual_help_smoke(self):
        dependencies = replace(
            build_dockwidget_dependencies(self.iface),
            settings=SettingsService(
                qsettings=_FakeQSettings(),
                credential_store=InMemoryCredentialStore(),
            ),
        )
        dock = QfitDockWidget(self.iface, dependencies=dependencies)
        try:
            from qgis.PyQt.QtWidgets import QComboBox, QLabel, QWidget

            self.assertEqual(dock.pointSamplingStrideLabel.text(), "Keep every Nth point")
            self.assertEqual(dock.workflowLabel.text(), "Sections: Fetch & store · Visualize · Analyze · Publish")
            for removed_attr in (
                "credentialsGroupBox",
                "clientIdLineEdit",
                "clientSecretLineEdit",
                "redirectUriLineEdit",
                "authCodeLineEdit",
                "refreshTokenLineEdit",
                "openAuthorizeButton",
                "exchangeCodeButton",
            ):
                with self.subTest(removed_attr=removed_attr):
                    self.assertFalse(hasattr(dock, removed_attr))
            self.assertTrue(
                bool(
                    dock.features()
                    & qt_class_enum_value(
                        type(dock), "DockWidgetFeature", "DockWidgetMovable"
                    )
                )
            )
            self.assertTrue(
                bool(
                    dock.features()
                    & qt_class_enum_value(
                        type(dock), "DockWidgetFeature", "DockWidgetFloatable"
                    )
                )
            )
            self.assertEqual(dock.activitiesGroupBox.title(), "")
            self.assertFalse(hasattr(dock, "activitiesSectionToggleButton"))
            self.assertFalse(hasattr(dock, "activitiesSectionContentWidget"))
            self.assertTrue(dock.activitiesIntroLabel.isHidden())
            self.assertIn("saved in qfit → Configuration", dock.activitiesGroupBox.toolTip())
            self.assertFalse(dock.mapboxAccessTokenLabel.isVisible())
            self.assertFalse(dock.mapboxAccessTokenLineEdit.isVisible())
            self.assertEqual(dock.refreshButton.text(), "Sync activities")
            self.assertEqual(dock.loadButton.text(), "Store activities")
            self.assertEqual(dock.loadLayersButton.text(), "Load stored map layers")
            self.assertEqual(dock.clearDatabaseButton.text(), "Clear database…")
            self.assertEqual(dock.applyFiltersButton.text(), "Apply filters")
            self.assertTrue(dock.writeActivityPointsCheckBox.isChecked())
            self.assertFalse(dock.pointSamplingStrideSpinBox.isHidden())
            self.assertFalse(dock.backgroundHelpLabel.isVisible())
            self.assertFalse(dock.analysisHelpLabel.isVisible())
            self.assertFalse(dock.publishHelpLabel.isVisible())
            for removed_temporal_attr in (
                "analysisTemporalModeRow",
                "temporalModeLabel",
                "temporalModeComboBox",
                "temporalHelpLabel",
            ):
                with self.subTest(removed_temporal_attr=removed_temporal_attr):
                    self.assertFalse(hasattr(dock, removed_temporal_attr))
            self.assertTrue(dock.outputIntroLabel.isHidden())
            self.assertEqual(
                dock.outputGroupBox.toolTip(),
                "Pick where qfit should store the synced GeoPackage. Tracks and start points are always written; sampled point analysis is optional.",
            )
            self.assertEqual(dock.outputGroupBox.title(), "Data storage")
            self.assertEqual(
                dock.outputGroupBox.parentWidget(),
                dock._local_first_dock_composition.connection_content,
            )
            self.assertGreaterEqual(
                dock._local_first_dock_composition.connection_content.outer_layout().indexOf(
                    dock.outputGroupBox,
                ),
                0,
            )
            self.assertEqual(dock.previewGroupBox.title(), "Fetched activity preview")
            self.assertEqual(
                dock.previewGroupBox.parentWidget(),
                dock._local_first_dock_composition.sync_content,
            )
            self.assertGreaterEqual(
                dock._local_first_dock_composition.sync_content.outer_layout().indexOf(
                    dock.previewGroupBox,
                ),
                0,
            )
            self.assertEqual(dock.styleGroupBox.title(), "")
            self.assertEqual(
                dock.stylePresetComboBox.parentWidget(),
                dock._local_first_dock_composition.map_content.style_controls_panel,
            )
            self.assertGreaterEqual(
                dock._local_first_dock_composition.map_content.style_controls_layout().indexOf(
                    dock.stylePresetComboBox,
                ),
                0,
            )
            self.assertFalse(hasattr(dock, "styleSectionToggleButton"))
            self.assertFalse(hasattr(dock, "styleSectionContentWidget"))
            self.assertEqual(dock.loadLayersButton.parent(), dock.styleGroupBox)
            self.assertEqual(
                dock.backgroundGroupBox.parentWidget(),
                dock._local_first_dock_composition.connection_content,
            )
            self.assertGreaterEqual(
                dock._local_first_dock_composition.connection_content.outer_layout().indexOf(
                    dock.backgroundGroupBox,
                ),
                0,
            )
            self.assertEqual(dock.analysisWorkflowGroupBox.title(), "")
            self.assertFalse(hasattr(dock, "analysisSectionToggleButton"))
            self.assertFalse(hasattr(dock, "analysisSectionContentWidget"))
            self.assertEqual(dock.analysisWorkflowLayout.spacing(), 6)
            self.assertEqual(dock.analysisModeLabel.text(), "Analysis")
            self.assertEqual(dock.runAnalysisButton.text(), "Run analysis")
            self.assertEqual(
                dock.analysisModeLabel.parentWidget().parentWidget(),
                dock.analysisWorkflowGroupBox,
            )
            self.assertEqual(dock.publishGroupBox.title(), "")
            self.assertFalse(hasattr(dock, "publishSectionToggleButton"))
            self.assertFalse(hasattr(dock, "publishSectionContentWidget"))
            self.assertTrue(
                dock.publishSettingsWidget.parent() is dock.publishGroupBox
                or dock.publishSettingsWidget.isVisible()
            )
            self.assertTrue(dock.atlasPdfHelpLabel.isHidden())
            self.assertIn("per-activity PDF atlas", dock.atlasPdfGroupBox.toolTip())
            self.assertEqual(dock.generateAtlasPdfButton.toolTip(), dock.atlasPdfGroupBox.toolTip())
            self.assertEqual(dock.tileModeComboBox.currentText(), TILE_MODE_RASTER)
            self.assertEqual(dock.atlasTitleLineEdit.text(), "qfit Activity Atlas")
            self.assertEqual(dock.atlasSubtitleLineEdit.text(), "")
            self.assertFalse(hasattr(dock, "backfillMissingDetailedRoutesButton"))
            temporal_helper = dock.findChild(QLabel, "temporalModeComboBoxContextHelpLabel")
            self.assertIsNone(temporal_helper)
        finally:
            dock.close()
            dock.deleteLater()

    def test_map_filters_ignore_retired_route_detail_settings_on_startup_and_restore(self):
        from qgis.PyQt.QtWidgets import QWidget
        from qfit.activities.application.activity_preview import build_activity_preview_selection_state
        from qfit.activities.domain.activity_query import DETAILED_ROUTE_FILTER_ANY
        from qfit.ui.application.local_first_activity_controls import build_current_activity_preview_request
        from qfit.ui.application.local_first_filter_summary import build_local_first_filter_description

        for saved_value in (None, "present", "missing"):
            with self.subTest(saved_value=saved_value):
                settings = SettingsService(
                    qsettings=_FakeQSettings({"qfit/detailed_route_filter": saved_value}),
                    credential_store=InMemoryCredentialStore(),
                )
                dependencies = replace(build_dockwidget_dependencies(self.iface), settings=settings)
                dock = QfitDockWidget(self.iface, dependencies=dependencies)
                restored = None
                try:
                    dock.show()
                    self.qgs.processEvents()
                    self.assertFalse(hasattr(dock, "detailedRouteStatusComboBox"))
                    self.assertFalse(hasattr(dock, "detailedOnlyCheckBox"))
                    for name in ("detailedRouteStatusComboBox", "detailedOnlyCheckBox"):
                        self.assertIsNone(dock.findChild(QWidget, name))
                    self.assertTrue(dock._local_first_filter_controls_installed)
                    self.assertIs(dock.filterGroupBox.parentWidget(), dock._local_first_dock_composition.map_content.filter_controls_panel)
                    dock.activityTypeComboBox.setOptions(["All", "Walk", "Hike", "Run"])
                    dock.activityTypeComboBox.setSelectedTypes(["Walk", "Hike"])
                    dock.dateFromEdit.setDate(QDate(2026, 5, 1))
                    dock.dateToEdit.setDate(QDate(2026, 5, 31))
                    dock.minDistanceSpinBox.setValue(4)
                    dock.maxDistanceSpinBox.setValue(6)
                    dock.activitySearchLineEdit.setText("Morning")
                    activities = [
                        Activity(source="fixture", source_activity_id=str(i), activity_type=kind,
                                 sport_type=kind, geometry_source=geometry, name=name,
                                 distance_m=distance, start_date=f"{date}T10:00:00")
                        for i, (kind, geometry, name, distance, date) in enumerate([
                            ("Walk", "stream", "Morning walk", 5000, "2026-05-01"),
                            ("Walk", "summary_polyline", "Morning walk", 5000, "2026-05-01"),
                            ("Hike", None, "Morning hike", 5000, "2026-05-01"),
                            ("Run", "stream", "Morning run", 5000, "2026-05-01"),
                            ("Walk", "stream", "Evening walk", 5000, "2026-05-01"),
                            ("Walk", "stream", "Morning walk", 9000, "2026-05-01"),
                            ("Walk", "stream", "Morning walk", 5000, "2026-04-01"),
                        ])
                    ]
                    dock.activities = activities
                    layer = QgsVectorLayer("LineString?crs=EPSG:4326&field=activity_type:string&field=sport_type:string&field=start_date:string&field=distance_m:double&field=name:string&field=geometry_source:string", "Route detail migration", "memory")
                    for activity in activities:
                        feature = QgsFeature(layer.fields())
                        feature.setAttributes([activity.activity_type, activity.sport_type, activity.start_date,
                                               activity.distance_m, activity.name, activity.geometry_source])
                        layer.dataProvider().addFeatures([feature])
                    dock.activities_layer = layer
                    request = build_current_activity_preview_request(dock)
                    selection = build_activity_preview_selection_state(request)
                    self.assertEqual(selection.query.detailed_route_filter, DETAILED_ROUTE_FILTER_ANY)
                    self.assertEqual(selection.filtered_count, 3)
                    self.assertNotIn("routes:", build_local_first_filter_description(request))
                    dock.on_apply_filters_clicked()
                    self.assertEqual(layer.featureCount(), 3)
                    self.assertEqual(layer.subsetString(), build_subset_string(selection.query))
                    self.assertNotIn("geometry_source", layer.subsetString())
                    dock._save_settings()
                    restored = QfitDockWidget(self.iface, dependencies=dependencies)
                    restored.activities = activities
                    restored.dateFromEdit.setDate(dock.dateFromEdit.date())
                    restored.dateToEdit.setDate(dock.dateToEdit.date())
                    restored.minDistanceSpinBox.setValue(dock.minDistanceSpinBox.value())
                    restored_selection = build_activity_preview_selection_state(build_current_activity_preview_request(restored))
                    self.assertEqual(restored_selection.query.detailed_route_filter, DETAILED_ROUTE_FILTER_ANY)
                    self.assertEqual(restored_selection.filtered_count, 3)
                    self.assertEqual(restored.activityTypeComboBox.selectedTypes(), ("Hike", "Walk"))
                    self.assertEqual(settings.get("detailed_route_filter"), saved_value)
                finally:
                    if restored is not None:
                        restored.close()
                        restored.deleteLater()
                    dock.close()
                    dock.deleteLater()

    def test_multi_activity_type_selector_real_clicks_apply_map_filters_and_restore_settings(self):
        from qgis.PyQt.QtTest import QTest
        from qfit.ui.application.local_first_activity_controls import build_current_activity_preview_request
        from qfit.activities.application.activity_preview import build_activity_query
        from qfit.ui.widgets.activity_type_selector import ActivityTypeSelector
        settings = SettingsService(qsettings=_FakeQSettings(), credential_store=InMemoryCredentialStore())
        dependencies = replace(build_dockwidget_dependencies(self.iface), settings=settings)
        dock = QfitDockWidget(self.iface, dependencies=dependencies)
        restored = None
        try:
            selector = dock.activityTypeComboBox
            self.assertIsInstance(selector, ActivityTypeSelector)
            selector.setOptions(["All", "Walk", "Hike", "Run"])
            selector.resize(240, 35)
            selector.show()

            def click_type(label):
                selector.showPopup()
                self.qgs.processEvents()
                index = selector.model().index(selector.findText(label), 0)
                position = selector.view().visualRect(index).center()
                QTest.mouseClick(selector.view().viewport(), qt_enum_value(Qt, "MouseButton", "LeftButton"), pos=position)
                self.qgs.processEvents()
                selector.hidePopup()

            click_type("Walk")
            click_type("Hike")
            self.assertEqual(selector.selectedTypes(), ("Hike", "Walk"))
            layer = QgsVectorLayer("LineString?crs=EPSG:4326&field=activity_type:string&field=sport_type:string&field=start_date:string&field=distance_m:double&field=name:string&field=geometry_source:string", "Types", "memory")
            for label in ("Walk", "Hike", "Run"):
                feature = QgsFeature(layer.fields())
                feature.setAttributes([label, label, "2026-05-01T10:00:00", 5000, "Morning route", "stream"])
                layer.dataProvider().addFeatures([feature])
            dock.activities_layer = layer
            dock.dateFromEdit.setDate(QDate(2026, 1, 1))
            dock.dateToEdit.setDate(QDate(2026, 12, 31))
            dock.on_apply_filters_clicked()
            self.assertEqual({f["activity_type"] for f in layer.getFeatures()}, {"Walk", "Hike"})
            query = build_activity_query(build_current_activity_preview_request(dock))
            self.assertEqual(query.activity_types, ("Hike", "Walk"))
            self.assertEqual(layer.subsetString(), build_subset_string(query))
            dock._populate_activity_types_from_layer()
            self.assertEqual(selector.selectedTypes(), ("Hike", "Walk"))
            self.assertGreaterEqual(selector.findText("Run"), 0)
            self.assertEqual({f["activity_type"] for f in layer.getFeatures()}, {"Walk", "Hike"})
            dock._save_settings()
            restored = QfitDockWidget(self.iface, dependencies=dependencies)
            self.assertEqual(restored.activityTypeComboBox.selectedTypes(), ("Hike", "Walk"))
            click_type("All")
            self.assertEqual(selector.selectedTypes(), ())
            click_type("Walk")
            self.assertEqual(selector.selectedTypes(), ("Walk",))
            click_type("Walk")
            self.assertEqual(selector.selectedTypes(), ())
            selector.setSelectedTypes(["trail-run"])
            selector.setOptions(["All", "Trail Run", "Walk"])
            self.assertEqual([selector.itemText(i) for i in range(selector.count())], ["All", "Trail Run", "Walk"])
            self.assertEqual(selector.checkedItems(), ["Trail Run"])
            click_type("Trail Run")
            self.assertEqual(selector.selectedTypes(), ())
        finally:
            if restored is not None:
                restored.close()
                restored.deleteLater()
            dock.close()
            dock.deleteLater()

    def test_dock_widget_updates_local_first_visibility_rules(self):
        dock = QfitDockWidget(self.iface)
        try:
            update_local_first_point_sampling_visibility(dock, False)
            self.assertTrue(dock.pointSamplingStrideSpinBox.isHidden())
            update_local_first_point_sampling_visibility(dock, True)
            self.assertFalse(dock.pointSamplingStrideSpinBox.isHidden())

            update_local_first_mapbox_custom_style_visibility(dock, "Outdoor")
            self.assertTrue(dock.mapboxStyleOwnerLineEdit.isHidden())
            update_local_first_mapbox_custom_style_visibility(dock, "Custom")
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
        settings.set("client_id", "configured-client")
        settings.set("client_secret", "configured-secret")
        settings.set("redirect_uri", "http://localhost:8123/callback")
        settings.set("refresh_token", "configured-token")
        dependencies = replace(
            build_dockwidget_dependencies(self.iface),
            settings=settings,
        )

        dock = QfitDockWidget(self.iface, dependencies=dependencies)
        try:
            style_preset_text = dock.stylePresetComboBox.itemText(
                1 if dock.stylePresetComboBox.count() > 1 else 0
            )
            background_preset_text = dock.backgroundPresetComboBox.itemText(
                1 if dock.backgroundPresetComboBox.count() > 1 else 0
            )

            dock.outputPathLineEdit.setText("/tmp/roundtrip.gpkg")
            dock.backgroundMapCheckBox.setChecked(True)
            dock.backgroundPresetComboBox.setCurrentText(background_preset_text)
            dock.stylePresetComboBox.setCurrentText(style_preset_text)
            dock.analysisModeComboBox.setCurrentText("Most frequent starting points")
            dock.atlasTitleLineEdit.setText("Spring Atlas")
            dock.atlasSubtitleLineEdit.setText("Road and trail")
            dock.atlasPdfPathLineEdit.setText("/tmp/roundtrip.pdf")

            dock._save_settings()

            self.assertEqual(settings.get("client_id"), "configured-client")
            self.assertEqual(settings.get("client_secret"), "configured-secret")
            self.assertEqual(settings.get("redirect_uri"), "http://localhost:8123/callback")
            self.assertEqual(settings.get("refresh_token"), "configured-token")
            self.assertEqual(settings.get("output_path"), "/tmp/roundtrip.gpkg")
            self.assertIsNone(settings.get("per_page"))
            self.assertIsNone(settings.get("use_detailed_streams"))
            self.assertIsNone(settings.get("detailed_route_strategy"))
            self.assertTrue(settings.get_bool("use_background_map"))
            self.assertEqual(settings.get("background_preset"), background_preset_text)
            self.assertIsNone(settings.get("preview_sort"))
            self.assertEqual(settings.get("style_preset"), style_preset_text)
            self.assertIsNone(settings.get("temporal_mode"))
            self.assertEqual(settings.get("analysis_mode"), "Most frequent starting points")
            self.assertEqual(settings.get("atlas_title"), "Spring Atlas")
            self.assertEqual(settings.get("atlas_subtitle"), "Road and trail")
            self.assertEqual(settings.get("atlas_pdf_path"), "/tmp/roundtrip.pdf")
        finally:
            dock.close()
            dock.deleteLater()

        dock_reloaded = QfitDockWidget(self.iface, dependencies=dependencies)
        try:
            self.assertFalse(hasattr(dock_reloaded, "clientIdLineEdit"))
            self.assertEqual(settings.get("client_id"), "configured-client")
            self.assertEqual(dock_reloaded.outputPathLineEdit.text(), "/tmp/roundtrip.gpkg")
            self.assertTrue(dock_reloaded.backgroundMapCheckBox.isChecked())
            self.assertEqual(dock_reloaded.backgroundPresetComboBox.currentText(), background_preset_text)
            self.assertFalse(hasattr(dock_reloaded, "previewSortComboBox"))
            self.assertEqual(dock_reloaded.stylePresetComboBox.currentText(), style_preset_text)
            self.assertFalse(hasattr(dock_reloaded, "temporalModeComboBox"))
            self.assertEqual(dock_reloaded.analysisModeComboBox.currentText(), "Most frequent starting points")
            self.assertEqual(dock_reloaded.atlasTitleLineEdit.text(), "Spring Atlas")
            self.assertEqual(dock_reloaded.atlasSubtitleLineEdit.text(), "Road and trail")
            self.assertEqual(dock_reloaded.atlasPdfPathLineEdit.text(), "/tmp/roundtrip.pdf")
        finally:
            dock_reloaded.close()
            dock_reloaded.deleteLater()

    def test_dock_widget_ignores_legacy_temporal_mode_settings_and_uses_disabled_default(self):
        settings = SettingsService(
            qsettings=_FakeQSettings({"qfit/temporal_mode": "UTC time"}),
            credential_store=InMemoryCredentialStore(),
        )
        dependencies = replace(
            build_dockwidget_dependencies(self.iface),
            settings=settings,
        )

        dock = QfitDockWidget(self.iface, dependencies=dependencies)
        try:
            self.assertFalse(hasattr(dock, "temporalModeComboBox"))
            action = dock._build_visual_workflow_action(ApplyVisualizationAction)
            self.assertEqual(action.temporal_mode, DEFAULT_TEMPORAL_MODE_LABEL)
        finally:
            dock.close()
            dock.deleteLater()

    def test_generate_atlas_pdf_shows_clear_error_when_pypdf_is_missing(self):
        dock = QfitDockWidget(self.iface)
        try:
            dock.atlas_layer = MagicMock()
            dock.atlas_layer.featureCount.return_value = 3
            dock.atlasPdfPathLineEdit.setText("/tmp/qfit-atlas.pdf")
            dock.atlasTitleLineEdit.setText("Custom Atlas")
            dock.atlasSubtitleLineEdit.setText("April 2026")

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
            dock.atlasTitleLineEdit.setText("Custom Atlas")
            dock.atlasSubtitleLineEdit.setText("April 2026")

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
            self.assertEqual(export_command.atlas_title, "Custom Atlas")
            self.assertEqual(export_command.atlas_subtitle, "April 2026")
            self.assertEqual(export_command.profile_plot_style, "style-override")
            dock.atlas_export_use_case.start_export.assert_called_once_with(
                prepared_export,
                export_command,
            )
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
                dock.on_refresh_clicked()

            dock.sync_controller.build_fetch_task_request.assert_called_once()
            self.assertEqual(
                dock.sync_controller.build_fetch_task_request.call_args.kwargs["detailed_route_strategy"],
                "Recent fetch only",
            )
            self.assertEqual(dock.sync_controller.build_fetch_task_request.call_args.kwargs["per_page"], 200)
            self.assertEqual(dock.sync_controller.build_fetch_task_request.call_args.kwargs["max_pages"], 0)
            self.assertTrue(dock.sync_controller.build_fetch_task_request.call_args.kwargs["use_detailed_streams"])
            self.assertEqual(
                dock.sync_controller.build_fetch_task_request.call_args.kwargs[
                    "max_detailed_activities"
                ],
                0,
            )
            dock.sync_controller.build_fetch_task.assert_called_once_with("fetch-request")
            task_manager.return_value.addTask.assert_called_once_with(fake_task)
            self.assertIs(dock._fetch_task, fake_task)
            self.assertEqual(dock.refreshButton.text(), "Cancel")
        finally:
            dock.close()
            dock.deleteLater()

    def test_load_clicked_builds_background_store_task(self):
        dock = QfitDockWidget(self.iface)
        try:
            fake_task = MagicMock(name="store_task")
            dock._save_settings = MagicMock()
            dock._runtime_store().set_activities([{"id": 1}])
            dock.store_workflow.build_write_request = MagicMock(return_value="store-request")

            with (
                patch("qfit.qfit_dockwidget.build_store_task", return_value=fake_task) as build_store_task,
                patch("qfit.qfit_dockwidget.QgsApplication.taskManager") as task_manager,
            ):
                task_manager.return_value.addTask = MagicMock()
                dock.on_load_clicked()

            dock.store_workflow.build_write_request.assert_called_once()
            build_store_task.assert_called_once()
            self.assertEqual(build_store_task.call_args.args[:2], (dock.store_workflow, "store-request"))
            self.assertIs(build_store_task.call_args.kwargs["on_finished"].__self__, dock)
            task_manager.return_value.addTask.assert_called_once_with(fake_task)
            self.assertIs(dock._store_task, fake_task)
            self.assertEqual(dock.loadButton.text(), "Store in progress...")
            self.assertFalse(dock.loadButton.isEnabled())
        finally:
            dock.close()
            dock.deleteLater()

    def test_store_task_finished_restores_ui_and_updates_status(self):
        dock = QfitDockWidget(self.iface)
        try:
            dock._store_task = MagicMock(name="store_task")
            dock.loadButton.setEnabled(False)
            dock.loadButton.setText("Store in progress...")
            dock.settings = _FakeQSettings({"last_sync_date": "2026-04-07"})
            result = MagicMock(
                output_path="/tmp/qfit.gpkg",
                total_stored=12,
                status="Stored 12 activities",
            )

            dock._handle_store_task_finished(result, None, False)

            self.assertIsNone(dock._store_task)
            self.assertTrue(dock.loadButton.isEnabled())
            self.assertEqual(dock.loadButton.text(), "Store activities")
            self.assertEqual(dock.output_path, "/tmp/qfit.gpkg")
            self.assertIn("12 activities stored in database", dock.countLabel.text())
            self.assertEqual(dock.statusLabel.text(), "Stored 12 activities")
        finally:
            dock.close()
            dock.deleteLater()

    def test_refresh_clicked_cancels_existing_fetch_task(self):
        dock = QfitDockWidget(self.iface)
        try:
            running_task = MagicMock(name="running_fetch_task")
            dock._fetch_task = running_task

            dock.on_refresh_clicked()

            running_task.cancel.assert_called_once_with()
            self.assertIsNone(dock._fetch_task)
            self.assertEqual(dock.refreshButton.text(), "Sync activities")
            self.assertEqual(dock.statusLabel.text(), "Fetch cancelled.")
        finally:
            dock.close()
            dock.deleteLater()

    def test_refresh_clicked_reports_provider_error_without_starting_task(self):
        from qfit.providers.domain.provider import ProviderError

        dock = QfitDockWidget(self.iface)
        try:
            dock._save_settings = MagicMock()
            dock._show_error = MagicMock()
            dock.sync_controller.build_fetch_task_request = MagicMock(return_value="fetch-request")
            dock.sync_controller.build_fetch_task = MagicMock(side_effect=ProviderError("missing token"))

            dock.on_refresh_clicked()

            dock._show_error.assert_called_once_with("Strava import failed", "missing token")
            self.assertEqual(dock.statusLabel.text(), "Strava fetch failed")
            self.assertIsNone(dock._fetch_task)
            self.assertEqual(dock.refreshButton.text(), "Sync activities")
        finally:
            dock.close()
            dock.deleteLater()

    def test_config_dialog_exposes_strava_oauth_helper_controls(self):
        dialog = QfitConfigDialog(
            settings_service=SettingsService(
                qsettings=_FakeQSettings(),
                credential_store=InMemoryCredentialStore(),
            )
        )
        try:
            self.assertEqual(dialog._authorization_code_edit.objectName(), "cfgAuthorizationCodeEdit")
            self.assertEqual(dialog._open_authorize_button.objectName(), "cfgOpenAuthorizeButton")
            self.assertEqual(dialog._exchange_code_button.objectName(), "cfgExchangeCodeButton")
            self.assertIn("Do not paste", dialog._oauth_help_label.text())
            self.assertEqual(dialog._strava_oauth_status_label.text(), "Not started")
        finally:
            dialog.close()
            dialog.deleteLater()

    def test_config_dialog_uses_compact_content_sized_layout(self):
        dialog = QfitConfigDialog(
            settings_service=SettingsService(
                qsettings=_FakeQSettings(),
                credential_store=InMemoryCredentialStore(),
            )
        )
        try:
            self.assertEqual(dialog.layout().count(), 3)

            for label in (
                dialog._strava_status_label,
                dialog._strava_oauth_status_label,
                dialog._strava_test_status_label,
                dialog._mapbox_status_label,
                dialog._mapbox_test_status_label,
            ):
                self.assertTrue(label.wordWrap())

            form = dialog._oauth_help_label.parentWidget().layout()
            _row, role = form.getWidgetPosition(dialog._oauth_help_label)
            self.assertEqual(
                role,
                qt_class_enum_value(QFormLayout, "ItemRole", "SpanningRole"),
            )
            self.assertEqual(
                form.rowWrapPolicy(),
                qt_class_enum_value(QFormLayout, "RowWrapPolicy", "WrapLongRows"),
            )
        finally:
            dialog.close()
            dialog.deleteLater()

    def test_config_dialog_save_emits_settings_saved_signal(self):
        dialog = QfitConfigDialog(
            settings_service=SettingsService(
                qsettings=_FakeQSettings(),
                credential_store=InMemoryCredentialStore(),
            )
        )
        try:
            saves = []
            dialog.settingsSaved.connect(lambda: saves.append("saved"))

            dialog._client_id_edit.setText("client-id")
            dialog._save()

            self.assertEqual(saves, ["saved"])
        finally:
            dialog.close()
            dialog.deleteLater()

    def test_config_dialog_open_authorize_clicked_builds_authorize_url_via_sync_controller(self):
        dialog = QfitConfigDialog(
            settings_service=SettingsService(
                qsettings=_FakeQSettings(),
                credential_store=InMemoryCredentialStore(),
            )
        )
        try:
            dialog._save = MagicMock()
            dialog._sync_controller.build_authorize_request = MagicMock(return_value="authorize-request")
            dialog._sync_controller.build_authorize_url = MagicMock(return_value="https://strava.test/auth")

            with patch("qfit.qfit_config_dialog.QDesktopServices.openUrl", return_value=True) as open_url:
                dialog._open_strava_authorize_page()

            dialog._sync_controller.build_authorize_request.assert_called_once()
            dialog._sync_controller.build_authorize_url.assert_called_once_with("authorize-request")
            open_url.assert_called_once()
            self.assertIn("Strava authorization opened", dialog._strava_oauth_status_label.text())
        finally:
            dialog.close()
            dialog.deleteLater()

    def test_config_dialog_exchange_code_clicked_uses_sync_controller_exchange_workflow(self):
        dialog = QfitConfigDialog(
            settings_service=SettingsService(
                qsettings=_FakeQSettings(),
                credential_store=InMemoryCredentialStore(),
            )
        )
        try:
            dialog._authorization_code_edit.setText("abc123")
            dialog._save = MagicMock()
            dialog._sync_controller.build_exchange_code_request = MagicMock(return_value="exchange-request")
            dialog._sync_controller.exchange_code_for_tokens = MagicMock(
                return_value={
                    "refresh_token": "rtok",
                    "athlete": {"firstname": "Ada", "lastname": "Lovelace"},
                }
            )

            dialog._exchange_strava_code()

            dialog._sync_controller.build_exchange_code_request.assert_called_once()
            dialog._sync_controller.exchange_code_for_tokens.assert_called_once_with("exchange-request")
            self.assertEqual(dialog._refresh_token_edit.text(), "rtok")
            self.assertEqual(dialog._authorization_code_edit.text(), "")
            self.assertIn("Ada Lovelace", dialog._strava_oauth_status_label.text())
        finally:
            dialog.close()
            dialog.deleteLater()

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

            user_selected_crs = QgsCoordinateReferenceSystem("EPSG:3857")
            QgsProject.instance().setCrs(user_selected_crs)
            self.iface.mapCanvas().setDestinationCrs(user_selected_crs)

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
            self.assertEqual(temporal_summary, "")
            self.assertFalse(activities_layer.temporalProperties().isActive())
            self.assertFalse(starts_layer.temporalProperties().isActive())
            self.assertFalse(points_layer.temporalProperties().isActive())
            self.assertFalse(atlas_layer.temporalProperties().isActive())

            atlas_feature = next(atlas_layer.getFeatures())
            self.assertEqual(atlas_feature["page_number"], 1)
            self.assertTrue(atlas_feature["page_name"])
            self.assertEqual(atlas_feature["profile_available"], 1)
            self.assertTrue(atlas_feature["profile_distance_label"])
            self.assertGreater(float(atlas_feature["extent_width_m"]), 0)
            self.assertGreater(float(atlas_feature["extent_height_m"]), 0)

            layer_order = self._layer_order()
            self.assertEqual(layer_order[-1], background_name)
            self.assertNotIn("qfit atlas pages", layer_order)
            self.assertEqual(layer_order[:-1], [
                "qfit activity points",
                "qfit activity starts",
                "qfit activities",
            ])

            self.layer_manager.ensure_background_layer(False, "Outdoor", "test-token")
            self.assertNotIn(background_name, self._layer_order())

    def test_full_sync_rewrite_removes_stale_activity_points(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = str(Path(temp_dir) / "qfit-prune-points.gpkg")
            writer = GeoPackageWriter(
                output_path,
                write_activity_points=True,
                point_stride=1,
                atlas_margin_percent=10,
                atlas_min_extent_degrees=0.01,
                atlas_target_aspect_ratio=1.5,
            )

            writer.write_activities(
                self._sample_activities(),
                sync_metadata={"provider": "strava", "is_full_sync": True},
            )
            _activities_layer, _starts_layer, points_layer, _atlas_layer = self.layer_manager.load_output_layers(output_path)
            initial_ids = sorted({feature["source_activity_id"] for feature in points_layer.getFeatures()})
            initial_point_count = points_layer.featureCount()

            writer.write_activities(
                self._sample_activities()[:1],
                sync_metadata={"provider": "strava", "is_full_sync": True},
            )
            activities_layer, _starts_layer, points_layer, _atlas_layer = self.layer_manager.load_output_layers(output_path)

            self.assertEqual(initial_ids, ["1001", "1002"])
            self.assertEqual(activities_layer.featureCount(), 1)
            self.assertLess(points_layer.featureCount(), initial_point_count)
            remaining_ids = sorted({feature["source_activity_id"] for feature in points_layer.getFeatures()})
            self.assertEqual(remaining_ids, ["1001"])

    def test_activity_publication_is_incremental_after_initial_import(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = str(Path(temp_dir) / "qfit-incremental.gpkg")
            writer = GeoPackageWriter(
                output_path,
                write_activity_points=True,
                point_stride=1,
                atlas_margin_percent=10,
                atlas_min_extent_degrees=0.01,
                atlas_target_aspect_ratio=1.5,
            )
            activities = self._sample_activities()

            initial = writer.write_activities(
                activities,
                sync_metadata={"provider": "strava"},
            )
            unchanged_fingerprints = self._derived_activity_fingerprints(
                output_path,
                "1001",
            )

            changed = dict(activities[1])
            changed["distance_m"] = 10250
            changed["total_elevation_gain_m"] = 92
            updated = writer.write_activities(
                [changed],
                sync_metadata={"provider": "strava"},
            )

            appended = dict(changed)
            appended.update(
                source_activity_id="1003",
                external_id="strava-1003",
                name="Evening Run",
                start_date="2026-03-22T17:30:00+00:00",
                start_date_local="2026-03-22T18:30:00+01:00",
            )
            inserted = writer.write_activities(
                [appended],
                sync_metadata={"provider": "strava"},
            )
            no_op = writer.write_activities(
                [appended],
                sync_metadata={"provider": "strava"},
            )

            self.assertEqual(initial["publication_mode"], "full_rebuild")
            self.assertEqual(updated["publication_mode"], "incremental")
            self.assertEqual(inserted["publication_mode"], "incremental")
            self.assertEqual(no_op["publication_mode"], "unchanged")
            self.assertEqual(inserted["track_count"], 3)
            self.assertEqual(inserted["atlas_count"], 3)
            self.assertEqual(
                self._derived_activity_fingerprints(output_path, "1001"),
                unchanged_fingerprints,
            )

            with sqlite3.connect(output_path) as connection:
                page_rows = connection.execute(
                    "SELECT source_activity_id, page_number FROM activity_atlas_pages "
                    "ORDER BY page_number"
                ).fetchall()
                summary = connection.execute(
                    "SELECT activity_count, total_distance_m "
                    "FROM atlas_document_summary"
                ).fetchone()
            self.assertEqual(page_rows, [("1001", 1), ("1002", 2), ("1003", 3)])
            self.assertEqual(summary[0], 3)
            self.assertAlmostEqual(summary[1], 45700)

            expected_path = str(Path(temp_dir) / "qfit-full-equivalent.gpkg")
            GeoPackageWriter(
                expected_path,
                write_activity_points=True,
                point_stride=1,
                atlas_margin_percent=10,
                atlas_min_extent_degrees=0.01,
                atlas_target_aspect_ratio=1.5,
            ).write_activities(
                [activities[0], changed, appended],
                sync_metadata={"provider": "strava"},
            )
            self.assertEqual(
                self._derived_database_snapshot(output_path),
                self._derived_database_snapshot(expected_path),
            )

            backdated = dict(appended)
            backdated.update(
                source_activity_id="0999",
                external_id="strava-0999",
                name="Older Run",
                start_date="2026-03-19T17:30:00+00:00",
                start_date_local="2026-03-19T18:30:00+01:00",
            )
            fallback = writer.write_activities(
                [backdated],
                sync_metadata={"provider": "strava"},
            )
            self.assertEqual(fallback["publication_mode"], "full_rebuild")
            self.assertIn("append-only", fallback["publication_fallback_reason"])

    def test_incremental_atlas_rename_matches_full_rebuild(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            incremental_path = str(Path(temp_dir) / "qfit-incremental-rename.gpkg")
            expected_path = str(Path(temp_dir) / "qfit-full-rename.gpkg")
            writer_kwargs = {
                "write_activity_points": True,
                "point_stride": 1,
                "atlas_margin_percent": 10,
                "atlas_min_extent_degrees": 0.01,
                "atlas_target_aspect_ratio": 1.5,
            }
            activities = self._sample_activities()
            renamed = dict(activities[1])
            renamed["name"] = "Renamed Lunch Run"

            incremental_writer = GeoPackageWriter(
                incremental_path,
                **writer_kwargs,
            )
            incremental_writer.write_activities(
                activities,
                sync_metadata={"provider": "strava"},
            )
            result = incremental_writer.write_activities(
                [renamed],
                sync_metadata={"provider": "strava"},
            )

            GeoPackageWriter(expected_path, **writer_kwargs).write_activities(
                [activities[0], renamed],
                sync_metadata={"provider": "strava"},
            )

            self.assertEqual(result["publication_mode"], "incremental")
            self.assertEqual(
                self._derived_database_snapshot(incremental_path),
                self._derived_database_snapshot(expected_path),
            )

    def test_failed_incremental_publication_rolls_back_and_retries_dirty_keys(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = str(Path(temp_dir) / "qfit-incremental-retry.gpkg")
            writer = GeoPackageWriter(
                output_path,
                write_activity_points=True,
                point_stride=1,
            )
            activities = self._sample_activities()
            writer.write_activities(
                activities,
                sync_metadata={"provider": "strava"},
            )
            visible_before = self._derived_database_snapshot(output_path)
            changed = dict(activities[1])
            changed["distance_m"] = 10999

            incremental = __import__(
                "qfit.activities.infrastructure.geopackage.gpkg_incremental_publication",
                fromlist=["_copy_feature"],
            )
            real_copy = incremental._copy_feature
            calls = 0

            def fail_after_first_copy(*args, **kwargs):
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise RuntimeError("synthetic incremental merge failure")
                return real_copy(*args, **kwargs)

            with patch.object(
                incremental,
                "_copy_feature",
                side_effect=fail_after_first_copy,
            ):
                with self.assertRaisesRegex(
                    RuntimeError,
                    "synthetic incremental merge failure",
                ):
                    writer.write_activities(
                        [changed],
                        sync_metadata={"provider": "strava"},
                    )

            self.assertEqual(
                self._derived_database_snapshot(output_path),
                visible_before,
            )

            retried = writer.write_activities(
                [changed],
                sync_metadata={"provider": "strava"},
            )
            self.assertEqual(retried["sync"].unchanged, 1)
            self.assertEqual(retried["publication_mode"], "incremental")
            with sqlite3.connect(output_path) as connection:
                distance = connection.execute(
                    "SELECT distance_m FROM activity_tracks "
                    "WHERE source = 'strava' AND source_activity_id = '1002'"
                ).fetchone()[0]
                dirty_count = connection.execute(
                    "SELECT COUNT(*) FROM activity_derived_dirty"
                ).fetchone()[0]
            self.assertAlmostEqual(distance, 10999)
            self.assertEqual(dirty_count, 0)

    def test_cancelled_incremental_publication_preserves_visible_layers(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = str(Path(temp_dir) / "qfit-incremental-cancel.gpkg")
            writer = GeoPackageWriter(
                output_path,
                write_activity_points=True,
                point_stride=1,
            )
            activities = self._sample_activities()
            writer.write_activities(
                activities,
                sync_metadata={"provider": "strava"},
            )
            visible_before = self._derived_database_snapshot(output_path)
            changed = dict(activities[1])
            changed["distance_m"] = 10888
            cancellation_checks = 0

            def cancelled():
                nonlocal cancellation_checks
                cancellation_checks += 1
                return cancellation_checks >= 6

            with self.assertRaises(InterruptedError):
                writer.write_activities(
                    [changed],
                    sync_metadata={"provider": "strava"},
                    cancelled=cancelled,
                )

            self.assertEqual(
                self._derived_database_snapshot(output_path),
                visible_before,
            )
            with sqlite3.connect(output_path) as connection:
                dirty_count = connection.execute(
                    "SELECT COUNT(*) FROM activity_derived_dirty"
                ).fetchone()[0]
            self.assertEqual(dirty_count, 1)

    def test_cancelled_small_fallback_rebuild_does_not_publish(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = str(Path(temp_dir) / "qfit-fallback-cancel.gpkg")
            writer = GeoPackageWriter(
                output_path,
                write_activity_points=True,
                point_stride=1,
            )
            activities = self._sample_activities()
            writer.write_activities(
                activities,
                sync_metadata={"provider": "strava"},
            )
            visible_before = self._derived_database_snapshot(output_path)
            backdated = dict(activities[0])
            backdated.update(
                source_activity_id="0999",
                external_id="strava-0999",
                name="Older Ride",
                start_date="2026-03-19T07:00:00+00:00",
                start_date_local="2026-03-19T08:00:00+01:00",
            )
            cancellation_checks = 0

            def cancelled():
                nonlocal cancellation_checks
                cancellation_checks += 1
                return cancellation_checks >= 3

            with self.assertRaises(InterruptedError):
                writer.write_activities(
                    [backdated],
                    sync_metadata={"provider": "strava"},
                    cancelled=cancelled,
                )

            self.assertEqual(
                self._derived_database_snapshot(output_path),
                visible_before,
            )

    def test_large_registry_incremental_update_never_hydrates_full_history(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = str(Path(temp_dir) / "qfit-large-incremental.gpkg")
            template = self._sample_activities()[0]
            activities = []
            for index in range(24):
                activity = dict(template)
                activity.update(
                    source_activity_id=f"large-{index:03d}",
                    external_id=f"strava-large-{index:03d}",
                    name=f"Scalability Ride {index:03d}",
                    start_date=f"2026-03-{index + 1:02d}T07:00:00+00:00",
                    start_date_local=f"2026-03-{index + 1:02d}T08:00:00+01:00",
                )
                activities.append(activity)

            writer = GeoPackageWriter(
                output_path,
                write_activity_points=True,
                point_stride=2,
            )
            writer.write_activities(
                activities,
                sync_metadata={"provider": "strava"},
            )
            changed = dict(activities[-1])
            changed["distance_m"] = 26001

            with patch(
                "qfit.activities.infrastructure.geopackage.activity_storage."
                "GeoPackageActivityStore.load_all_activity_records",
                side_effect=AssertionError("full history must not be hydrated"),
            ):
                result = writer.write_activities(
                    [changed],
                    sync_metadata={"provider": "strava"},
                )

            self.assertEqual(result["publication_mode"], "incremental")
            self.assertEqual(result["track_count"], 24)

    def test_changed_publication_settings_force_complete_rebuild(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = str(Path(temp_dir) / "qfit-publication-settings.gpkg")
            activities = self._sample_activities()
            first = GeoPackageWriter(
                output_path,
                write_activity_points=True,
                point_stride=1,
            ).write_activities(
                activities,
                sync_metadata={"provider": "strava"},
            )
            changed_settings = GeoPackageWriter(
                output_path,
                write_activity_points=True,
                point_stride=3,
            ).write_activities(
                activities,
                sync_metadata={"provider": "strava"},
            )

            self.assertEqual(first["publication_mode"], "full_rebuild")
            self.assertEqual(changed_settings["sync"].unchanged, 2)
            self.assertEqual(changed_settings["publication_mode"], "full_rebuild")
            self.assertIn(
                "settings changed",
                changed_settings["publication_fallback_reason"],
            )
            self.assertLess(
                changed_settings["point_count"],
                first["point_count"],
            )

    def _derived_activity_fingerprints(self, output_path, activity_id):
        queries = {
            "activity_tracks": "SELECT fid, hex(geom), summary_hash, details_json",
            "activity_starts": "SELECT fid, hex(geom), activity_fk, start_date",
            "activity_points": (
                "SELECT fid, hex(geom), activity_fk, point_index, altitude_m"
            ),
            "activity_atlas_pages": (
                "SELECT fid, hex(geom), page_number, page_sort_key, "
                "page_title, page_stats_summary, profile_point_count"
            ),
            "atlas_profile_samples": (
                "SELECT fid, page_number, page_sort_key, profile_point_index, "
                "distance_m, altitude_m"
            ),
        }
        with sqlite3.connect(output_path) as connection:
            return {
                table_name: connection.execute(
                    f'{select_sql} FROM "{table_name}" '
                    "WHERE source = 'strava' AND source_activity_id = ? ORDER BY fid",
                    (activity_id,),
                ).fetchall()
                for table_name, select_sql in queries.items()
            }

    def _derived_database_snapshot(self, output_path):
        tables = (
            "activity_tracks",
            "activity_starts",
            "activity_points",
            "activity_atlas_pages",
            "atlas_document_summary",
            "atlas_cover_highlights",
            "atlas_page_detail_items",
            "atlas_profile_samples",
            "atlas_toc_entries",
        )
        snapshots = {}
        with sqlite3.connect(output_path) as connection:
            for table_name in tables:
                columns = [
                    row[1]
                    for row in connection.execute(
                        f'PRAGMA table_info("{table_name}")'
                    )
                    if row[1] not in {
                        "fid",
                        "first_seen_at",
                        "last_synced_at",
                    }
                ]
                column_sql = ", ".join(f'"{column}"' for column in columns)
                rows = connection.execute(
                    f'SELECT {column_sql} FROM "{table_name}"'
                ).fetchall()
                snapshots[table_name] = sorted(rows, key=repr)
        return snapshots

    def test_rewrite_preserves_richer_activity_points_when_geometry_falls_back(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = str(Path(temp_dir) / "qfit-fallback-points.gpkg")
            writer = GeoPackageWriter(
                output_path,
                write_activity_points=True,
                point_stride=1,
                atlas_margin_percent=10,
                atlas_min_extent_degrees=0.01,
                atlas_target_aspect_ratio=1.5,
            )

            writer.write_activities(
                [self._summary_polyline_only_activity()],
                sync_metadata={"provider": "strava"},
            )
            _activities_layer, _starts_layer, points_layer, _atlas_layer = self.layer_manager.load_output_layers(output_path)
            initial_points = list(points_layer.getFeatures())

            writer.write_activities(
                [self._start_end_only_activity()],
                sync_metadata={"provider": "strava"},
            )
            _activities_layer, _starts_layer, points_layer, _atlas_layer = self.layer_manager.load_output_layers(output_path)
            refreshed_points = list(points_layer.getFeatures())

            self.assertGreaterEqual(len(initial_points), 3)
            self.assertEqual({feature["geometry_source"] for feature in initial_points}, {"summary_polyline"})
            self.assertEqual(points_layer.featureCount(), len(initial_points))
            self.assertEqual({feature["source_activity_id"] for feature in refreshed_points}, {"fallback-1001"})
            self.assertEqual({feature["geometry_source"] for feature in refreshed_points}, {"summary_polyline"})

            initial_coords = [feature.geometry().asPoint() for feature in initial_points]
            refreshed_coords = [feature.geometry().asPoint() for feature in refreshed_points]
            self.assertEqual(
                [(round(point.x(), 4), round(point.y(), 4)) for point in refreshed_coords],
                [(round(point.x(), 4), round(point.y(), 4)) for point in initial_coords],
            )

    def test_build_frequent_start_points_layer_rejects_invalid_layer(self):
        layer, clusters = build_frequent_start_points_layer(None)

        self.assertIsNone(layer)
        self.assertEqual(clusters, [])

    def test_build_frequent_start_points_layer_skips_empty_geometries(self):
        starts_layer = QgsVectorLayer(
            "Point?crs=EPSG:4326&field=source_activity_id:string",
            "qfit activity starts",
            "memory",
        )
        feature = QgsFeature(starts_layer.fields())
        feature["source_activity_id"] = "empty"
        starts_layer.dataProvider().addFeature(feature)
        starts_layer.updateExtents()

        layer, clusters = build_frequent_start_points_layer(starts_layer)

        self.assertIsNotNone(layer)
        self.assertEqual(layer.featureCount(), 0)
        self.assertEqual(clusters, [])

    def test_remove_stale_qfit_layers_keeps_memory_analysis_layer(self):
        memory_layer = QgsVectorLayer(
            "Point?crs=EPSG:4326",
            "qfit frequent starting points",
            "memory",
        )
        QgsProject.instance().addMapLayer(memory_layer)

        dock = QfitDockWidget(self.iface)
        try:
            self.assertIsNotNone(QgsProject.instance().mapLayer(memory_layer.id()))
        finally:
            dock.close()
            dock.deleteLater()
            QgsProject.instance().removeMapLayer(memory_layer.id())

    def test_apply_analysis_configuration_returns_empty_status_without_starts_layer(self):
        dock = QfitDockWidget(self.iface)
        try:
            dock.analysisModeComboBox.setCurrentText("Most frequent starting points")
            dock.starts_layer = None

            status = dock._apply_analysis_configuration()

            self.assertEqual(status, "")
            self.assertIsNone(dock.analysis_layer)
        finally:
            dock.close()
            dock.deleteLater()

    def test_apply_analysis_configuration_reports_no_matches_for_empty_starts_layer(self):
        dock = QfitDockWidget(self.iface)
        try:
            dock.analysisModeComboBox.setCurrentText("Most frequent starting points")
            dock.starts_layer = QgsVectorLayer(
                "Point?crs=EPSG:4326",
                "qfit activity starts",
                "memory",
            )

            status = dock._apply_analysis_configuration()

            self.assertEqual(status, "No frequent starting points matched the current filters")
            self.assertIsNone(dock.analysis_layer)
        finally:
            dock.close()
            dock.deleteLater()

    def test_run_analysis_clicked_updates_status_with_analysis_result(self):
        dock = QfitDockWidget(self.iface)
        try:
            with tempfile.TemporaryDirectory() as tmp:
                output_path = self._write_sample_gpkg(tmp)
                (
                    dock.activities_layer,
                    dock.starts_layer,
                    dock.points_layer,
                    dock.atlas_layer,
                ) = dock.layer_gateway.load_output_layers(output_path)

                dock.analysisModeComboBox.setCurrentText("Most frequent starting points")
                dock.visual_apply.build_request = MagicMock(return_value=object())
                dock.visual_apply.apply_request = MagicMock(
                    return_value=MagicMock(
                        status="Applied current filters",
                        background_error=None,
                        background_layer=None,
                    )
                )
                dock.visual_apply.should_update_background = MagicMock(return_value=False)
                dock._set_status = MagicMock()

                dock.on_run_analysis_clicked()

                dock._set_status.assert_called_once()
                status = dock._set_status.call_args.args[0]
                self.assertIn("Applied current filters", status)
                self.assertIn("Showing top 2 frequent starting-point clusters", status)
                self.assertIsNotNone(dock.analysis_layer)
        finally:
            dock.close()
            dock.deleteLater()

    def test_load_layers_replaces_existing_frequent_starting_points_analysis_layer(self):
        dock = QfitDockWidget(self.iface)
        try:
            with tempfile.TemporaryDirectory() as tmp:
                output_path = self._write_sample_gpkg(tmp)
                dock.outputPathLineEdit.setText(output_path)
                dock.analysisModeComboBox.setCurrentText("Most frequent starting points")

                dock.on_load_layers_clicked()
                first_analysis_layer = dock.analysis_layer
                self.assertIsNotNone(first_analysis_layer)
                first_analysis_layer_id = first_analysis_layer.id()

                dock.on_load_layers_clicked()

                analysis_layers = [
                    layer
                    for layer in QgsProject.instance().mapLayers().values()
                    if layer.name() == "qfit frequent starting points"
                ]
                self.assertEqual(len(analysis_layers), 1)
                self.assertIsNotNone(dock.analysis_layer)
                self.assertNotEqual(dock.analysis_layer.id(), first_analysis_layer_id)
        finally:
            dock.close()
            dock.deleteLater()

    def test_most_frequent_starting_points_analysis_creates_ranked_layer(self):
        dock = QfitDockWidget(self.iface)
        try:
            activities = [
                {
                    "source": "strava",
                    "source_activity_id": "start-a1",
                    "external_id": "start-a1",
                    "name": "Morning ride 1",
                    "activity_type": "Ride",
                    "sport_type": "Ride",
                    "start_date": "2026-03-20T07:00:00+00:00",
                    "start_date_local": "2026-03-20T08:00:00+01:00",
                    "timezone": "Europe/Zurich",
                    "distance_m": 12000,
                    "moving_time_s": 2400,
                    "elapsed_time_s": 2500,
                    "total_elevation_gain_m": 180,
                    "start_lat": 46.5200,
                    "start_lon": 6.6200,
                    "end_lat": 46.5300,
                    "end_lon": 6.6400,
                    "geometry_source": "stream",
                    "geometry_points": [(46.5200, 6.6200), (46.5300, 6.6400)],
                    "details_json": {},
                },
                {
                    "source": "strava",
                    "source_activity_id": "start-a2",
                    "external_id": "start-a2",
                    "name": "Morning ride 2",
                    "activity_type": "Ride",
                    "sport_type": "Ride",
                    "start_date": "2026-03-21T07:00:00+00:00",
                    "start_date_local": "2026-03-21T08:00:00+01:00",
                    "timezone": "Europe/Zurich",
                    "distance_m": 11800,
                    "moving_time_s": 2380,
                    "elapsed_time_s": 2450,
                    "total_elevation_gain_m": 170,
                    "start_lat": 46.5201,
                    "start_lon": 6.6202,
                    "end_lat": 46.5310,
                    "end_lon": 6.6410,
                    "geometry_source": "stream",
                    "geometry_points": [(46.5201, 6.6202), (46.5310, 6.6410)],
                    "details_json": {},
                },
                {
                    "source": "strava",
                    "source_activity_id": "start-a3",
                    "external_id": "start-a3",
                    "name": "Morning ride 3",
                    "activity_type": "Ride",
                    "sport_type": "Ride",
                    "start_date": "2026-03-22T07:00:00+00:00",
                    "start_date_local": "2026-03-22T08:00:00+01:00",
                    "timezone": "Europe/Zurich",
                    "distance_m": 12200,
                    "moving_time_s": 2420,
                    "elapsed_time_s": 2480,
                    "total_elevation_gain_m": 175,
                    "start_lat": 46.5202,
                    "start_lon": 6.6201,
                    "end_lat": 46.5320,
                    "end_lon": 6.6420,
                    "geometry_source": "stream",
                    "geometry_points": [(46.5202, 6.6201), (46.5320, 6.6420)],
                    "details_json": {},
                },
                {
                    "source": "strava",
                    "source_activity_id": "start-b1",
                    "external_id": "start-b1",
                    "name": "Evening run",
                    "activity_type": "Run",
                    "sport_type": "Run",
                    "start_date": "2026-03-23T18:00:00+00:00",
                    "start_date_local": "2026-03-23T19:00:00+01:00",
                    "timezone": "Europe/Zurich",
                    "distance_m": 8000,
                    "moving_time_s": 2200,
                    "elapsed_time_s": 2260,
                    "total_elevation_gain_m": 60,
                    "start_lat": 46.5400,
                    "start_lon": 6.7000,
                    "end_lat": 46.5500,
                    "end_lon": 6.7100,
                    "geometry_source": "stream",
                    "geometry_points": [(46.5400, 6.7000), (46.5500, 6.7100)],
                    "details_json": {},
                },
            ]

            with tempfile.TemporaryDirectory() as tmp:
                output_path = str(Path(tmp) / "qfit-analysis-test.gpkg")
                GeoPackageWriter(
                    output_path,
                    write_activity_points=True,
                    point_stride=1,
                    atlas_margin_percent=10,
                    atlas_min_extent_degrees=0.01,
                    atlas_target_aspect_ratio=1.5,
                ).write_activities(activities, sync_metadata={"provider": "strava"})

                (
                    dock.activities_layer,
                    dock.starts_layer,
                    dock.points_layer,
                    dock.atlas_layer,
                ) = dock.layer_gateway.load_output_layers(output_path)

                dock.analysisModeComboBox.setCurrentText("Most frequent starting points")
                status = dock._apply_analysis_configuration()

                self.assertIn("frequent starting-point clusters", status)
                self.assertIsNotNone(dock.analysis_layer)
                self.assertEqual(dock.analysis_layer.name(), "qfit frequent starting points")
                features = list(dock.analysis_layer.getFeatures())
                counts = sorted((feature["activity_count"] for feature in features), reverse=True)
                sizes = sorted((float(feature["marker_size"]) for feature in features), reverse=True)
                self.assertEqual(counts, [3, 1])
                self.assertGreater(sizes[0], sizes[-1])
        finally:
            dock.close()
            dock.deleteLater()

    def test_heatmap_analysis_creates_renderable_density_layer(self):
        dock = QfitDockWidget(self.iface)
        try:
            with tempfile.TemporaryDirectory() as tmp:
                dock.cache.base_path = Path(tmp) / "cache"
                dock.dateFromEdit.setDate(QDate(2026, 1, 1))
                dock.dateToEdit.setDate(QDate(2026, 12, 31))
                output_path = self._write_sample_gpkg(tmp)
                (
                    dock.activities_layer,
                    dock.starts_layer,
                    dock.points_layer,
                    dock.atlas_layer,
                ) = dock.layer_gateway.load_output_layers(output_path)

                dock.analysisModeComboBox.setCurrentText("Heatmap")
                status = dock._apply_analysis_configuration()

                self.assertIn("Building static red heatmap", status)
                self._wait_for_heatmap(dock)
                self.assertIsNotNone(dock.analysis_layer)
                self.assertEqual(dock.analysis_layer.name(), "qfit activity heatmap")
                self.assertGreater(dock.analysis_layer.customProperty("qfit/heatmap/activity_count"), 0)
                self.assertEqual(dock.analysis_layer.providerType(), "gdal")
                image = self._render_layers_to_image(
                    [dock.analysis_layer],
                    dock.analysis_layer.extent(),
                )
                artifact_path = Path(tmp) / "heatmap-analysis.png"
                self.assertTrue(image.save(str(artifact_path)))
                non_white_pixels, strong_pixels = self._count_heatmap_pixels(image)
                self.assertGreater(non_white_pixels, 100)
                self.assertGreater(strong_pixels, 100)
                previous = dock.analysis_layer
                previous_key = previous.customProperty("qfit/heatmap/cache_key")
                dock._apply_analysis_configuration()
                self.assertIs(dock.analysis_layer, previous)
                self._wait_for_heatmap(dock)
                self.assertIsNot(dock.analysis_layer, previous)
                self.assertEqual(dock.analysis_layer.customProperty("qfit/heatmap/cache_key"),
                                 previous_key)
        finally:
            dock.close()
            dock.deleteLater()

    def test_heatmap_analysis_falls_back_to_activity_lines_without_points_layer(self):
        dock = QfitDockWidget(self.iface)
        try:
            with tempfile.TemporaryDirectory() as tmp:
                dock.cache.base_path = Path(tmp) / "cache"
                dock.dateFromEdit.setDate(QDate(2026, 1, 1))
                dock.dateToEdit.setDate(QDate(2026, 12, 31))
                output_path = self._write_sample_gpkg(tmp)
                (
                    dock.activities_layer,
                    dock.starts_layer,
                    _points_layer,
                    dock.atlas_layer,
                ) = dock.layer_gateway.load_output_layers(output_path)
                dock.points_layer = None

                dock.analysisModeComboBox.setCurrentText("Heatmap")
                status = dock._apply_analysis_configuration()

                self.assertIn("Building static red heatmap", status)
                self._wait_for_heatmap(dock)
                self.assertIsNotNone(dock.analysis_layer)
                self.assertGreater(dock.analysis_layer.customProperty("qfit/heatmap/activity_count"), 0)
                self.assertEqual(dock.analysis_layer.providerType(), "gdal")
                image = self._render_layers_to_image(
                    [dock.analysis_layer],
                    dock.analysis_layer.extent(),
                )
                artifact_path = Path(tmp) / "heatmap-analysis-lines-fallback.png"
                self.assertTrue(image.save(str(artifact_path)))
                non_white_pixels, strong_pixels = self._count_heatmap_pixels(image)
                self.assertGreater(non_white_pixels, 100)
                self.assertGreater(strong_pixels, 100)
        finally:
            dock.close()
            dock.deleteLater()

    def test_heatmap_real_task_retains_previous_on_cancel_stale_and_failure(self):
        import threading
        from qfit.analysis.domain.route_density import HeatmapCancelled
        from qfit.analysis.infrastructure.route_heatmap_raster import build_route_heatmap
        dock = QfitDockWidget(self.iface)
        try:
            with tempfile.TemporaryDirectory() as tmp:
                dock.cache.base_path = Path(tmp) / "cache"
                dock.dateFromEdit.setDate(QDate(2026, 1, 1))
                dock.dateToEdit.setDate(QDate(2026, 12, 31))
                output = self._write_sample_gpkg(tmp)
                dock.activities_layer, dock.starts_layer, dock.points_layer, dock.atlas_layer = dock.layer_gateway.load_output_layers(output)
                dock.analysisModeComboBox.setCurrentText("Heatmap")
                dock._apply_analysis_configuration()
                self._wait_for_heatmap(dock)
                previous = dock.analysis_layer
                self.assertIsNotNone(previous)
                for outcome in ("cancel", "stale", "failed", "missing"):
                    with self.subTest(outcome=outcome):
                        started, release = threading.Event(), threading.Event()
                        def controlled(request, cancelled, progress):
                            started.set()
                            if not release.wait(5):
                                raise RuntimeError("Test did not release worker")
                            if cancelled():
                                raise HeatmapCancelled()
                            if outcome == "failed":
                                raise ValueError("Controlled write failure")
                            if outcome == "missing":
                                return None
                            return build_route_heatmap(request, cancelled, progress)
                        with patch("qfit.analysis.infrastructure.route_heatmap_task.build_route_heatmap", side_effect=controlled), patch.object(dock, "_show_error") as error:
                            dock._apply_analysis_configuration()
                            self.assertTrue(started.wait(3))
                            self.assertIs(dock.analysis_layer, previous)
                            if outcome == "cancel":
                                self.assertIn("Cancelling", dock._apply_analysis_configuration())
                            elif outcome == "stale":
                                dock.activitySearchLineEdit.setText("Changed selection")
                            release.set()
                            self._wait_for_heatmap(dock)
                            if outcome == "missing":
                                self.assertIsNone(dock.analysis_layer)
                            else:
                                self.assertIs(dock.analysis_layer, previous)
                            if outcome == "failed":
                                error.assert_called_once_with("Heatmap could not be built", "Controlled write failure")
                        dock.activitySearchLineEdit.clear()
        finally:
            dock.cancel_background_tasks()
            dock.close()
            dock.deleteLater()

    def test_heatmap_mode_changes_keep_worker_reserved_until_completion(self):
        import threading
        from qfit.analysis.domain.route_density import HeatmapCancelled
        dock = QfitDockWidget(self.iface)
        release = threading.Event()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                dock.cache.base_path = Path(tmp) / "cache"
                dock.dateFromEdit.setDate(QDate(2026, 1, 1))
                dock.dateToEdit.setDate(QDate(2026, 12, 31))
                output = self._write_sample_gpkg(tmp)
                dock.activities_layer, dock.starts_layer, dock.points_layer, dock.atlas_layer = dock.layer_gateway.load_output_layers(output)
                dock.analysisModeComboBox.setCurrentText("Heatmap")
                started = threading.Event()
                def controlled(request, cancelled, progress):
                    started.set()
                    if not release.wait(5):
                        raise RuntimeError("Test did not release worker")
                    if cancelled():
                        raise HeatmapCancelled()
                    return None
                with patch("qfit.analysis.infrastructure.route_heatmap_task.build_route_heatmap", side_effect=controlled) as build:
                    dock._apply_analysis_configuration()
                    self.assertTrue(started.wait(3))
                    worker = dock._heatmap_task
                    dock.analysisModeComboBox.setCurrentText("Most frequent starting points")
                    dock._apply_analysis_configuration()
                    self.assertIs(dock._heatmap_task, worker)
                    self.assertTrue(worker.isCanceled())
                    other_layer = dock.analysis_layer
                    self.assertIsNotNone(other_layer)
                    dock.analysisModeComboBox.setCurrentText("Heatmap")
                    self.assertIn("Cancelling", dock._apply_analysis_configuration())
                    self.assertIs(dock._heatmap_task, worker)
                    self.assertEqual(build.call_count, 1)
                    self.assertTrue(dock._local_first_dock_composition.analysis_content.run_analysis_button.isEnabled())
                    release.set()
                    self._wait_for_heatmap(dock)
                    self.assertIs(dock.analysis_layer, other_layer)
                    dock._apply_analysis_configuration()
                    self._wait_for_heatmap(dock)
                    self.assertEqual(build.call_count, 2)
        finally:
            release.set()
            dock.cancel_background_tasks()
            dock.close()
            dock.deleteLater()

    def test_offscreen_profile_chart_export_contains_rendered_curve(self):
        """Bound profile exports should differ visibly from the same chart when cleared."""
        script = textwrap.dedent(
            """
            import os
            import sys
            import tempfile
            from pathlib import Path

            os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

            from qgis.core import QgsApplication, QgsLayoutExporter, QgsProject, QgsRectangle
            from qgis.PyQt.QtGui import QImage
            from pypdf import PdfReader

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
            from qfit.activities.infrastructure.geopackage.gpkg_writer import GeoPackageWriter
            from qfit.visualization.infrastructure.qgis_layer_gateway import (
                QgisLayerGateway as LayerManager,
            )

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

            def pdf_content_stream_size(pdf_path):
                page = PdfReader(pdf_path).pages[0]
                contents = page.get_contents()
                if contents is None:
                    return 0
                if isinstance(contents, list):
                    return sum(len(content.get_data()) for content in contents)
                return len(contents.get_data())

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
                        pdf_settings = QgsLayoutExporter.PdfExportSettings()
                        pdf_settings.dpi = 150
                        pdf_settings.rasterizeWholeImage = False
                        pdf_settings.forceVectorOutput = True

                        bound_path = str(Path(tmp) / "profile-bound.png")
                        blank_path = str(Path(tmp) / "profile-blank.png")
                        bound_pdf_path = str(Path(tmp) / "profile-bound.pdf")
                        blank_pdf_path = str(Path(tmp) / "profile-blank.pdf")
                        if exporter.exportToImage(bound_path, image_settings) != QgsLayoutExporter.ExportResult.Success:
                            raise RuntimeError("Bound profile image export failed")
                        if exporter.exportToPdf(bound_pdf_path, pdf_settings) != QgsLayoutExporter.ExportResult.Success:
                            raise RuntimeError("Bound profile PDF export failed")
                        profile_adapter.clear_profile()
                        if exporter.exportToImage(blank_path, image_settings) != QgsLayoutExporter.ExportResult.Success:
                            raise RuntimeError("Blank profile image export failed")
                        if exporter.exportToPdf(blank_pdf_path, pdf_settings) != QgsLayoutExporter.ExportResult.Success:
                            raise RuntimeError("Blank profile PDF export failed")

                        print(
                            count_changed_pixels(bound_path, blank_path),
                            pdf_content_stream_size(bound_pdf_path),
                            pdf_content_stream_size(blank_pdf_path),
                            flush=True,
                        )
                        os._exit(0)
                    finally:
                        atlas.endRender()
                        QgsProject.instance().clear()
            """
        )

        import qgis as _qgis_mod
        _qgis_python_path = os.path.dirname(list(_qgis_mod.__path__)[0])
        _qfit_parent_path = str(REPO_ROOT.parent)
        _pythonpath_parts = [
            _qfit_parent_path,
            _qgis_python_path,
            os.environ.get("PYTHONPATH", ""),
        ]
        _pythonpath_parts = [p for p in _pythonpath_parts if p]

        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
            env={
                **os.environ,
                "QT_QPA_PLATFORM": "offscreen",
                "PYTHONPATH": os.pathsep.join(_pythonpath_parts),
            },
            timeout=180,
        )

        self.assertEqual(
            result.returncode,
            0,
            f"Profile smoke subprocess failed with code {result.returncode}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}",
        )
        changed_pixels, bound_pdf_content_bytes, blank_pdf_content_bytes = [
            int(value) for value in result.stdout.strip().splitlines()[-1].split()
        ]
        self.assertGreater(
            changed_pixels,
            80,
            f"Expected rendered profile content in exported chart, but only {changed_pixels} profile-chart pixels changed",
        )
        self.assertGreater(
            bound_pdf_content_bytes,
            blank_pdf_content_bytes + 1000,
            "Expected exported profile PDF content stream to include the rendered chart",
        )

    def _wait_for_heatmap(self, dock):
        deadline = time.monotonic() + 30
        while dock._heatmap_task is not None and time.monotonic() < deadline:
            QApplication.processEvents()
            time.sleep(0.01)
        self.assertIsNone(dock._heatmap_task, "Background heatmap did not finish")

    def _write_sample_gpkg(self, temp_dir):
        return self._write_sample_gpkg_with_options(
            temp_dir,
            filename="qfit-heatmap-test.gpkg",
            write_activity_points=True,
            point_stride=2,
        )

    def test_name_refresh_preserves_real_gpkg_geometries_and_samples(self):
        import sqlite3
        from qfit.sync_repository import SyncRepository
        from qfit.activities.application.activity_name_refresh_task import ActivityNameRefreshTask

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = self._write_sample_gpkg_with_options(
                temp_dir, filename="name-refresh.gpkg", write_activity_points=True, point_stride=2,
            )
            repo = SyncRepository(output_path)
            activity = repo.load_all_activity_records()[0]
            def snapshot(table):
                with sqlite3.connect(output_path) as connection:
                    columns = [row[1] for row in connection.execute(f'PRAGMA table_info("{table}")')]
                    unchanged = [column for column in columns if column not in {
                        "name", "page_name", "page_title", "page_toc_label", "toc_entry_label", "page_sort_key"}]
                    selection = ",".join(f'"{column}"' for column in unchanged)
                    return connection.execute(f'SELECT {selection} FROM "{table}" ORDER BY rowid').fetchall()
            tables = ("activity_tracks", "activity_starts", "activity_points", "activity_atlas_pages",
                      "atlas_profile_samples", "atlas_toc_entries", "atlas_page_detail_items", "sync_state")
            before = {table: snapshot(table) for table in tables}
            result = repo.refresh_activity_names({activity["source_activity_id"]: "Historical renamed ride"})
            self.assertEqual(result["updated"], 1)
            self.assertEqual(before, {table: snapshot(table) for table in tables})
            with sqlite3.connect(output_path) as connection:
                name = connection.execute(
                    "SELECT name FROM activity_tracks WHERE source = ? AND source_activity_id = ?",
                    (activity["source"], activity["source_activity_id"]),
                ).fetchone()[0]
            self.assertEqual(name, "Historical renamed ride")
            from qgis.core import QgsTask
            self.assertTrue(issubclass(ActivityNameRefreshTask, QgsTask))

    def _write_sample_gpkg_without_points(self, temp_dir):
        return self._write_sample_gpkg_with_options(
            temp_dir,
            filename="qfit-heatmap-no-points.gpkg",
            write_activity_points=False,
            point_stride=2,
        )

    def _write_sample_gpkg_without_starts(self, temp_dir):
        output_path = str(Path(temp_dir) / "qfit-heatmap-no-starts.gpkg")
        writer = GeoPackageWriter(
            output_path,
            write_activity_points=True,
            point_stride=2,
            atlas_margin_percent=10,
            atlas_min_extent_degrees=0.01,
            atlas_target_aspect_ratio=1.5,
        )
        writer.write_activities(
            self._sample_activities_without_start_coordinates(),
            sync_metadata={"provider": "strava"},
        )
        return output_path

    def _write_sample_gpkg_with_options(
        self,
        temp_dir,
        *,
        filename,
        write_activity_points,
        point_stride,
    ):
        output_path = str(Path(temp_dir) / filename)
        GeoPackageWriter(
            output_path,
            write_activity_points=write_activity_points,
            point_stride=point_stride,
            atlas_margin_percent=10,
            atlas_min_extent_degrees=0.01,
            atlas_target_aspect_ratio=1.5,
        ).write_activities(self._sample_activities(), sync_metadata={"provider": "strava"})
        return output_path

    def _summary_polyline_only_activity(self):
        return {
            "source": "strava",
            "source_activity_id": "fallback-1001",
            "external_id": "strava-fallback-1001",
            "name": "Fallback Polyline Ride",
            "activity_type": "Ride",
            "sport_type": "Ride",
            "start_date": "2026-03-22T08:00:00+00:00",
            "start_date_local": "2026-03-22T09:00:00+01:00",
            "timezone": "Europe/Zurich",
            "distance_m": 12000,
            "moving_time_s": 3600,
            "elapsed_time_s": 3660,
            "total_elevation_gain_m": 250,
            "start_lat": 38.5,
            "start_lon": -120.2,
            "end_lat": 43.252,
            "end_lon": -126.453,
            "summary_polyline": "_p~iF~ps|U_ulLnnqC_mqNvxq`@",
            "geometry_source": "summary_polyline",
            "geometry_points": [],
            "details_json": {},
        }

    def _sample_activities_without_start_coordinates(self):
        activities = []
        for activity in self._sample_activities():
            updated = dict(activity)
            updated["start_lat"] = None
            updated["start_lon"] = None
            activities.append(updated)
        return activities

    def _start_end_only_activity(self):
        return {
            "source": "strava",
            "source_activity_id": "fallback-1001",
            "external_id": "strava-fallback-1001",
            "name": "Fallback Start End Ride",
            "activity_type": "Ride",
            "sport_type": "Ride",
            "start_date": "2026-03-22T08:00:00+00:00",
            "start_date_local": "2026-03-22T09:00:00+01:00",
            "timezone": "Europe/Zurich",
            "distance_m": 5000,
            "moving_time_s": 1500,
            "elapsed_time_s": 1560,
            "total_elevation_gain_m": 40,
            "start_lat": 46.5100,
            "start_lon": 6.6000,
            "end_lat": 46.5250,
            "end_lon": 6.6300,
            "summary_polyline": None,
            "geometry_source": "start_end",
            "geometry_points": [],
            "details_json": {},
        }

    def _render_layers_to_image(self, layers, extent, width=800, height=800):
        settings = QgsMapSettings()
        settings.setLayers(layers)
        settings.setOutputSize(
            QImage(
                width,
                height,
                qt_class_enum_value(QImage, "Format", "Format_ARGB32"),
            ).size()
        )
        settings.setBackgroundColor(qt_enum_value(Qt, "GlobalColor", "white"))

        destination_crs = QgsProject.instance().crs()
        if destination_crs.isValid():
            settings.setDestinationCrs(destination_crs)
            source_layer = next((layer for layer in layers if layer is not None and layer.isValid()), None)
            source_crs = source_layer.crs() if source_layer is not None else None
            if source_crs is not None and source_crs.isValid() and source_crs != destination_crs:
                transform = QgsCoordinateTransform(source_crs, destination_crs, QgsProject.instance())
                extent = transform.transformBoundingBox(extent)
        settings.setExtent(extent)

        job = QgsMapRendererSequentialJob(settings)
        job.start()
        job.waitForFinished()
        return job.renderedImage()

    def _count_heatmap_pixels(self, image):
        non_white_pixels = 0
        strong_pixels = 0
        for y in range(image.height()):
            for x in range(image.width()):
                color = image.pixelColor(x, y)
                delta = (255 - color.red()) + (255 - color.green()) + (255 - color.blue())
                if delta > 0:
                    non_white_pixels += 1
                if delta > 120:
                    strong_pixels += 1
        return non_white_pixels, strong_pixels

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
