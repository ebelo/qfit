import importlib
import sys
import unittest
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock, patch

from tests import _path  # noqa: F401


class _AutoModule(ModuleType):
    def __getattr__(self, name):  # pragma: no cover - helper for stub imports
        value = MagicMock(name=name)
        setattr(self, name, value)
        return value


class _FakeSignal:
    def __init__(self):
        self.connected = []

    def connect(self, callback):
        self.connected.append(callback)


class _FakeLayout:
    def __init__(self):
        self.inserted = []
        self.contents_margins = None
        self.spacing = None

    def insertWidget(self, index, widget):
        self.inserted.append((index, widget))

    def setContentsMargins(self, *margins):
        self.contents_margins = margins

    def setSpacing(self, spacing):
        self.spacing = spacing


class _FakeWidget:
    def __init__(self, parent=None):
        self._parent = parent
        self._object_name = None
        self._layout = None

    def setObjectName(self, name):
        self._object_name = name

    def objectName(self):
        return self._object_name

    def parentWidget(self):
        return self._parent

    def setLayout(self, layout):
        self._layout = layout

    def layout(self):
        return self._layout


class _FakeLabel(_FakeWidget):
    def __init__(self, text, parent=None):
        super().__init__(parent)
        self._text = text

    def text(self):
        return self._text

    def setText(self, text):
        self._text = text


class _FakeComboBox(_FakeWidget):
    def __init__(self, parent=None, current_text=None):
        super().__init__(parent)
        self.items = []
        self._current_text = current_text

    def addItem(self, text):
        self.items.append(text)
        if self._current_text is None:
            self._current_text = text

    def currentText(self):
        return self._current_text

    def setCurrentText(self, text):
        self._current_text = text


class _FakeButton(_FakeWidget):
    def __init__(self, text, parent=None):
        super().__init__(parent)
        self._text = text
        self._enabled = True
        self.clicked = _FakeSignal()

    def text(self):
        return self._text

    def setText(self, text):
        self._text = text

    def setEnabled(self, enabled):
        self._enabled = enabled

    def isEnabled(self):
        return self._enabled


class _FakeHBoxLayout(_FakeLayout):
    def __init__(self, widget):
        super().__init__()
        self.widget = widget
        self.children = []
        widget.setLayout(self)

    def addWidget(self, widget):
        self.children.append(widget)

    def addStretch(self, stretch):
        self.children.append(("stretch", stretch))


class _FakeLayerTreeRoot:
    def __init__(self):
        self.inserted = []

    def insertLayer(self, index, layer):
        self.inserted.append((index, layer))


class _FakeProject:
    def __init__(self, layers=None):
        self._layers = dict(layers or {})
        self.removed = []
        self.added = []
        self.layer_tree_root = _FakeLayerTreeRoot()

    def mapLayers(self):
        return dict(self._layers)

    def removeMapLayer(self, layer):
        self.removed.append(layer)

    def addMapLayer(self, layer, add_to_legend=True):
        self.added.append((layer, add_to_legend))

    def layerTreeRoot(self):
        return self.layer_tree_root


class _FakeLayer:
    _next_id = 1

    def __init__(self, name, source=""):
        self._name = name
        self._source = source
        self._id = _FakeLayer._next_id
        _FakeLayer._next_id += 1

    def name(self):
        return self._name

    def source(self):
        return self._source

    def id(self):
        return self._id


class _FakeLineEdit:
    def __init__(self, text=""):
        self._text = text

    def text(self):
        return self._text

    def setText(self, text):
        self._text = text


class _FakeSpinBox:
    def __init__(self, value):
        self._value = value

    def value(self):
        return self._value


class _FakeCheckBox:
    def __init__(self, checked=False):
        self._checked = checked

    def isChecked(self):
        return self._checked


class _FakeSettings:
    def __init__(self, values=None):
        self._values = dict(values or {})

    def get(self, key, default=None):
        return self._values.get(key, default)


