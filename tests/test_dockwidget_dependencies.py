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

    def setTitle(self, title):
        self.title = title

    def setCheckable(self, value):
        self.checkable = value


class _FakeLabel(_FakeWidget):
    def __init__(self):
        super().__init__()
        self.text = None

    def setText(self, text):
        self.text = text




class _FakeGroupBox:
    def __init__(self):
        self.parent_obj = None
        self.visible = None
        self.title = None
        self.checkable = None

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


class WorkflowSectionCoordinatorTests(unittest.TestCase):
    def _make_section_dock(self):
        dock = type("Dock", (), {})()
        dock.activitiesGroupLayout = _FakeLayoutContainer([_FakeItem(widget=object())])
        dock.styleGroupLayout = _FakeLayoutContainer([_FakeItem(widget=object())])
        dock.analysisWorkflowLayout = _FakeLayoutContainer([_FakeItem(widget=object())])
        dock.publishGroupLayout = _FakeLayoutContainer([_FakeItem(widget=object())])
        dock.verticalLayout = _FakeLayoutContainer()
        dock.outputGroupLayout = _FakeLayoutContainer()
        dock.activitiesGroupBox = _FakeGroupBox()
        dock.styleGroupBox = _FakeGroupBox()
        dock.analysisWorkflowGroupBox = _FakeGroupBox()
        dock.publishGroupBox = _FakeGroupBox()
        dock.outputGroupBox = _FakeWidget()
        dock.publishSettingsWidget = _FakeWidget()
        dock.credentialsGroupBox = _FakeWidget()
        dock.workflowLabel = _FakeLabel()
        dock.activitiesIntroLabel = _FakeLabel()
        dock.mapboxAccessTokenLabel = _FakeWidget()
        dock.mapboxAccessTokenLineEdit = _FakeWidget()
        dock.loadLayersButton = _FakeWidget()
        return dock

    def test_configure_starting_sections_moves_widgets_and_installs_collapsibles(self):
        import qfit.ui.workflow_section_coordinator as workflow_section_coordinator

        class _FakeSignal:
            def connect(self, _callback):
                pass

        class _FakeToolButton(_FakeWidget):
            def __init__(self, _parent=None):
                super().__init__()
                self.toggled = _FakeSignal()
                self.arrow_type = None
                self.checked = None
                self.object_name = None
                self.text = None

            def setObjectName(self, name):
                self.object_name = name

            def setText(self, text):
                self.text = text

            def setToolButtonStyle(self, _style):
                pass

            def setArrowType(self, arrow_type):
                self.arrow_type = arrow_type

            def setChecked(self, checked):
                self.checked = checked

            def setStyleSheet(self, _style):
                pass

        class _FakeVBoxLayout:
            def __init__(self, _parent=None):
                self.items = []
                self._spacing = 0

            def setContentsMargins(self, *_args):
                pass

            def setSpacing(self, spacing):
                self._spacing = spacing

            def addWidget(self, widget):
                self.items.append(("widget", widget))

            def addLayout(self, layout):
                self.items.append(("layout", layout))

            def addItem(self, item):
                self.items.append(("item", item))

        qtwidgets = ModuleType("qgis.PyQt.QtWidgets")
        qtwidgets.QToolButton = _FakeToolButton
        qtwidgets.QVBoxLayout = _FakeVBoxLayout
        qtwidgets.QWidget = _FakeWidget

        coordinator = workflow_section_coordinator.WorkflowSectionCoordinator(self._make_section_dock())
        with patch.dict(sys.modules, {"qgis.PyQt.QtWidgets": qtwidgets}):
            coordinator.configure_starting_sections()
        dock = coordinator.dock_widget

        self.assertEqual(dock.workflowLabel.text, "Workflow: Fetch & store → Visualize → Analyze → Publish")
        self.assertFalse(dock.credentialsGroupBox.visible)
        self.assertEqual(dock.outputGroupBox.parent(), dock.activitiesGroupBox)
        self.assertEqual(dock.loadLayersButton.parent(), dock.styleGroupBox)
        self.assertEqual(dock.outputGroupBox.visible, None)
        self.assertTrue(hasattr(dock, "activitiesSectionToggleButton"))
        self.assertTrue(hasattr(dock, "activitiesSectionContentWidget"))
        self.assertTrue(hasattr(dock, "styleSectionToggleButton"))
        self.assertFalse(dock.mapboxAccessTokenLabel.visible)
        self.assertFalse(dock.mapboxAccessTokenLineEdit.visible)

    def test_set_section_expanded_updates_toggle_arrow_and_content_visibility(self):
        import qfit.ui.workflow_section_coordinator as workflow_section_coordinator

        dock = type("Dock", (), {})()
        dock.activitiesSectionToggleButton = type("Toggle", (), {"arrow": None, "setArrowType": lambda self, val: setattr(self, "arrow", val)})()
        dock.activitiesSectionContentWidget = _FakeWidget()
        coordinator = workflow_section_coordinator.WorkflowSectionCoordinator(dock)

        coordinator.set_section_expanded("activities", False)
        self.assertEqual(dock.activitiesSectionToggleButton.arrow, workflow_section_coordinator.Qt.RightArrow)
        self.assertFalse(dock.activitiesSectionContentWidget.visible)

        coordinator.set_section_expanded("activities", True)
        self.assertEqual(dock.activitiesSectionToggleButton.arrow, workflow_section_coordinator.Qt.DownArrow)
        self.assertTrue(dock.activitiesSectionContentWidget.visible)

