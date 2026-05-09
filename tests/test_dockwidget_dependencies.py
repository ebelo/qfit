import importlib.util
import os
import sys
import unittest
from types import ModuleType
from typing import get_type_hints
from unittest.mock import MagicMock, call, patch, sentinel

from tests import _path  # noqa: F401

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from qfit.ui.dockwidget_dependencies import (
    DockWidgetDependencies,
    build_dockwidget_dependencies,
    _build_cache,
    _build_project_hygiene_service,
)
from qfit.visualization.application.layer_gateway import LayerGateway
from qfit.visualization.application.project_hygiene_port import ProjectHygienePort
from qfit.ui.dock_startup_coordinator import DockStartupCoordinator, DockStartupResult


class _FakeIface:
    def mapCanvas(self):
        return None

    def mainWindow(self):
        return None


class DockWidgetDependenciesTests(unittest.TestCase):
    def test_dependency_annotations_use_explicit_ports(self):
        hints = get_type_hints(DockWidgetDependencies)

        self.assertIs(hints["layer_gateway"], LayerGateway)
        self.assertIs(hints["project_hygiene_service"], ProjectHygienePort)

    def test_build_dockwidget_dependencies_wires_shared_gateway_and_sync_controller(self):
        iface = _FakeIface()
        layer_gateway = MagicMock(spec=LayerGateway)
        project_hygiene_service = MagicMock(spec=ProjectHygienePort)

        with (
            patch("qfit.ui.dockwidget_dependencies.SettingsService", return_value=sentinel.settings),
            patch("qfit.ui.dockwidget_dependencies.SyncController", return_value=sentinel.sync_controller),
            patch(
                "qfit.ui.dockwidget_dependencies.build_analysis_workflow",
                return_value=sentinel.analysis_workflow,
            ),
            patch(
                "qfit.ui.dockwidget_dependencies.AtlasExportController",
                return_value=sentinel.atlas_export_controller,
            ),
            patch(
                "qfit.ui.dockwidget_dependencies.AtlasExportUseCase",
                return_value=sentinel.atlas_export_use_case,
            ) as atlas_export_use_case,
            patch(
                "qfit.ui.dockwidget_dependencies._build_layer_gateway",
                return_value=layer_gateway,
            ),
            patch(
                "qfit.ui.dockwidget_dependencies.BackgroundMapController",
                return_value=sentinel.background_controller,
            ) as background_controller,
            patch(
                "qfit.ui.dockwidget_dependencies._build_project_hygiene_service",
                return_value=project_hygiene_service,
            ),
            patch(
                "qfit.ui.dockwidget_dependencies.StoreActivitiesWorkflow",
                return_value=sentinel.store_workflow,
            ) as store_workflow,
            patch(
                "qfit.ui.dockwidget_dependencies.LoadDatasetWorkflow",
                return_value=sentinel.dataset_load_workflow,
            ) as dataset_load_workflow,
            patch(
                "qfit.ui.dockwidget_dependencies.ClearDatabaseWorkflow",
                return_value=sentinel.clear_database_workflow,
            ) as clear_database_workflow,
            patch(
                "qfit.ui.dockwidget_dependencies.LoadWorkflowService",
                return_value=sentinel.load_workflow,
            ) as load_workflow,
            patch(
                "qfit.ui.dockwidget_dependencies.VisualApplyService",
                return_value=sentinel.visual_apply,
            ) as visual_apply,
            patch(
                "qfit.ui.dockwidget_dependencies.AtlasExportService",
                return_value=sentinel.atlas_export_service,
            ) as atlas_export_service,
            patch(
                "qfit.ui.dockwidget_dependencies.FetchResultService",
                return_value=sentinel.fetch_result_service,
            ) as fetch_result_service,
            patch(
                "qfit.ui.dockwidget_dependencies.ActivityPreviewService",
                return_value=sentinel.activity_preview_service,
            ) as activity_preview_service,
            patch(
                "qfit.ui.dockwidget_dependencies.DockActivityWorkflowCoordinator",
                return_value=sentinel.activity_workflow,
            ) as activity_workflow,
            patch(
                "qfit.ui.dockwidget_dependencies.DockAtlasWorkflowCoordinator",
                return_value=sentinel.atlas_workflow,
            ) as atlas_workflow,
            patch("qfit.ui.dockwidget_dependencies._build_cache", return_value=sentinel.cache),
        ):
            dependencies = build_dockwidget_dependencies(iface)

        self.assertIs(dependencies.settings, sentinel.settings)
        self.assertIs(dependencies.sync_controller, sentinel.sync_controller)
        self.assertIs(dependencies.analysis_workflow, sentinel.analysis_workflow)
        self.assertIs(dependencies.atlas_export_controller, sentinel.atlas_export_controller)
        self.assertIs(dependencies.atlas_export_use_case, sentinel.atlas_export_use_case)
        self.assertIs(dependencies.layer_gateway, layer_gateway)
        self.assertIs(dependencies.background_controller, sentinel.background_controller)
        self.assertIs(dependencies.project_hygiene_service, project_hygiene_service)
        self.assertIs(dependencies.store_workflow, sentinel.store_workflow)
        self.assertIs(dependencies.dataset_load_workflow, sentinel.dataset_load_workflow)
        self.assertIs(dependencies.clear_database_workflow, sentinel.clear_database_workflow)
        self.assertIs(dependencies.load_workflow, sentinel.load_workflow)
        self.assertIs(dependencies.visual_apply, sentinel.visual_apply)
        self.assertIs(dependencies.atlas_export_service, sentinel.atlas_export_service)
        self.assertIs(dependencies.activity_workflow, sentinel.activity_workflow)
        self.assertIs(dependencies.atlas_workflow, sentinel.atlas_workflow)
        self.assertIs(dependencies.cache, sentinel.cache)

        background_controller.assert_called_once_with(layer_gateway)
        store_workflow.assert_called_once_with()
        dataset_load_workflow.assert_called_once_with(layer_gateway)
        clear_database_workflow.assert_called_once_with(layer_gateway)
        load_workflow.assert_called_once_with(
            layer_gateway,
            store_workflow=sentinel.store_workflow,
            dataset_load_workflow=sentinel.dataset_load_workflow,
            clear_database_workflow=sentinel.clear_database_workflow,
        )
        visual_apply.assert_called_once_with(layer_gateway)
        atlas_export_service.assert_called_once_with(layer_gateway)
        atlas_export_use_case.assert_called_once_with(
            sentinel.atlas_export_controller,
            sentinel.atlas_export_service,
        )
        fetch_result_service.assert_called_once_with(sentinel.sync_controller)
        activity_preview_service.assert_called_once_with()
        activity_workflow.assert_called_once_with(
            sync_controller=sentinel.sync_controller,
            fetch_result_service=sentinel.fetch_result_service,
            activity_preview_service=sentinel.activity_preview_service,
        )
        atlas_workflow.assert_called_once_with(
            atlas_export_use_case=sentinel.atlas_export_use_case,
        )

    def test_build_cache_prefers_legacy_cache_path_when_current_path_is_missing(self):
        with (
            patch(
                "qfit.ui.dockwidget_dependencies._writable_app_data_location",
                return_value="/tmp/appdata",
            ),
            patch(
                "qfit.ui.dockwidget_dependencies.os.path.exists",
                side_effect=lambda path: path == "/tmp/appdata/QFIT/cache",
            ),
            patch("qfit.ui.dockwidget_dependencies.QfitCache", return_value=sentinel.cache) as cache_class,
        ):
            cache = _build_cache()

        self.assertIs(cache, sentinel.cache)
        cache_class.assert_called_once_with("/tmp/appdata/QFIT/cache")

    def test_build_cache_falls_back_to_home_dot_qfit_when_appdata_is_blank(self):
        with (
            patch("qfit.ui.dockwidget_dependencies._writable_app_data_location", return_value=""),
            patch("qfit.ui.dockwidget_dependencies.os.path.expanduser", return_value="/home/tester"),
            patch("qfit.ui.dockwidget_dependencies.os.path.exists", return_value=False),
            patch("qfit.ui.dockwidget_dependencies.QfitCache", return_value=sentinel.cache) as cache_class,
        ):
            cache = _build_cache()

        self.assertIs(cache, sentinel.cache)
        cache_class.assert_called_once_with("/home/tester/.qfit/qfit/cache")

    def test_build_project_hygiene_service_instantiates_service(self):
        fake_module = ModuleType("qfit.visualization.infrastructure.project_hygiene_service")
        fake_service_class = MagicMock(return_value=sentinel.project_hygiene_service)
        fake_module.ProjectHygieneService = fake_service_class

        with patch.dict(
            sys.modules,
            {"qfit.visualization.infrastructure.project_hygiene_service": fake_module},
        ):
            service = _build_project_hygiene_service()

        self.assertIs(service, sentinel.project_hygiene_service)
        fake_service_class.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()