class TestQfitDockWidgetAnalysisPure(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = cls._import_module_with_stubs()

    @staticmethod
    def _import_module_with_stubs():
        qgis_mod = ModuleType("qgis")
        qgis_core = _AutoModule("qgis.core")
        pyqt = ModuleType("qgis.PyQt")
        uic = ModuleType("qgis.PyQt.uic")
        uic.loadUiType = lambda _path: (type("FakeForm", (), {}), None)
        qtcore = _AutoModule("qgis.PyQt.QtCore")
        qtgui = _AutoModule("qgis.PyQt.QtGui")
        qtwidgets = _AutoModule("qgis.PyQt.QtWidgets")

        for name in [
            "QApplication",
            "QComboBox",
            "QFileDialog",
            "QDockWidget",
            "QGridLayout",
            "QHBoxLayout",
            "QLabel",
            "QMessageBox",
            "QPushButton",
            "QToolButton",
            "QVBoxLayout",
            "QWidget",
        ]:
            setattr(qtwidgets, name, type(name, (), {"__init__": lambda self, *a, **k: None}))
        qtwidgets.QDockWidget.DockWidgetClosable = 1
        qtwidgets.QDockWidget.DockWidgetMovable = 2
        qtwidgets.QDockWidget.DockWidgetFloatable = 4

        qgis_mod.core = qgis_core
        qgis_mod.PyQt = pyqt

        with patch.dict(
            sys.modules,
            {
                "qgis": qgis_mod,
                "qgis.core": qgis_core,
                "qgis.PyQt": pyqt,
                "qgis.PyQt.uic": uic,
                "qgis.PyQt.QtCore": qtcore,
                "qgis.PyQt.QtGui": qtgui,
                "qgis.PyQt.QtWidgets": qtwidgets,
            },
            clear=False,
        ):
            sys.modules.pop("qfit.qfit_dockwidget", None)
            return importlib.import_module("qfit.qfit_dockwidget")

    def test_configure_analysis_mode_options_inserts_row_into_section_content(self):
        dock = object.__new__(self.module.QfitDockWidget)
        section_content = _FakeWidget()
        content_layout = _FakeLayout()
        section_content.setLayout(content_layout)
        dock.analysisSectionContentWidget = section_content
        dock.analysisWorkflowGroupBox = _FakeWidget()
        dock.analysisWorkflowLayout = _FakeLayout()

        with patch.multiple(
            self.module,
            QWidget=_FakeWidget,
            QHBoxLayout=_FakeHBoxLayout,
            QLabel=_FakeLabel,
            QComboBox=_FakeComboBox,
            QPushButton=_FakeButton,
        ):
            self.module.QfitDockWidget._configure_analysis_mode_options(dock)

        self.assertEqual(len(content_layout.inserted), 1)
        index, row = content_layout.inserted[0]
        self.assertEqual(index, 0)
        self.assertEqual(row.objectName(), "analysisModeRow")
        self.assertEqual(dock.analysisModeLabel.text(), "Analysis")
        self.assertEqual(
            dock.analysisModeComboBox.items,
            ["None", "Most frequent starting points", "Heatmap"],
        )
        self.assertEqual(dock.runAnalysisButton.text(), "Run analysis")

    def test_remove_stale_qfit_layers_delegates_to_project_hygiene_service(self):
        dock = object.__new__(self.module.QfitDockWidget)
        dock.project_hygiene_service = MagicMock()

        self.module.QfitDockWidget._remove_stale_qfit_layers(dock)

        dock.project_hygiene_service.remove_stale_qfit_layers.assert_called_once_with()

    def test_on_apply_filters_clicked_dispatches_apply_visualization_action(self):
        dock = object.__new__(self.module.QfitDockWidget)
        dock._dispatch_dock_action = MagicMock()

        self.module.QfitDockWidget.on_apply_filters_clicked(dock)

        dock._dispatch_dock_action.assert_called_once_with(
            self.module.ApplyVisualizationAction
        )

    def test_on_run_analysis_clicked_dispatches_run_analysis_action(self):
        dock = object.__new__(self.module.QfitDockWidget)
        dock._dispatch_dock_action = MagicMock()

        self.module.QfitDockWidget.on_run_analysis_clicked(dock)

        dock._dispatch_dock_action.assert_called_once_with(
            self.module.RunAnalysisAction
        )

    def test_dispatch_dock_action_returns_early_without_layers(self):
        dock = object.__new__(self.module.QfitDockWidget)
        dock._build_visual_workflow_action = MagicMock(
            return_value=SimpleNamespace(layers=SimpleNamespace(has_any=lambda: False))
        )
        dock._dock_action_dispatcher = MagicMock()

        self.module.QfitDockWidget._dispatch_dock_action(
            dock,
            self.module.ApplyVisualizationAction,
        )

        dock._dock_action_dispatcher.dispatch.assert_not_called()

    def test_dispatch_dock_action_handles_structured_dispatch_result(self):
        dock = object.__new__(self.module.QfitDockWidget)
        action = SimpleNamespace(layers=SimpleNamespace(has_any=lambda: True))
        dock._build_visual_workflow_action = MagicMock(return_value=action)
        dock._dock_action_dispatcher = MagicMock()
        dock._dock_action_dispatcher.dispatch.return_value = SimpleNamespace(
            unsupported_reason="",
            background_error="boom",
            background_layer="background-layer",
            status="Applied current filters",
        )
        dock._show_error = MagicMock()
        dock._set_status = MagicMock()

        self.module.QfitDockWidget._dispatch_dock_action(
            dock,
            self.module.RunAnalysisAction,
        )

        dock._dock_action_dispatcher.dispatch.assert_called_once_with(action)
        dock._show_error.assert_called_once_with("Background map failed", "boom")
        self.assertEqual(dock.background_layer, "background-layer")
        dock._set_status.assert_called_once_with("Applied current filters")

    def test_dispatch_dock_action_reports_unsupported_reason(self):
        dock = object.__new__(self.module.QfitDockWidget)
        action = SimpleNamespace(layers=SimpleNamespace(has_any=lambda: True))
        dock._build_visual_workflow_action = MagicMock(return_value=action)
        dock._dock_action_dispatcher = MagicMock()
        dock._dock_action_dispatcher.dispatch.return_value = SimpleNamespace(
            unsupported_reason="Unsupported dock action: object",
            background_error="",
            background_layer=None,
            status="",
        )
        dock._set_status = MagicMock()

        self.module.QfitDockWidget._dispatch_dock_action(
            dock,
            self.module.ApplyVisualizationAction,
        )

        dock._set_status.assert_called_once_with("Unsupported dock action: object")

    def test_build_visual_workflow_action_uses_current_ui_state(self):
        dock = object.__new__(self.module.QfitDockWidget)
        dock.activities_layer = "activities"
        dock.starts_layer = "starts"
        dock.points_layer = "points"
        dock.atlas_layer = "atlas"
        selection_state = self.module.ActivitySelectionState(query=object(), filtered_count=3)
        dock._current_activity_selection_state = MagicMock(return_value=selection_state)
        dock.stylePresetComboBox = _FakeComboBox(current_text="By activity type")
        dock.temporalModeComboBox = _FakeComboBox(current_text="By month")
        dock.backgroundMapCheckBox = _FakeCheckBox(True)
        dock.backgroundPresetComboBox = _FakeComboBox(current_text="Outdoors")
        dock._mapbox_access_token = MagicMock(return_value="token")
        dock.mapboxStyleOwnerLineEdit = _FakeLineEdit("mapbox")
        dock.mapboxStyleIdLineEdit = _FakeLineEdit("style-id")
        dock.tileModeComboBox = _FakeComboBox(current_text="Raster")
        dock.analysisModeComboBox = _FakeComboBox(current_text="Most frequent starting points")

        action = self.module.QfitDockWidget._build_visual_workflow_action(
            dock,
            self.module.ApplyVisualizationAction,
        )

        self.assertIsInstance(action, self.module.ApplyVisualizationAction)
        self.assertEqual(action.layers.activities, "activities")
        self.assertEqual(action.layers.starts, "starts")
        self.assertIs(action.selection_state, selection_state)
        self.assertIs(action.query, selection_state.query)
        self.assertEqual(action.filtered_count, 3)
        self.assertEqual(action.analysis_mode, "Most frequent starting points")
        self.assertEqual(action.background_config.access_token, "token")
        self.assertEqual(action.background_config.tile_mode, "Raster")

    def test_run_selected_analysis_delegates_to_analysis_controller(self):
        dock = object.__new__(self.module.QfitDockWidget)
        dock.analysis_controller = MagicMock()
        dock.analysis_controller.build_request.return_value = "analysis-request"
        dock.analysis_controller.run_request.return_value = SimpleNamespace(
            status="Showing top 2 frequent starting-point clusters",
            layer=None,
        )
        dock.activities_layer = "activities-layer"
        dock.points_layer = "points-layer"
        selection_state = self.module.ActivitySelectionState(query=object(), filtered_count=2)

        result = self.module.QfitDockWidget._run_selected_analysis(
            dock,
            "Most frequent starting points",
            "starts-layer",
            selection_state,
        )

        self.assertEqual(result, "Showing top 2 frequent starting-point clusters")
        dock.analysis_controller.build_request.assert_called_once_with(
            analysis_mode="Most frequent starting points",
            activities_layer="activities-layer",
            starts_layer="starts-layer",
            points_layer="points-layer",
            selection_state=selection_state,
        )
        dock.analysis_controller.run_request.assert_called_once_with("analysis-request")

    def test_run_selected_analysis_adds_returned_layer_to_project(self):
        dock = object.__new__(self.module.QfitDockWidget)
        dock.analysis_controller = MagicMock()
        dock.analysis_controller.build_request.return_value = "analysis-request"
        analysis_layer = _FakeLayer(self.module.FREQUENT_STARTING_POINTS_LAYER_NAME)
        dock.analysis_controller.run_request.return_value = SimpleNamespace(
            status="Showing top 2 frequent starting-point clusters",
            layer=analysis_layer,
        )
        dock.activities_layer = "activities-layer"
        dock.points_layer = "points-layer"
        project = _FakeProject()
        selection_state = self.module.ActivitySelectionState(query=object(), filtered_count=2)

        with patch.object(self.module.QgsProject, "instance", return_value=project):
            status = self.module.QfitDockWidget._run_selected_analysis(
                dock,
                "Most frequent starting points",
                "starts-layer",
                selection_state,
            )

        self.assertEqual(status, "Showing top 2 frequent starting-point clusters")
        self.assertIs(dock.analysis_layer, analysis_layer)
        self.assertEqual(project.added, [(analysis_layer, False)])
        self.assertEqual(project.layer_tree_root.inserted, [(0, analysis_layer)])

    def test_apply_visual_configuration_dispatches_apply_action(self):
        dock = object.__new__(self.module.QfitDockWidget)
        action = self.module.ApplyVisualizationAction(
            layers=self.module.LayerRefs(activities="activities"),
            selection_state=self.module.ActivitySelectionState(query=object(), filtered_count=1),
            style_preset="By activity type",
            temporal_mode="By month",
            background_config=self.module.BackgroundConfig(),
            analysis_mode="None",
            apply_subset_filters=True,
        )
        dock._build_visual_workflow_action = MagicMock(return_value=action)
        dock._dock_action_dispatcher = MagicMock()
        dock._dock_action_dispatcher.dispatch.return_value = SimpleNamespace(
            status="Applied styling",
            background_error="",
            background_layer="background-layer",
        )
        dock._show_error = MagicMock()

        status = self.module.QfitDockWidget._apply_visual_configuration(dock, False)

        dispatched_action = dock._dock_action_dispatcher.dispatch.call_args.args[0]
        self.assertFalse(dispatched_action.apply_subset_filters)
        self.assertEqual(status, "Applied styling")
        self.assertEqual(dock.background_layer, "background-layer")
        dock._show_error.assert_not_called()

    def test_apply_analysis_configuration_delegates_current_mode_and_layer(self):
        dock = object.__new__(self.module.QfitDockWidget)
        dock.analysisModeComboBox = _FakeComboBox(current_text="Most frequent starting points")
        dock.starts_layer = "starts-layer"
        dock._clear_analysis_layer = MagicMock()
        dock._run_selected_analysis = MagicMock(return_value="status")
        selection_state = self.module.ActivitySelectionState(query=object(), filtered_count=2)
        dock._current_activity_selection_state = MagicMock(return_value=selection_state)

        status = self.module.QfitDockWidget._apply_analysis_configuration(dock)

        self.assertEqual(status, "status")
        dock._clear_analysis_layer.assert_called_once_with()
        dock._run_selected_analysis.assert_called_once_with(
            "Most frequent starting points",
            "starts-layer",
            selection_state,
        )

    def test_apply_analysis_configuration_defaults_missing_starts_layer_to_none(self):
        dock = object.__new__(self.module.QfitDockWidget)
        dock.analysisModeComboBox = _FakeComboBox(current_text="Most frequent starting points")
        dock._clear_analysis_layer = MagicMock()
        dock._run_selected_analysis = MagicMock(return_value="")
        selection_state = self.module.ActivitySelectionState(query=object(), filtered_count=0)
        dock._current_activity_selection_state = MagicMock(return_value=selection_state)

        status = self.module.QfitDockWidget._apply_analysis_configuration(dock)

        self.assertEqual(status, "")
        dock._run_selected_analysis.assert_called_once_with(
            "Most frequent starting points",
            None,
            selection_state,
        )

    def test_clear_analysis_layer_removes_current_and_stale_project_layers(self):
        dock = object.__new__(self.module.QfitDockWidget)
        current_layer = _FakeLayer(self.module.FREQUENT_STARTING_POINTS_LAYER_NAME)
        stale_layer = _FakeLayer(self.module.FREQUENT_STARTING_POINTS_LAYER_NAME)
        stale_heatmap_layer = _FakeLayer("qfit activity heatmap")
        project = _FakeProject(
            {"one": stale_layer, "two": _FakeLayer("other"), "three": stale_heatmap_layer}
        )
        dock.analysis_layer = current_layer

        with patch.object(self.module.QgsProject, "instance", return_value=project):
            self.module.QfitDockWidget._clear_analysis_layer(dock)

        self.assertIsNone(dock.analysis_layer)
        self.assertEqual(
            project.removed,
            [current_layer.id(), stale_layer.id(), stale_heatmap_layer.id()],
        )

    def test_on_load_clicked_starts_background_store_task(self):
        dock = object.__new__(self.module.QfitDockWidget)
        dock._store_task = None
        dock._save_settings = MagicMock()
        dock.activities = [{"id": 1}]
        dock.outputPathLineEdit = _FakeLineEdit("/tmp/qfit.gpkg")
        dock.writeActivityPointsCheckBox = _FakeCheckBox(True)
        dock.pointSamplingStrideSpinBox = _FakeSpinBox(2)
        dock.atlasMarginPercentSpinBox = _FakeSpinBox(10)
        dock.atlasMinExtentSpinBox = _FakeSpinBox(0.01)
        dock.atlasTargetAspectRatioSpinBox = _FakeSpinBox(1.5)
        dock.last_fetch_context = {"provider": "strava"}
        dock.settings = _FakeSettings({"last_sync_date": "2026-04-07"})
        dock.loadButton = _FakeButton("Store activities")
        dock._set_status = MagicMock()
        dock.load_workflow = MagicMock()
        dock.load_workflow.build_write_request.return_value = "store-request"
        fake_task = object()
        fake_task_manager = SimpleNamespace(addTask=MagicMock())

        with patch.object(self.module, "build_store_task", return_value=fake_task) as build_store_task, patch.object(
            self.module.QgsApplication,
            "taskManager",
            return_value=fake_task_manager,
        ):
            self.module.QfitDockWidget.on_load_clicked(dock)

        dock._save_settings.assert_called_once_with()
        dock.load_workflow.build_write_request.assert_called_once()
        build_store_task.assert_called_once()
        self.assertIs(dock._store_task, fake_task)
        self.assertEqual(dock.loadButton.text(), "Store in progress...")
        self.assertFalse(dock.loadButton.isEnabled())
        fake_task_manager.addTask.assert_called_once_with(fake_task)

    def test_handle_store_task_finished_restores_ui_and_status(self):
        dock = object.__new__(self.module.QfitDockWidget)
        dock._store_task = object()
        dock.loadButton = _FakeButton("Store in progress...")
        dock.loadButton.setEnabled(False)
        dock.outputPathLineEdit = _FakeLineEdit()
        dock.settings = _FakeSettings({"last_sync_date": "2026-04-07"})
        dock.countLabel = _FakeLabel("")
        dock._set_status = MagicMock()
        result = SimpleNamespace(output_path="/tmp/qfit.gpkg", total_stored=12, status="Stored 12 activities")

        self.module.QfitDockWidget._handle_store_task_finished(dock, result, None, False)

        self.assertIsNone(dock._store_task)
        self.assertTrue(dock.loadButton.isEnabled())
        self.assertEqual(dock.loadButton.text(), "Store activities")
        self.assertEqual(dock.output_path, "/tmp/qfit.gpkg")
        self.assertIn("12 activities stored in database", dock.countLabel.text())
        dock._set_status.assert_called_once_with("Stored 12 activities")


if __name__ == "__main__":
    unittest.main()