class WorkflowSectionCoordinatorVisibilityTests(unittest.TestCase):
    def _make_dock(self):
        dock = sentinel.dock
        attrs = {
            "backfillMissingDetailedRoutesButton": _VisibilityTarget(),
            "detailedRouteStrategyLabel": _VisibilityTarget(),
            "detailedRouteStrategyComboBox": _VisibilityTarget(),
            "maxDetailedActivitiesLabel": _VisibilityTarget(),
            "maxDetailedActivitiesSpinBox": _VisibilityTarget(),
            "pointSamplingStrideLabel": _VisibilityTarget(),
            "pointSamplingStrideSpinBox": _VisibilityTarget(),
            "advancedFetchSettingsWidget": _VisibilityTarget(),
            "mapboxStyleOwnerLabel": _VisibilityTarget(),
            "mapboxStyleOwnerLineEdit": _VisibilityTarget(),
            "mapboxStyleIdLabel": _VisibilityTarget(),
            "mapboxStyleIdLineEdit": _VisibilityTarget(),
            "detailedRouteStrategyComboBoxContextHelpLabel": _VisibilityTarget(),
            "detailedRouteStrategyComboBoxHelpField": _VisibilityTarget(),
            "maxDetailedActivitiesSpinBoxContextHelpLabel": _VisibilityTarget(),
            "maxDetailedActivitiesSpinBoxHelpField": _VisibilityTarget(),
            "pointSamplingStrideSpinBoxContextHelpLabel": _VisibilityTarget(),
            "pointSamplingStrideSpinBoxHelpField": _VisibilityTarget(),
            "mapboxStyleOwnerLineEditContextHelpLabel": _VisibilityTarget(),
            "mapboxStyleIdLineEditContextHelpLabel": _VisibilityTarget(),
            "mapboxStyleIdLineEditHelpField": _VisibilityTarget(),
            "detailedStreamsCheckBox": sentinel.detailedStreamsCheckBox,
            "writeActivityPointsCheckBox": sentinel.writeActivityPointsCheckBox,
            "advancedFetchGroupBox": sentinel.advancedFetchGroupBox,
            "backgroundPresetComboBox": sentinel.backgroundPresetComboBox,
        }
        dock = type("Dock", (), attrs)()
        dock.detailedStreamsCheckBox = sentinel.detailedStreamsCheckBox
        dock.writeActivityPointsCheckBox = sentinel.writeActivityPointsCheckBox
        dock.advancedFetchGroupBox = sentinel.advancedFetchGroupBox
        dock.backgroundPresetComboBox = sentinel.backgroundPresetComboBox
        return dock

    def test_workflow_section_coordinator_applies_visibility_rules(self):
        import qfit.ui.workflow_section_coordinator as workflow_section_coordinator

        with patch.object(
            workflow_section_coordinator,
            "preset_requires_custom_style",
            side_effect=lambda name: name == "Custom",
        ):
            WorkflowSectionCoordinator = workflow_section_coordinator.WorkflowSectionCoordinator

            detailed_streams = sentinel.detailedStreamsCheckBox
            detailed_streams.isChecked = lambda: True
            write_points = sentinel.writeActivityPointsCheckBox
            write_points.isChecked = lambda: False
            advanced_group = sentinel.advancedFetchGroupBox
            advanced_group.isChecked = lambda: True
            preset_combo = sentinel.backgroundPresetComboBox
            preset_combo.currentText = lambda: "Custom"

            dock = self._make_dock()
            coordinator = WorkflowSectionCoordinator(dock)
            coordinator.configure_workflow_sections()

        self.assertTrue(dock.backfillMissingDetailedRoutesButton.visible)
        self.assertTrue(dock.detailedRouteStrategyLabel.visible)
        self.assertFalse(dock.pointSamplingStrideSpinBox.visible)
        self.assertTrue(dock.advancedFetchSettingsWidget.visible)
        self.assertTrue(dock.mapboxStyleOwnerLineEdit.visible)
        self.assertTrue(dock.mapboxStyleIdLineEdit.visible)


class DockStartupCoordinatorTests(unittest.TestCase):
    def test_run_orchestrates_startup_in_constructor_order(self):
        dock = MagicMock()
        dock.DEFAULT_DOCK_FEATURES = sentinel.features
        dock.STARTUP_ALLOWED_AREAS = sentinel.allowed_areas
        workflow_section_coordinator = MagicMock()

        coordinator = DockStartupCoordinator(
            dock,
            workflow_section_coordinator=workflow_section_coordinator,
        )

        result = coordinator.run()

        self.assertEqual(
            result,
            DockStartupResult(
                performed_steps=(
                    "set_features",
                    "set_allowed_areas",
                    "configure_starting_sections",
                    "remove_stale_qfit_layers",
                    "apply_contextual_help",
                    "configure_background_preset_options",
                    "configure_detailed_route_filter_options",
                    "configure_detailed_route_strategy_options",
                    "configure_preview_sort_options",
                    "configure_temporal_mode_options",
                    "configure_analysis_mode_options",
                    "load_settings",
                    "wire_events",
                    "set_default_dates",
                    "configure_workflow_sections",
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
                call._remove_stale_qfit_layers(),
                call._apply_contextual_help(),
                call._configure_background_preset_options(),
                call._configure_detailed_route_filter_options(),
                call._configure_detailed_route_strategy_options(),
                call._configure_preview_sort_options(),
                call._configure_temporal_mode_options(),
                call._configure_analysis_mode_options(),
                call._load_settings(),
                call._wire_events(),
                call._set_default_dates(),
                call._refresh_activity_preview(),
                call._update_connection_status(),
            ],
        )
        self.assertEqual(
            workflow_section_coordinator.mock_calls,
            [
                call.configure_starting_sections(),
                call.configure_workflow_sections(),
            ],
        )