class _VisibilityTarget:
    def __init__(self):
        self.visible = None

    def setVisible(self, value):
        self.visible = value




class _FakeItem:
    def __init__(self, widget=None, layout=None, spacer=None):
        self._widget = widget
        self._layout = layout
        self._spacer = spacer

    def widget(self):
        return self._widget

    def layout(self):
        return self._layout

    def spacerItem(self):
        return self._spacer


class _FakeLayoutContainer:
    def __init__(self, items=None, spacing=6):
        self._items = list(items or [])
        self._spacing = spacing
        self.added_widgets = []
        self.inserted_widgets = []
        self.removed_widgets = []

    def spacing(self):
        return self._spacing

    def count(self):
        return len(self._items)

    def takeAt(self, _index):
        return self._items.pop(0)

    def addWidget(self, widget):
        self.added_widgets.append(widget)

    def addLayout(self, layout):
        self.added_widgets.append(layout)

    def addItem(self, item):
        self.added_widgets.append(item)

    def insertWidget(self, index, widget):
        self.inserted_widgets.append((index, widget))

    def removeWidget(self, widget):
        self.removed_widgets.append(widget)


class _FakeWidget:
    def __init__(self, parent=None):
        self.parent_obj = parent
        self.visible = None
        self.title = None
        self.checkable = None
        self.object_name = None
        self.tooltip = None

    def setParent(self, parent):
        self.parent_obj = parent

    def parent(self):
        return self.parent_obj

    def setVisible(self, value):
        self.visible = value

    def setObjectName(self, name):
        self.object_name = name

    def hide(self):
        self.visible = False

    def click(self):
        pass

    def setTitle(self, title):
        self.title = title

    def setCheckable(self, value):
        self.checkable = value

    def setToolTip(self, text):
        self.tooltip = text


