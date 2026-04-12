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
        self._current_index = 0

    def addItem(self, text):
        self.items.append(text)
        if self._current_text is None:
            self._current_text = text
            self._current_index = len(self.items) - 1

    def clear(self):
        self.items = []
        self._current_text = None
        self._current_index = 0

    def findText(self, text):
        try:
            return self.items.index(text)
        except ValueError:
            return -1

    def currentText(self):
        return self._current_text

    def setCurrentText(self, text):
        self._current_text = text
        index = self.findText(text)
        if index >= 0:
            self._current_index = index

    def setCurrentIndex(self, index):
        self._current_index = index
        if 0 <= index < len(self.items):
            self._current_text = self.items[index]


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


class _FakeQDate:
    def __init__(self, value=None):
        self._value = value

    def isValid(self):
        return self._value is not None

    def toString(self, _format):
        return self._value


class _FakeDateEdit:
    def __init__(self, value=None):
        self._date = _FakeQDate(value)

    def date(self):
        return self._date


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
            ["None", "Most frequent starting points"],
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
        self.assertEqual(action.temporal_mode, self.module.DEFAULT_TEMPORAL_MODE_LABEL)
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

    def test_apply_activity_type_options_updates_combo_items_and_selection(self):
        dock = object.__new__(self.module.QfitDockWidget)
        dock.activityTypeComboBox = _FakeComboBox(current_text="Swim")
        dock.activityTypeComboBox.items = ["Swim"]

        self.module.QfitDockWidget._apply_activity_type_options(
            dock,
            self.module.ActivityTypeOptionsResult(
                options=["All", "Ride", "Trail Run"],
                selected_value="Trail Run",
            ),
        )

        self.assertEqual(dock.activityTypeComboBox.items, ["All", "Ride", "Trail Run"])
        self.assertEqual(dock.activityTypeComboBox.currentText(), "Trail Run")

    def test_populate_activity_types_delegates_to_activity_type_options_helper(self):
        dock = object.__new__(self.module.QfitDockWidget)
        dock.activities = ["a1", "a2"]
        dock.activityTypeComboBox = _FakeComboBox(current_text="Run")
        dock._apply_activity_type_options = MagicMock()
        result = self.module.ActivityTypeOptionsResult(options=["All", "Run"], selected_value="Run")

        with patch.object(self.module, "build_activity_type_options_from_activities", return_value=result) as build_options:
            self.module.QfitDockWidget._populate_activity_types(dock)

        build_options.assert_called_once_with(["a1", "a2"], current_value="Run")
        dock._apply_activity_type_options.assert_called_once_with(result)

    def test_current_activity_preview_request_reads_current_ui_filters(self):
        dock = object.__new__(self.module.QfitDockWidget)
        dock.activities = ["a1", "a2"]
        dock.activityTypeComboBox = _FakeComboBox(current_text="Run")
        dock.dateFromEdit = _FakeDateEdit("2026-04-01")
        dock.dateToEdit = _FakeDateEdit("2026-04-30")
        dock.minDistanceSpinBox = _FakeSpinBox(5)
        dock.maxDistanceSpinBox = _FakeSpinBox(42)
        dock.activitySearchLineEdit = _FakeLineEdit(" lunch ")
        dock.detailedRouteStatusComboBox = SimpleNamespace(currentData=lambda: "missing")
        dock.previewSortComboBox = _FakeComboBox(current_text="Name (A–Z)")

        request = self.module.QfitDockWidget._current_activity_preview_request(dock)

        self.assertEqual(request.activities, ["a1", "a2"])
        self.assertEqual(request.activity_type, "Run")
        self.assertEqual(request.date_from, "2026-04-01")
        self.assertEqual(request.date_to, "2026-04-30")
        self.assertEqual(request.min_distance_km, 5)
        self.assertEqual(request.max_distance_km, 42)
        self.assertEqual(request.search_text, "lunch")
        self.assertEqual(request.detailed_route_filter, "missing")
        self.assertEqual(request.sort_label, "Name (A–Z)")

    def test_current_activity_selection_state_delegates_to_activity_preview_workflow(self):
        dock = object.__new__(self.module.QfitDockWidget)
        dock._current_activity_preview_request = MagicMock(return_value="preview-request")
        selection_state = self.module.ActivitySelectionState(query=object(), filtered_count=2)

        with patch.object(self.module, "build_activity_selection_state", return_value=selection_state) as build_state:
            result = self.module.QfitDockWidget._current_activity_selection_state(dock)

        self.assertIs(result, selection_state)
        build_state.assert_called_once_with("preview-request")

    def test_refresh_activity_preview_delegates_and_updates_widgets(self):
        dock = object.__new__(self.module.QfitDockWidget)
        dock._current_activity_preview_request = MagicMock(return_value="preview-request")
        dock.querySummaryLabel = SimpleNamespace(setText=MagicMock())
        dock.activityPreviewPlainTextEdit = SimpleNamespace(setPlainText=MagicMock())
        preview_result = SimpleNamespace(
            query_summary_text="2 activities",
            preview_text="first\nsecond",
            fetched_activities=["first", "second"],
        )

        with patch.object(self.module, "build_activity_preview", return_value=preview_result) as build_preview:
            result = self.module.QfitDockWidget._refresh_activity_preview(dock)

        self.assertEqual(result, ["first", "second"])
        build_preview.assert_called_once_with("preview-request")
        dock.querySummaryLabel.setText.assert_called_once_with("2 activities")
        dock.activityPreviewPlainTextEdit.setPlainText.assert_called_once_with("first\nsecond")

    def test_populate_activity_types_from_layer_delegates_and_applies_result(self):
        dock = object.__new__(self.module.QfitDockWidget)
        dock.activityTypeComboBox = _FakeComboBox(current_text="Ride")
        dock._apply_activity_type_options = MagicMock()
        fields = SimpleNamespace(
            count=lambda: 2,
            at=lambda i: SimpleNamespace(name=lambda: ["sport_type", "activity_type"][i]),
        )
        result = self.module.ActivityTypeOptionsResult(options=["All", "TrailRun"], selected_value="TrailRun")

        class _Feature:
            def __getitem__(self, key):
                return {"sport_type": "TrailRun", "activity_type": "Run"}[key]

        dock.activities_layer = SimpleNamespace(
            isValid=lambda: True,
            fields=lambda: fields,
            getFeatures=lambda: [_Feature()],
        )

        with patch.object(self.module, "build_activity_type_options_from_records", return_value=result) as build_options:
            self.module.QfitDockWidget._populate_activity_types_from_layer(dock)

        build_options.assert_called_once()
        args, kwargs = build_options.call_args
        self.assertEqual(list(args[1]), ["sport_type", "activity_type"])
        self.assertEqual(kwargs["current_value"], "Ride")
        dock._apply_activity_type_options.assert_called_once_with(result)

    def test_update_connection_status_delegates_to_connection_status_helper(self):
        dock = object.__new__(self.module.QfitDockWidget)
        dock.clientIdLineEdit = _FakeLineEdit("client-id")
        dock.clientSecretLineEdit = _FakeLineEdit("client-secret")
        dock.refreshTokenLineEdit = _FakeLineEdit("refresh-token")
        dock.connectionStatusLabel = SimpleNamespace(setText=MagicMock())

        with patch.object(
            self.module,
            "build_strava_connection_status",
            return_value="Strava connection: ready to fetch activities",
        ) as build_status:
            self.module.QfitDockWidget._update_connection_status(dock)

        build_status.assert_called_once_with(
            client_id="client-id",
            client_secret="client-secret",
            refresh_token="refresh-token",
        )
        dock.connectionStatusLabel.setText.assert_called_once_with(
            "Strava connection: ready to fetch activities"
        )

    def test_update_cleared_activities_summary_delegates_to_layer_summary_helper(self):
        dock = object.__new__(self.module.QfitDockWidget)
        dock.countLabel = _FakeLabel("")

        with patch.object(
            self.module,
            "build_cleared_activities_summary",
            return_value="Activities fetched: 0",
        ) as build_summary:
            self.module.QfitDockWidget._update_cleared_activities_summary(dock)

        build_summary.assert_called_once_with()
        self.assertEqual(dock.countLabel.text(), "Activities fetched: 0")

    def test_update_last_sync_summary_delegates_to_layer_summary_helper(self):
        dock = object.__new__(self.module.QfitDockWidget)
        dock.settings = _FakeSettings({"last_sync_date": "2026-04-12"})
        dock.countLabel = _FakeLabel("")

        with patch.object(
            self.module,
            "build_last_sync_summary",
            return_value="Last sync: 2026-04-12",
        ) as build_summary:
            self.module.QfitDockWidget._update_last_sync_summary(dock)

        build_summary.assert_called_once_with(last_sync_date="2026-04-12")
        self.assertEqual(dock.countLabel.text(), "Last sync: 2026-04-12")

    def test_update_last_sync_summary_skips_empty_summary(self):
        dock = object.__new__(self.module.QfitDockWidget)
        dock.settings = _FakeSettings({})
        dock.countLabel = _FakeLabel("unchanged")

        with patch.object(self.module, "build_last_sync_summary", return_value=None):
            self.module.QfitDockWidget._update_last_sync_summary(dock)

        self.assertEqual(dock.countLabel.text(), "unchanged")

    def test_update_loaded_activities_summary_delegates_to_layer_summary_helper(self):
        dock = object.__new__(self.module.QfitDockWidget)
        dock.settings = _FakeSettings({"last_sync_date": "2026-04-12"})
        dock.countLabel = _FakeLabel("")

        with patch.object(
            self.module,
            "build_loaded_activities_summary",
            return_value="12 activities loaded (last sync: 2026-04-12)",
        ) as build_summary:
            self.module.QfitDockWidget._update_loaded_activities_summary(dock, 12)

        build_summary.assert_called_once_with(
            total_activities=12,
            last_sync_date="2026-04-12",
        )
        self.assertEqual(
            dock.countLabel.text(),
            "12 activities loaded (last sync: 2026-04-12)",
        )

    def test_update_stored_activities_summary_delegates_to_layer_summary_helper(self):
        dock = object.__new__(self.module.QfitDockWidget)
        dock.settings = _FakeSettings({"last_sync_date": "2026-04-12"})
        dock.countLabel = _FakeLabel("")

        with patch.object(
            self.module,
            "build_stored_activities_summary",
            return_value="12 activities stored in database (last sync: 2026-04-12)",
        ) as build_summary:
            self.module.QfitDockWidget._update_stored_activities_summary(dock, 12)

        build_summary.assert_called_once_with(
            total_activities=12,
            last_sync_date="2026-04-12",
        )
        self.assertEqual(
            dock.countLabel.text(),
            "12 activities stored in database (last sync: 2026-04-12)",
        )

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
        dock._update_stored_activities_summary = MagicMock()
        dock._set_status = MagicMock()
        result = SimpleNamespace(output_path="/tmp/qfit.gpkg", total_stored=12, status="Stored 12 activities")

        self.module.QfitDockWidget._handle_store_task_finished(dock, result, None, False)

        self.assertIsNone(dock._store_task)
        self.assertTrue(dock.loadButton.isEnabled())
        self.assertEqual(dock.loadButton.text(), "Store activities")
        self.assertEqual(dock.output_path, "/tmp/qfit.gpkg")
        dock._update_stored_activities_summary.assert_called_once_with(12)
        dock._set_status.assert_called_once_with("Stored 12 activities")

    def test_on_clear_database_clicked_reports_missing_output_path_via_helper(self):
        dock = object.__new__(self.module.QfitDockWidget)
        dock.outputPathLineEdit = _FakeLineEdit("")
        dock._show_error = MagicMock()

        with patch.object(
            self.module,
            "build_missing_output_path_error",
            return_value=("No database path", "Set a GeoPackage output path first."),
        ) as build_error:
            self.module.QfitDockWidget.on_clear_database_clicked(dock)

        build_error.assert_called_once_with()
        dock._show_error.assert_called_once_with(
            "No database path",
            "Set a GeoPackage output path first.",
        )

    def test_on_clear_database_clicked_uses_confirmation_helpers(self):
        dock = object.__new__(self.module.QfitDockWidget)
        dock.outputPathLineEdit = _FakeLineEdit("/tmp/qfit.gpkg")
        dock.activities_layer = object()
        dock.starts_layer = object()
        dock.points_layer = object()
        dock.atlas_layer = object()
        dock.load_workflow = MagicMock()
        dock.load_workflow.build_clear_database_request.return_value = "clear-request"
        dock.load_workflow.clear_database_request.return_value = SimpleNamespace(status="Database cleared")
        dock._clear_analysis_layer = MagicMock()
        dock._update_cleared_activities_summary = MagicMock()
        dock._set_status = MagicMock()
        dock._show_error = MagicMock()
        dock.activities = []
        dock.output_path = "/tmp/qfit.gpkg"
        dock.last_fetch_context = {}
        self.module.QMessageBox.Yes = 1
        self.module.QMessageBox.No = 0

        with patch.object(
            self.module,
            "build_clear_database_confirmation_title",
            return_value="Clear database",
        ) as build_title, patch.object(
            self.module,
            "build_clear_database_confirmation_body",
            return_value="Body text",
        ) as build_body, patch.object(
            self.module.QMessageBox,
            "question",
            return_value=1,
            create=True,
        ) as question:
            self.module.QfitDockWidget.on_clear_database_clicked(dock)

        build_title.assert_called_once_with()
        build_body.assert_called_once_with("/tmp/qfit.gpkg")
        question.assert_called_once()
        self.assertEqual(question.call_args.args[1], "Clear database")
        self.assertEqual(question.call_args.args[2], "Body text")

    def test_on_clear_database_clicked_reports_load_workflow_error_title_via_helper(self):
        dock = object.__new__(self.module.QfitDockWidget)
        dock.outputPathLineEdit = _FakeLineEdit("/tmp/qfit.gpkg")
        dock.activities_layer = object()
        dock.starts_layer = object()
        dock.points_layer = object()
        dock.atlas_layer = object()
        dock._show_error = MagicMock()
        dock.load_workflow = MagicMock()
        dock.load_workflow.build_clear_database_request.return_value = "clear-request"
        dock.load_workflow.clear_database_request.side_effect = self.module.LoadWorkflowError("missing file")
        self.module.QMessageBox.Yes = 1
        self.module.QMessageBox.No = 0

        with patch.object(self.module.QMessageBox, "question", return_value=1, create=True), patch.object(
            self.module,
            "build_clear_database_load_workflow_error_title",
            return_value="No database path",
        ) as build_title:
            self.module.QfitDockWidget.on_clear_database_clicked(dock)

        build_title.assert_called_once_with()
        dock._show_error.assert_called_once_with("No database path", "missing file")

    def test_on_clear_database_clicked_reports_delete_failure_status_via_helpers(self):
        dock = object.__new__(self.module.QfitDockWidget)
        dock.outputPathLineEdit = _FakeLineEdit("/tmp/qfit.gpkg")
        dock.activities_layer = object()
        dock.starts_layer = object()
        dock.points_layer = object()
        dock.atlas_layer = object()
        dock._show_error = MagicMock()
        dock._set_status = MagicMock()
        dock.load_workflow = MagicMock()
        dock.load_workflow.build_clear_database_request.return_value = "clear-request"
        dock.load_workflow.clear_database_request.side_effect = OSError("permission denied")
        self.module.QMessageBox.Yes = 1
        self.module.QMessageBox.No = 0

        with patch.object(self.module.QMessageBox, "question", return_value=1, create=True), patch.object(
            self.module,
            "build_clear_database_delete_failure_error_title",
            return_value="Could not delete database",
        ) as build_title, patch.object(
            self.module,
            "build_clear_database_delete_failure_status",
            return_value="Failed to delete the GeoPackage file",
        ) as build_status:
            self.module.QfitDockWidget.on_clear_database_clicked(dock)

        build_title.assert_called_once_with()
        dock._show_error.assert_called_once_with("Could not delete database", "permission denied")
        build_status.assert_called_once_with()
        dock._set_status.assert_called_once_with("Failed to delete the GeoPackage file")

    def test_on_clear_database_clicked_delegates_reset_summary_update(self):
        dock = object.__new__(self.module.QfitDockWidget)
        dock.outputPathLineEdit = _FakeLineEdit("/tmp/qfit.gpkg")
        dock.activities_layer = object()
        dock.starts_layer = object()
        dock.points_layer = object()
        dock.atlas_layer = object()
        dock._clear_analysis_layer = MagicMock()
        dock.activities = [1]
        dock.output_path = "/tmp/qfit.gpkg"
        dock.last_fetch_context = {"provider": "strava"}
        dock._update_cleared_activities_summary = MagicMock()
        dock._set_status = MagicMock()
        dock._show_error = MagicMock()
        dock.load_workflow = MagicMock()
        dock.load_workflow.build_clear_database_request.return_value = "clear-request"
        dock.load_workflow.clear_database_request.return_value = SimpleNamespace(status="Database cleared")
        self.module.QMessageBox.Yes = 1
        self.module.QMessageBox.No = 0

        with patch.object(self.module.QMessageBox, "question", return_value=1, create=True):
            self.module.QfitDockWidget.on_clear_database_clicked(dock)

        dock.load_workflow.build_clear_database_request.assert_called_once()
        dock.load_workflow.clear_database_request.assert_called_once_with("clear-request")
        dock._clear_analysis_layer.assert_called_once_with()
        dock._update_cleared_activities_summary.assert_called_once_with()
        dock._set_status.assert_called_once_with("Database cleared")
        self.assertEqual(dock.activities, [])
        self.assertIsNone(dock.activities_layer)
        self.assertIsNone(dock.output_path)


if __name__ == "__main__":
    unittest.main()