class _FakeLabel(_FakeWidget):
    def __init__(self):
        super().__init__()
        self.text = None

    def setText(self, text):
        self.text = text


class _FakeSpinBox(_FakeWidget):
    def __init__(self):
        super().__init__()
        self.suffix = None

    def setSuffix(self, suffix):
        self.suffix = suffix


class _FakeGroupBox:
    def __init__(self):
        self.parent_obj = None
        self.visible = None
        self.title = None
        self.checkable = None
        self.tooltip = None

    def setParent(self, parent):
        self.parent_obj = parent

    def parent(self):
        return self.parent_obj

    def setVisible(self, value):
        self.visible = value

    def hide(self):
        self.visible = False

    def setTitle(self, title):
        self.title = title

    def setCheckable(self, value):
        self.checkable = value

    def setToolTip(self, text):
        self.tooltip = text


class LocalFirstBackingControlsTests(unittest.TestCase):
    def _make_section_dock(self):
        dock = type("Dock", (), {})()
        dock.activitiesGroupLayout = _FakeLayoutContainer([_FakeItem(widget=object())])
        dock.styleGroupLayout = _FakeLayoutContainer([_FakeItem(widget=object())])
        dock.analysisWorkflowLayout = _FakeLayoutContainer([_FakeItem(widget=object())])
        dock.publishGroupLayout = _FakeLayoutContainer([_FakeItem(widget=object())])
        dock.verticalLayout = _FakeLayoutContainer()
        dock.outerLayout = _FakeLayoutContainer()
        dock.outputGroupLayout = _FakeLayoutContainer()
        dock.dockWidgetContents = _FakeWidget()
        dock.activitiesGroupBox = _FakeGroupBox()
        dock.styleGroupBox = _FakeGroupBox()
        dock.analysisWorkflowGroupBox = _FakeGroupBox()
        dock.publishGroupBox = _FakeGroupBox()
        dock.outputGroupBox = _FakeWidget()
        dock.publishSettingsWidget = _FakeWidget()
        dock.credentialsGroupBox = _FakeWidget()
        dock.workflowLabel = _FakeLabel()
        dock.activitiesIntroLabel = _FakeLabel()
        dock.outputIntroLabel = _FakeLabel()
        dock.outputIntroLabel.text = "Pick where qfit should store the synced GeoPackage."
        dock.atlasPdfHelpLabel = _FakeLabel()
        dock.atlasPdfHelpLabel.text = "Export a per-activity PDF atlas using loaded activity_atlas_pages."
        dock.perPageLabel = _FakeLabel()
        dock.perPageSpinBox = _FakeSpinBox()
        dock.maxPagesLabel = _FakeLabel()
        dock.maxPagesSpinBox = _FakeSpinBox()
        dock.maxDetailedActivitiesLabel = _FakeLabel()
        dock.maxDetailedActivitiesSpinBox = _FakeSpinBox()
        dock.pointSamplingStrideLabel = _FakeLabel()
        dock.pointSamplingStrideSpinBox = _FakeSpinBox()
        dock.atlasPdfGroupBox = _FakeGroupBox()
        dock.generateAtlasPdfButton = _FakeWidget()
        dock.mapboxAccessTokenLabel = _FakeWidget()
        dock.mapboxAccessTokenLineEdit = _FakeWidget()
        dock.loadLayersButton = _FakeWidget()
        dock.clearDatabaseButton = _FakeWidget()
        dock.summaryStatusLabel = _FakeWidget()
        dock.countLabel = _FakeWidget()
        dock.statusLabel = _FakeWidget()
        return dock

    def test_configure_starting_sections_prepares_local_first_backing_controls(self):
        from qfit.ui.application.local_first_backing_controls import (
            configure_local_first_backing_controls,
        )

        class _FakeSignal:
            def __init__(self):
                self.callback = None

            def connect(self, callback):
                self.callback = callback

        class _FakeAction:
            def __init__(self, text):
                self.text = text
                self.tooltip = None
                self.triggered = _FakeSignal()

            def setToolTip(self, text):
                self.tooltip = text

        class _FakeMenu(_FakeWidget):
            def __init__(self, parent=None):
                super().__init__(parent)
                self.actions = []

            def addAction(self, text):
                action = _FakeAction(text)
                self.actions.append(action)
                return action

        class _FakeToolButton(_FakeWidget):
            def __init__(self, _parent=None):
                super().__init__()
                self.object_name = None
                self.text = None
                self.menu = None
                self.popup_mode = None

            def setObjectName(self, name):
                self.object_name = name

            def setText(self, text):
                self.text = text

            def setToolButtonStyle(self, _style):
                pass

            def setPopupMode(self, mode):
                self.popup_mode = mode

            def setMenu(self, menu):
                self.menu = menu

        _FakeToolButton.InstantPopup = "instant-popup"

        qtwidgets = ModuleType("qgis.PyQt.QtWidgets")
        qtwidgets.QMenu = _FakeMenu
        qtwidgets.QToolButton = _FakeToolButton

        dock = self._make_section_dock()
        with patch.dict(sys.modules, {"qgis.PyQt.QtWidgets": qtwidgets}):
            configure_local_first_backing_controls(dock)

        self.assertEqual(
            dock.workflowLabel.text,
            "Sections: Fetch & store · Visualize · Analyze · Publish",
        )
        self.assertFalse(dock.credentialsGroupBox.visible)
        self.assertEqual(dock.outputGroupBox.parent(), dock.activitiesGroupBox)
        self.assertEqual(dock.loadLayersButton.parent(), dock.styleGroupBox)
        self.assertFalse(dock.clearDatabaseButton.visible)
        self.assertIn(dock.clearDatabaseButton, dock.outputGroupLayout.removed_widgets)
        self.assertIn(dock.databaseActionsButton, dock.outputGroupLayout.added_widgets)
        self.assertEqual(dock.databaseActionsButton.text, "Database actions")
        self.assertEqual(dock.databaseActionsMenu.actions[0].text, "Clear database…")
        self.assertIs(
            dock.databaseActionsMenu.actions[0].triggered.callback.__self__,
            dock.clearDatabaseButton,
        )
        self.assertEqual(dock.summaryStatusLabel.parent(), dock.dockWidgetContents)
        self.assertIn(dock.summaryStatusLabel, dock.verticalLayout.removed_widgets)
        self.assertIn(dock.summaryStatusLabel, dock.outerLayout.added_widgets)
        self.assertTrue(dock._summary_status_footer_pinned)
        self.assertFalse(dock.countLabel.visible)
        self.assertFalse(dock.statusLabel.visible)
        self.assertEqual(dock.outputGroupBox.visible, None)
        self.assertFalse(hasattr(dock, "activitiesSectionToggleButton"))
        self.assertFalse(hasattr(dock, "activitiesSectionContentWidget"))
        self.assertFalse(hasattr(dock, "styleSectionToggleButton"))
        self.assertFalse(dock.activitiesIntroLabel.visible)
        self.assertIn("saved in qfit → Configuration", dock.activitiesGroupBox.tooltip)
        self.assertFalse(dock.outputIntroLabel.visible)
        self.assertEqual(dock.outputGroupBox.tooltip, dock.outputIntroLabel.text)
        self.assertFalse(dock.atlasPdfHelpLabel.visible)
        self.assertEqual(dock.atlasPdfGroupBox.tooltip, dock.atlasPdfHelpLabel.text)
        self.assertEqual(dock.generateAtlasPdfButton.tooltip, dock.atlasPdfHelpLabel.text)
        self.assertFalse(dock.mapboxAccessTokenLabel.visible)
        self.assertFalse(dock.mapboxAccessTokenLineEdit.visible)

    def test_configure_spinbox_unit_copy_moves_units_to_spinbox_suffixes(self):
        from qfit.ui.application.local_first_backing_controls import (
            configure_local_first_spinbox_unit_copy,
        )

        dock = self._make_section_dock()
        configure_local_first_spinbox_unit_copy(dock)

        self.assertEqual(dock.perPageLabel.text, "Page size")
        self.assertEqual(dock.perPageSpinBox.suffix, " activities")
        self.assertEqual(dock.maxPagesLabel.text, "Pages to fetch")
        self.assertEqual(dock.maxPagesSpinBox.suffix, " pages")
        self.assertEqual(
            dock.maxDetailedActivitiesLabel.text,
            "Max new detailed routes this run",
        )
        self.assertEqual(dock.maxDetailedActivitiesSpinBox.suffix, " routes")
        self.assertEqual(dock.pointSamplingStrideLabel.text, "Keep every Nth point")
        self.assertEqual(dock.pointSamplingStrideSpinBox.suffix, " points")

    def test_workflow_section_coordinator_compatibility_module_is_retired(self):
        self.assertIsNone(
            importlib.util.find_spec("qfit.ui.workflow_section_coordinator")
        )


class DockStartupCoordinatorTests(unittest.TestCase):
    def test_run_orchestrates_startup_in_constructor_order(self):
        dock = MagicMock()
        dock.DEFAULT_DOCK_FEATURES = sentinel.features
        dock.STARTUP_ALLOWED_AREAS = sentinel.allowed_areas
        with (
            patch(
                "qfit.ui.dock_startup_coordinator."
                "configure_local_first_backing_controls"
            ) as configure_local_first_backing_controls,
            patch(
                "qfit.ui.dock_startup_coordinator."
                "configure_local_first_spinbox_unit_copy"
            ) as configure_local_first_spinbox_unit_copy,
        ):
            coordinator = DockStartupCoordinator(dock)
            result = coordinator.run()

        self.assertEqual(
            result,
            DockStartupResult(
                performed_steps=(
                    "set_features",
                    "set_allowed_areas",
                    "ensure_wizard_settings",
                    "configure_local_first_backing_controls",
                    "remove_stale_qfit_layers",
                    "apply_contextual_help",
                    "configure_local_first_spinbox_unit_copy",
                    "configure_background_preset_options",
                    "configure_detailed_route_filter_options",
                    "configure_detailed_route_strategy_options",
                    "configure_preview_sort_options",
                    "configure_temporal_mode_options",
                    "configure_analysis_mode_options",
                    "load_settings",
                    "set_default_dates",
                    "wire_events",
                    "refresh_conditional_control_visibility",
                    "refresh_activity_preview",
                    "update_connection_status",
                ),
            ),
        )
        self.assertEqual(
            dock.mock_calls,
            [
                call.setFeatures(sentinel.features),
                call.setAllowedAreas(sentinel.allowed_areas),
                call._ensure_wizard_settings(),
                call._remove_stale_qfit_layers(),
                call._apply_contextual_help(),
                call._configure_background_preset_options(),
                call._configure_detailed_route_filter_options(),
                call._configure_detailed_route_strategy_options(),
                call._configure_preview_sort_options(),
                call._configure_temporal_mode_options(),
                call._configure_analysis_mode_options(),
                call._load_settings(),
                call._set_default_dates(),
                call._wire_events(),
                call._refresh_conditional_control_visibility(),
                call._refresh_activity_preview(),
                call._update_connection_status(),
            ],
        )
        configure_local_first_backing_controls.assert_called_once_with(dock)
        configure_local_first_spinbox_unit_copy.assert_called_once_with(dock)
