import importlib
import sys
import unittest
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock, patch

from tests import _path  # noqa: F401
from qfit.activities.domain.activity_query import DETAILED_ROUTE_FILTER_MISSING


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
        self.added = []
        self.contents_margins = None
        self.spacing = None

    def insertWidget(self, index, widget):
        self.inserted.append((index, widget))

    def addWidget(self, widget):
        self.added.append(widget)

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

    def count(self):
        return len(self.items)

    def itemText(self, index):
        return self.items[index]

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


class _FakeSubsetLayer:
    def __init__(self, subset="", feature_count=0):
        self._subset = subset
        self._feature_count = feature_count

    def subsetString(self):
        return self._subset

    def featureCount(self):
        return self._feature_count


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

    def set(self, key, value):
        self._values[key] = value


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
            ["None", "Most frequent starting points", "Heatmap"],
        )
        self.assertEqual(dock.runAnalysisButton.text(), "Run analysis")

    def test_set_default_dates_uses_current_date_window(self):
        dock = object.__new__(self.module.QfitDockWidget)
        dock.dateFromEdit = MagicMock()
        dock.dateToEdit = MagicMock()
        today = MagicMock()
        last_year = object()
        today.addYears.return_value = last_year

        with patch.object(self.module.QDate, "currentDate", return_value=today):
            self.module.QfitDockWidget._set_default_dates(dock)

        dock.dateFromEdit.setDate.assert_called_once_with(last_year)
        dock.dateToEdit.setDate.assert_called_once_with(today)
        today.addYears.assert_called_once_with(-1)

    def test_remove_stale_qfit_layers_delegates_to_project_hygiene_service(self):
        dock = object.__new__(self.module.QfitDockWidget)
        dock.project_hygiene_service = MagicMock()

        self.module.QfitDockWidget._remove_stale_qfit_layers(dock)

        dock.project_hygiene_service.remove_stale_qfit_layers.assert_called_once_with()

    def test_current_wizard_progress_facts_reads_live_dock_runtime(self):
        dock = object.__new__(self.module.QfitDockWidget)
        dock._runtime_state_store = self.module.DockRuntimeStore()
        dock.clientIdLineEdit = _FakeLineEdit("client-id")
        dock.clientSecretLineEdit = _FakeLineEdit("client-secret")
        dock.refreshTokenLineEdit = _FakeLineEdit("refresh-token")
        dock.atlasPdfPathLineEdit = _FakeLineEdit("/tmp/current-atlas.pdf")
        dock.backgroundMapCheckBox = _FakeCheckBox(True)
        dock.backgroundPresetComboBox = _FakeComboBox(current_text="Outdoors")
        dock.stylePresetComboBox = _FakeComboBox(current_text="By activity type")
        dock.settings = _FakeSettings({"last_sync_date": "2026-04-16"})
        dock._atlas_export_completed = True
        dock._atlas_export_output_path = "/tmp/exported-atlas.pdf"

        dock._runtime_store().load_dataset(
            output_path="/tmp/qfit.gpkg",
            stored_activity_count=4,
            activities_layer=object(),
            starts_layer=object(),
            points_layer=object(),
            atlas_layer=object(),
        )
        dock._runtime_store().set_analysis_layer(object())
        dock._runtime_store().set_background_layer(_FakeLayer("Outdoors"))

        facts = self.module.QfitDockWidget._current_wizard_progress_facts(dock)

        self.assertTrue(facts.connection_configured)
        self.assertTrue(facts.activities_stored)
        self.assertEqual(facts.activity_count, 4)
        self.assertTrue(facts.activity_layers_loaded)
        self.assertTrue(facts.analysis_generated)
        self.assertTrue(facts.atlas_exported)
        self.assertEqual(facts.atlas_output_name, "exported-atlas.pdf")
        self.assertTrue(facts.background_enabled)
        self.assertTrue(facts.background_layer_loaded)
        self.assertEqual(facts.background_name, "Outdoors")
        self.assertEqual(facts.activity_style_preset, "By activity type")
        self.assertEqual(facts.last_sync_date, "2026-04-16")

    def test_current_wizard_activity_style_preset_reads_trimmed_combo_text(self):
        dock = object.__new__(self.module.QfitDockWidget)
        dock.stylePresetComboBox = _FakeComboBox(current_text=" Simple lines ")

        style_preset = (
            self.module.QfitDockWidget._current_wizard_activity_style_preset(dock)
        )

        self.assertEqual(style_preset, "Simple lines")

    def test_current_wizard_background_facts_report_disabled_basemap(self):
        dock = object.__new__(self.module.QfitDockWidget)
        dock._runtime_state_store = self.module.DockRuntimeStore()
        dock.backgroundMapCheckBox = _FakeCheckBox(False)
        dock.backgroundPresetComboBox = _FakeComboBox(current_text="Outdoors")

        facts = self.module.QfitDockWidget._current_wizard_background_facts(
            dock,
            dock.runtime_state,
        )

        self.assertEqual(facts, (False, False, None))

    def test_current_wizard_background_facts_prefers_loaded_layer_over_pending_ui(self):
        dock = object.__new__(self.module.QfitDockWidget)
        dock._runtime_state_store = self.module.DockRuntimeStore()
        dock.backgroundMapCheckBox = _FakeCheckBox(False)
        dock.backgroundPresetComboBox = _FakeComboBox(current_text="Outdoors")
        dock._runtime_store().set_background_layer(_FakeLayer("Satellite"))

        facts = self.module.QfitDockWidget._current_wizard_background_facts(
            dock,
            dock.runtime_state,
        )

        self.assertEqual(facts, (True, True, "Satellite"))

    def test_current_wizard_background_facts_ignore_blank_loaded_layer_name(self):
        dock = object.__new__(self.module.QfitDockWidget)
        dock._runtime_state_store = self.module.DockRuntimeStore()
        dock.backgroundMapCheckBox = _FakeCheckBox(False)
        dock.backgroundPresetComboBox = _FakeComboBox(current_text="Outdoors")
        dock._runtime_store().set_background_layer(_FakeLayer("   "))

        facts = self.module.QfitDockWidget._current_wizard_background_facts(
            dock,
            dock.runtime_state,
        )

        self.assertEqual(facts, (True, True, None))

    def test_current_wizard_background_facts_report_enabled_basemap_name(self):
        dock = object.__new__(self.module.QfitDockWidget)
        dock._runtime_state_store = self.module.DockRuntimeStore()
        dock.backgroundMapCheckBox = _FakeCheckBox(True)
        dock.backgroundPresetComboBox = _FakeComboBox(current_text=" Satellite ")

        facts = self.module.QfitDockWidget._current_wizard_background_facts(
            dock,
            dock.runtime_state,
        )

        self.assertEqual(facts, (True, False, "Satellite"))

    def test_current_wizard_progress_facts_uses_frozen_atlas_path_during_export(self):
        dock = object.__new__(self.module.QfitDockWidget)
        dock._runtime_state_store = self.module.DockRuntimeStore()
        dock.clientIdLineEdit = _FakeLineEdit("client-id")
        dock.clientSecretLineEdit = _FakeLineEdit("client-secret")
        dock.refreshTokenLineEdit = _FakeLineEdit("refresh-token")
        dock.atlasPdfPathLineEdit = _FakeLineEdit("/tmp/new-atlas.pdf")
        dock._atlas_export_completed = True
        dock._atlas_export_output_path = "/tmp/old-atlas.pdf"
        dock._atlas_export_task_output_path = "/tmp/running-atlas.pdf"
        dock._runtime_store().set_atlas_export_task(object())

        facts = self.module.QfitDockWidget._current_wizard_progress_facts(dock)

        self.assertTrue(facts.atlas_exported)
        self.assertTrue(facts.atlas_export_in_progress)
        self.assertEqual(facts.atlas_output_name, "running-atlas.pdf")

    def test_current_wizard_filter_facts_prefers_loaded_layer_subset(self):
        dock = object.__new__(self.module.QfitDockWidget)
        dock._runtime_state_store = self.module.DockRuntimeStore()
        dock._runtime_store().set_activities([object(), object(), object()])
        dock._runtime_store().load_dataset(
            output_path="/tmp/qfit.gpkg",
            activities_layer=_FakeSubsetLayer('"activity_type" = \'Run\'', 2),
        )

        filters_active, filtered_count, filter_description = (
            self.module.QfitDockWidget._current_wizard_filter_facts(dock)
        )

        self.assertTrue(filters_active)
        self.assertEqual(filtered_count, 2)
        self.assertEqual(filter_description, "layer subset")

    def test_current_wizard_filter_facts_treats_empty_loaded_subset_as_unfiltered(self):
        dock = object.__new__(self.module.QfitDockWidget)
        dock._runtime_state_store = self.module.DockRuntimeStore()
        dock._runtime_store().set_activities([object(), object(), object()])
        dock._runtime_store().load_dataset(
            output_path="/tmp/qfit.gpkg",
            activities_layer=_FakeSubsetLayer("", 3),
        )

        filters_active, filtered_count, filter_description = (
            self.module.QfitDockWidget._current_wizard_filter_facts(dock)
        )

        self.assertFalse(filters_active)
        self.assertIsNone(filtered_count)
        self.assertIsNone(filter_description)

    def test_current_wizard_filter_facts_describes_preview_request_filters(self):
        dock = object.__new__(self.module.QfitDockWidget)
        dock._runtime_state_store = self.module.DockRuntimeStore()
        dock._runtime_store().set_activities([object(), object(), object()])
        preview_request = SimpleNamespace(
            activity_type="Run",
            search_text="alps",
            date_from="2026-04-01",
            date_to=None,
            min_distance_km=10,
            max_distance_km=None,
            detailed_route_filter=DETAILED_ROUTE_FILTER_MISSING,
        )
        dock._current_activity_preview_request = MagicMock(return_value=preview_request)

        with patch.object(
            self.module,
            "build_activity_preview_selection_state",
            return_value=SimpleNamespace(filtered_count=1),
        ):
            filters_active, filtered_count, filter_description = (
                self.module.QfitDockWidget._current_wizard_filter_facts(dock)
            )

        self.assertTrue(filters_active)
        self.assertEqual(filtered_count, 1)
        self.assertEqual(
            filter_description,
            "type: Run · search: “alps” · dates: from 2026-04-01 · "
            "distance: ≥ 10 km · routes: missing details",
        )

    def test_persist_wizard_step_index_clamps_and_saves_setting(self):
        dock = object.__new__(self.module.QfitDockWidget)
        dock.settings = _FakeSettings()

        saved_index = self.module.QfitDockWidget._persist_wizard_step_index(dock, 99)

        self.assertEqual(saved_index, 4)
        self.assertEqual(dock.settings.get("ui/last_step_index"), 4)
        self.assertTrue(dock.settings.get("ui/last_step_index_user_selected"))

    def test_show_connection_configuration_hint_opens_config_when_available(self):
        dock = object.__new__(self.module.QfitDockWidget)
        dock._open_configuration = MagicMock()
        dock._show_info = MagicMock()
        dock._set_status = MagicMock()

        self.module.QfitDockWidget._show_connection_configuration_hint(dock)

        dock._open_configuration.assert_called_once_with()
        dock._show_info.assert_not_called()
        dock._set_status.assert_called_once_with(
            "qfit configuration opened; save credentials to continue."
        )

    def test_show_connection_configuration_hint_reports_menu_path_without_opener(self):
        dock = object.__new__(self.module.QfitDockWidget)
        dock._show_info = MagicMock()
        dock._set_status = MagicMock()

        self.module.QfitDockWidget._show_connection_configuration_hint(dock)

        dock._show_info.assert_called_once_with(
            "Configure qfit connection",
            "Open qfit → Configuration from the QGIS plugin menu to edit Strava "
            "credentials, then return to the dock to continue the workflow.",
        )
        dock._set_status.assert_called_once_with(
            "Open qfit → Configuration to edit Strava credentials."
        )

    def test_refresh_configuration_from_settings_updates_live_connection_state(self):
        dock = object.__new__(self.module.QfitDockWidget)
        dock._load_settings = MagicMock()
        dock._update_connection_status = MagicMock()
        dock._refresh_summary_status = MagicMock()
        dock._set_status = MagicMock()

        self.module.QfitDockWidget.refresh_configuration_from_settings(dock)

        dock._load_settings.assert_called_once_with()
        dock._update_connection_status.assert_called_once_with()
        dock._refresh_summary_status.assert_not_called()
        dock._set_status.assert_called_once_with(
            "Configuration saved; qfit dock connection state refreshed."
        )

    def test_run_wizard_sync_step_fetches_when_no_activities_are_ready(self):
        dock = object.__new__(self.module.QfitDockWidget)
        dock._runtime_state_store = self.module.DockRuntimeStore()
        dock.on_refresh_clicked = MagicMock()
        dock.on_load_clicked = MagicMock()

        self.module.QfitDockWidget._run_wizard_sync_step(dock)

        dock.on_refresh_clicked.assert_called_once_with()
        dock.on_load_clicked.assert_not_called()

    def test_run_wizard_sync_step_stores_fetched_activities(self):
        dock = object.__new__(self.module.QfitDockWidget)
        dock._runtime_state_store = self.module.DockRuntimeStore()
        dock._runtime_store().set_activities([object()])
        dock.on_refresh_clicked = MagicMock()
        dock.on_load_clicked = MagicMock()

        self.module.QfitDockWidget._run_wizard_sync_step(dock)

        dock.on_load_clicked.assert_called_once_with()
        dock.on_refresh_clicked.assert_not_called()

    def test_run_wizard_map_step_loads_layers_before_filters_are_available(self):
        dock = object.__new__(self.module.QfitDockWidget)
        dock._runtime_state_store = self.module.DockRuntimeStore()
        dock.on_load_layers_clicked = MagicMock()
        dock.on_apply_filters_clicked = MagicMock()

        self.module.QfitDockWidget._run_wizard_map_step(dock)

        dock.on_load_layers_clicked.assert_called_once_with()
        dock.on_apply_filters_clicked.assert_not_called()

    def test_run_wizard_map_step_applies_filters_after_layers_are_loaded(self):
        dock = object.__new__(self.module.QfitDockWidget)
        dock._runtime_state_store = self.module.DockRuntimeStore()
        dock._runtime_store().set_dataset_layers(activities_layer=object())
        dock.on_load_layers_clicked = MagicMock()
        dock.on_apply_filters_clicked = MagicMock()

        self.module.QfitDockWidget._run_wizard_map_step(dock)

        dock.on_apply_filters_clicked.assert_called_once_with()
        dock.on_load_layers_clicked.assert_not_called()

    def test_build_wizard_shell_from_runtime_wires_persistence_and_callbacks(self):
        dock = object.__new__(self.module.QfitDockWidget)
        dock._runtime_state_store = self.module.DockRuntimeStore()
        dock.clientIdLineEdit = _FakeLineEdit("client-id")
        dock.clientSecretLineEdit = _FakeLineEdit("client-secret")
        dock.refreshTokenLineEdit = _FakeLineEdit("refresh-token")
        dock._atlas_export_completed = False
        dock.settings = _FakeSettings(
            {
                "ui/wizard_version": 1,
                "ui/last_step_index": 1,
            }
        )
        parent = object()

        class FakeWizardActionCallbacks(SimpleNamespace):
            pass

        fake_wizard_composition = ModuleType("qfit.ui.dockwidget.wizard_composition")
        fake_wizard_composition.WizardActionCallbacks = FakeWizardActionCallbacks
        fake_wizard_composition.build_placeholder_wizard_shell = MagicMock(
            return_value="composition"
        )
        fake_wizard_composition.connect_wizard_action_callbacks = MagicMock(
            return_value="connected-composition"
        )

        with patch.dict(
            sys.modules,
            {"qfit.ui.dockwidget.wizard_composition": fake_wizard_composition},
        ):
            composition = self.module.QfitDockWidget._build_wizard_shell_from_runtime(
                dock,
                parent=parent,
            )

        self.assertEqual(composition, "connected-composition")
        self.assertEqual(dock._wizard_shell_composition, "connected-composition")
        fake_wizard_composition.build_placeholder_wizard_shell.assert_called_once()
        _args, kwargs = fake_wizard_composition.build_placeholder_wizard_shell.call_args
        self.assertEqual(kwargs["parent"], parent)
        self.assertTrue(kwargs["progress_facts"].connection_configured)
        self.assertEqual(kwargs["wizard_settings"].last_step_index, 1)
        self.assertFalse(kwargs["wizard_settings"].first_launch)
        self.assertTrue(kwargs["use_step_pages"])
        self.assertIs(kwargs["on_current_step_changed"].__self__, dock)
        self.assertIs(
            kwargs["on_current_step_changed"].__func__,
            self.module.QfitDockWidget._persist_wizard_step_index,
        )

        fake_wizard_composition.connect_wizard_action_callbacks.assert_called_once()
        connect_args = fake_wizard_composition.connect_wizard_action_callbacks.call_args.args
        self.assertEqual(connect_args[0], "composition")
        callbacks = connect_args[1]
        expected_callbacks = {
            "configure_connection": "_show_connection_configuration_hint",
            "sync_activities": "_run_wizard_sync_step",
            "sync_saved_routes": "on_sync_routes_clicked",
            "load_activity_layers": "on_load_layers_clicked",
            "edit_map_filters": "_update_status_for_filter_visibility",
            "apply_map_filters": "_run_wizard_map_step",
            "run_analysis": "on_run_analysis_clicked",
            "set_analysis_mode": "_set_wizard_analysis_mode",
            "export_atlas": "on_generate_atlas_pdf_clicked",
        }
        for callback_name, method_name in expected_callbacks.items():
            callback = getattr(callbacks, callback_name)
            self.assertIs(callback.__self__, dock)
            self.assertIs(
                callback.__func__,
                getattr(self.module.QfitDockWidget, method_name),
            )

    def test_build_wizard_shell_from_runtime_skips_configured_startup_connection(self):
        dock = object.__new__(self.module.QfitDockWidget)
        dock._runtime_state_store = self.module.DockRuntimeStore()
        dock.clientIdLineEdit = _FakeLineEdit("client-id")
        dock.clientSecretLineEdit = _FakeLineEdit("client-secret")
        dock.refreshTokenLineEdit = _FakeLineEdit("refresh-token")
        dock._atlas_export_completed = False
        dock.settings = _FakeSettings(
            {
                "ui/wizard_version": 1,
                "ui/last_step_index": 0,
            }
        )

        class FakeWizardActionCallbacks(SimpleNamespace):
            pass

        fake_wizard_composition = ModuleType("qfit.ui.dockwidget.wizard_composition")
        fake_wizard_composition.WizardActionCallbacks = FakeWizardActionCallbacks
        fake_wizard_composition.build_placeholder_wizard_shell = MagicMock(
            return_value="composition"
        )
        fake_wizard_composition.connect_wizard_action_callbacks = MagicMock(
            return_value="connected-composition"
        )

        with patch.dict(
            sys.modules,
            {"qfit.ui.dockwidget.wizard_composition": fake_wizard_composition},
        ):
            composition = self.module.QfitDockWidget._build_wizard_shell_from_runtime(
                dock,
            )

        self.assertEqual(composition, "connected-composition")
        _args, kwargs = fake_wizard_composition.build_placeholder_wizard_shell.call_args
        self.assertEqual(kwargs["progress_facts"].preferred_current_key, "sync")
        self.assertEqual(dock.settings.get("ui/last_step_index"), 1)
        self.assertFalse(dock.settings.get("ui/last_step_index_user_selected"))

    def test_build_wizard_shell_from_runtime_preserves_user_selected_connection(self):
        dock = object.__new__(self.module.QfitDockWidget)
        dock._runtime_state_store = self.module.DockRuntimeStore()
        dock.clientIdLineEdit = _FakeLineEdit("client-id")
        dock.clientSecretLineEdit = _FakeLineEdit("client-secret")
        dock.refreshTokenLineEdit = _FakeLineEdit("refresh-token")
        dock._atlas_export_completed = False
        dock.settings = _FakeSettings(
            {
                "ui/wizard_version": 1,
                "ui/last_step_index": 0,
                "ui/last_step_index_user_selected": True,
            }
        )

        class FakeWizardActionCallbacks(SimpleNamespace):
            pass

        fake_wizard_composition = ModuleType("qfit.ui.dockwidget.wizard_composition")
        fake_wizard_composition.WizardActionCallbacks = FakeWizardActionCallbacks
        fake_wizard_composition.build_placeholder_wizard_shell = MagicMock(
            return_value="composition"
        )
        fake_wizard_composition.connect_wizard_action_callbacks = MagicMock(
            return_value="connected-composition"
        )

        with patch.dict(
            sys.modules,
            {"qfit.ui.dockwidget.wizard_composition": fake_wizard_composition},
        ):
            self.module.QfitDockWidget._build_wizard_shell_from_runtime(dock)

        _args, kwargs = fake_wizard_composition.build_placeholder_wizard_shell.call_args
        self.assertIsNone(kwargs["progress_facts"].preferred_current_key)
        self.assertEqual(dock.settings.get("ui/last_step_index"), 0)
        self.assertTrue(dock.settings.get("ui/last_step_index_user_selected"))


    def test_install_wizard_filter_controls_moves_live_filter_group_into_map_panel(self):
        dock = object.__new__(self.module.QfitDockWidget)
        parent_layout = MagicMock()
        parent_widget = SimpleNamespace(layout=lambda: parent_layout)
        filter_group = MagicMock()
        filter_group.parentWidget.return_value = parent_widget
        dock.filterGroupBox = filter_group
        panel = object()
        filter_layout = MagicMock()
        map_content = SimpleNamespace(
            filter_controls_panel=panel,
            filter_controls_layout=MagicMock(return_value=filter_layout),
            set_filter_controls_visible=MagicMock(),
        )

        self.module.QfitDockWidget._install_wizard_filter_controls(
            dock,
            SimpleNamespace(map_content=map_content),
        )

        parent_layout.removeWidget.assert_called_once_with(filter_group)
        filter_group.setParent.assert_called_once_with(panel)
        filter_layout.addWidget.assert_called_once_with(filter_group)
        filter_group.show.assert_called_once_with()
        map_content.set_filter_controls_visible.assert_called_once_with(False)
        self.assertTrue(dock._wizard_filter_controls_installed)

    def test_install_wizard_filter_controls_is_idempotent(self):
        dock = object.__new__(self.module.QfitDockWidget)
        dock._wizard_filter_controls_installed = True
        dock.filterGroupBox = MagicMock()
        map_content = SimpleNamespace(filter_controls_layout=MagicMock())

        self.module.QfitDockWidget._install_wizard_filter_controls(
            dock,
            SimpleNamespace(map_content=map_content),
        )

        map_content.filter_controls_layout.assert_not_called()

    def test_update_status_for_filter_visibility_updates_status_copy(self):
        dock = object.__new__(self.module.QfitDockWidget)
        dock._set_status = MagicMock()

        self.module.QfitDockWidget._update_status_for_filter_visibility(dock, True)
        self.module.QfitDockWidget._update_status_for_filter_visibility(dock, False)

        dock._set_status.assert_any_call(
            "Edit map filters, then apply filters when ready."
        )
        dock._set_status.assert_any_call("Map filter controls hidden.")


    def test_bind_wizard_analysis_mode_controls_exposes_non_none_modes(self):
        dock = object.__new__(self.module.QfitDockWidget)
        dock.analysisModeComboBox = _FakeComboBox()
        for mode in ("None", "Heatmap", "Most frequent starting points"):
            dock.analysisModeComboBox.addItem(mode)
        dock.analysisModeComboBox.setCurrentText("None")
        analysis_content = SimpleNamespace(set_analysis_mode_options=MagicMock())

        self.module.QfitDockWidget._bind_wizard_analysis_mode_controls(
            dock,
            SimpleNamespace(analysis_content=analysis_content),
        )

        analysis_content.set_analysis_mode_options.assert_called_once_with(
            ("Heatmap", "Most frequent starting points"),
            selected="Heatmap",
        )
        self.assertEqual(dock.analysisModeComboBox.currentText(), "Heatmap")

    def test_set_wizard_analysis_mode_updates_backing_combo(self):
        dock = object.__new__(self.module.QfitDockWidget)
        dock.analysisModeComboBox = _FakeComboBox()
        for mode in ("None", "Heatmap", "Most frequent starting points"):
            dock.analysisModeComboBox.addItem(mode)

        self.module.QfitDockWidget._set_wizard_analysis_mode(
            dock,
            "Most frequent starting points",
        )

        self.assertEqual(
            dock.analysisModeComboBox.currentText(),
            "Most frequent starting points",
        )

    def test_build_wizard_dock_from_runtime_wraps_live_composition(self):
        dock = object.__new__(self.module.QfitDockWidget)
        dock._build_wizard_shell_from_runtime = MagicMock(return_value="composition")
        parent = object()
        fake_wizard_dock = ModuleType("qfit.ui.dockwidget.wizard_dock")
        fake_wizard_dock.build_wizard_dock_widget = MagicMock(
            return_value="wizard-dock"
        )

        with patch.dict(sys.modules, {"qfit.ui.dockwidget.wizard_dock": fake_wizard_dock}):
            result = self.module.QfitDockWidget._build_wizard_dock_from_runtime(
                dock,
                parent=parent,
            )

        self.assertEqual(result, "wizard-dock")
        dock._build_wizard_shell_from_runtime.assert_called_once_with(parent=parent)
        fake_wizard_dock.build_wizard_dock_widget.assert_called_once_with(
            "composition",
            parent=parent,
        )

    def test_install_live_wizard_shell_hides_long_scroll_path(self):
        dock = object.__new__(self.module.QfitDockWidget)
        shell = object()
        composition = SimpleNamespace(shell=shell)
        dock.dockWidgetContents = object()
        dock.outerLayout = _FakeLayout()
        dock.scrollArea = MagicMock()
        dock.summaryStatusLabel = MagicMock()
        dock._build_wizard_shell_from_runtime = MagicMock(return_value=composition)

        self.module.QfitDockWidget._install_live_wizard_shell(dock)

        dock._build_wizard_shell_from_runtime.assert_called_once_with(
            parent=dock.dockWidgetContents,
        )
        dock.scrollArea.hide.assert_called_once_with()
        dock.summaryStatusLabel.hide.assert_called_once_with()
        self.assertEqual(dock.outerLayout.added, [shell])
        self.assertIs(dock._wizard_live_shell, shell)
        self.assertTrue(dock._wizard_live_path_installed)

    def test_install_live_wizard_shell_is_idempotent(self):
        dock = object.__new__(self.module.QfitDockWidget)
        dock._wizard_live_path_installed = True
        dock._build_wizard_shell_from_runtime = MagicMock()

        self.module.QfitDockWidget._install_live_wizard_shell(dock)

        dock._build_wizard_shell_from_runtime.assert_not_called()

    def test_install_live_wizard_shell_does_not_hide_legacy_path_without_layout(self):
        dock = object.__new__(self.module.QfitDockWidget)
        dock.dockWidgetContents = object()
        dock.scrollArea = MagicMock()
        dock.summaryStatusLabel = MagicMock()
        dock._build_wizard_shell_from_runtime = MagicMock(
            return_value=SimpleNamespace(shell=object()),
        )

        with self.assertRaisesRegex(RuntimeError, "base outer layout"):
            self.module.QfitDockWidget._install_live_wizard_shell(dock)

        dock.scrollArea.hide.assert_not_called()
        dock.summaryStatusLabel.hide.assert_not_called()


    def test_refresh_wizard_shell_from_runtime_updates_optional_composition(self):
        dock = object.__new__(self.module.QfitDockWidget)
        dock._runtime_state_store = self.module.DockRuntimeStore()
        dock.clientIdLineEdit = _FakeLineEdit("client-id")
        dock.clientSecretLineEdit = _FakeLineEdit("client-secret")
        dock.refreshTokenLineEdit = _FakeLineEdit("refresh-token")
        dock.settings = _FakeSettings(
            {
                "ui/wizard_version": 1,
                "ui/last_step_index": 1,
            }
        )
        composition = object()
        dock._wizard_shell_composition = composition
        fake_wizard_composition = ModuleType("qfit.ui.dockwidget.wizard_composition")
        fake_wizard_composition.refresh_wizard_shell_composition = MagicMock(
            return_value="refreshed"
        )

        with patch.dict(
            sys.modules,
            {"qfit.ui.dockwidget.wizard_composition": fake_wizard_composition},
        ):
            refreshed = self.module.QfitDockWidget._refresh_wizard_shell_from_runtime(dock)

        self.assertEqual(refreshed, "refreshed")
        self.assertEqual(dock._wizard_shell_composition, "refreshed")
        fake_wizard_composition.refresh_wizard_shell_composition.assert_called_once()
        args, kwargs = fake_wizard_composition.refresh_wizard_shell_composition.call_args
        self.assertEqual(args, (composition,))
        self.assertTrue(kwargs["progress_facts"].connection_configured)
        self.assertEqual(kwargs["wizard_settings"].last_step_index, 1)
        self.assertFalse(kwargs["wizard_settings"].first_launch)

    def test_refresh_summary_status_notifies_optional_wizard_shell_refresh(self):
        dock = object.__new__(self.module.QfitDockWidget)
        dock.summaryStatusLabel = _FakeLabel("")
        dock.connectionStatusLabel = _FakeLabel("Strava connection: ready")
        dock.countLabel = _FakeLabel("12 activities")
        dock.querySummaryLabel = _FakeLabel("filtered")
        dock.statusLabel = _FakeLabel("Ready")
        dock._refresh_wizard_shell_from_runtime = MagicMock()

        self.module.QfitDockWidget._refresh_summary_status(dock)

        self.assertEqual(
            dock.summaryStatusLabel.text(),
            "Strava connection: ready · 12 activities · filtered · Ready",
        )
        dock._refresh_wizard_shell_from_runtime.assert_called_once_with()

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
        dock._dock_visual_workflow = MagicMock()
        dock._dock_visual_workflow.dispatch_action.return_value = None
        dock._current_visual_workflow_request = MagicMock(return_value="request")

        self.module.QfitDockWidget._dispatch_dock_action(
            dock,
            self.module.ApplyVisualizationAction,
        )

        dock._dock_visual_workflow.dispatch_action.assert_called_once_with(
            self.module.ApplyVisualizationAction,
            "request",
            require_layers=True,
        )

    def test_dispatch_dock_action_handles_structured_dispatch_result(self):
        dock = object.__new__(self.module.QfitDockWidget)
        dock._dock_visual_workflow = MagicMock()
        dock._current_visual_workflow_request = MagicMock(return_value="request")
        dock._dock_visual_workflow.dispatch_action.return_value = SimpleNamespace(
            unsupported_reason="",
            background_error="boom",
            background_layer="background-layer",
            status="Applied current filters",
        )
        dock._show_error = MagicMock()
        dock._set_status = MagicMock()

        with patch.object(
            self.module,
            "build_background_map_failure_title",
            return_value="Background map failed",
        ) as build_title:
            self.module.QfitDockWidget._dispatch_dock_action(
                dock,
                self.module.RunAnalysisAction,
            )

        dock._dock_visual_workflow.dispatch_action.assert_called_once_with(
            self.module.RunAnalysisAction,
            "request",
            require_layers=True,
        )
        build_title.assert_called_once_with()
        dock._show_error.assert_called_once_with("Background map failed", "boom")
        self.assertEqual(dock.background_layer, "background-layer")
        dock._set_status.assert_called_once_with("Applied current filters")

    def test_dispatch_dock_action_reports_unsupported_reason(self):
        dock = object.__new__(self.module.QfitDockWidget)
        dock._dock_visual_workflow = MagicMock()
        dock._current_visual_workflow_request = MagicMock(return_value="request")
        dock._dock_visual_workflow.dispatch_action.return_value = SimpleNamespace(
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

    def test_on_load_background_clicked_uses_failure_title_helper(self):
        dock = object.__new__(self.module.QfitDockWidget)
        dock._save_settings = MagicMock()
        dock.background_controller = MagicMock()
        dock.background_controller.build_load_request.return_value = "background-request"
        dock.background_controller.load_background_request.side_effect = RuntimeError("boom")
        dock.backgroundMapCheckBox = _FakeCheckBox(True)
        dock.backgroundPresetComboBox = _FakeComboBox(current_text="Outdoors")
        dock._mapbox_access_token = MagicMock(return_value="token")
        dock.mapboxStyleOwnerLineEdit = _FakeLineEdit("mapbox")
        dock.mapboxStyleIdLineEdit = _FakeLineEdit("outdoors-v12")
        dock.tileModeComboBox = _FakeComboBox(current_text="raster")
        dock._show_error = MagicMock()
        dock._set_status = MagicMock()

        with patch.object(
            self.module,
            "build_background_map_failure_title",
            return_value="Background map failed",
        ) as build_title, patch.object(
            self.module,
            "build_background_map_failure_status",
            return_value="Background map could not be updated",
        ) as build_status:
            self.module.QfitDockWidget.on_load_background_clicked(dock)

        build_title.assert_called_once_with()
        build_status.assert_called_once_with()
        dock._show_error.assert_called_once_with("Background map failed", "boom")
        dock._set_status.assert_called_once_with("Background map could not be updated")

    def test_build_visual_workflow_action_uses_current_ui_state(self):
        dock = object.__new__(self.module.QfitDockWidget)
        dock.activities_layer = "activities"
        dock.starts_layer = "starts"
        dock.points_layer = "points"
        dock.atlas_layer = "atlas"
        dock._current_activity_preview_request = MagicMock(return_value="preview-request")
        selection_state = self.module.ActivitySelectionState(query=object(), filtered_count=3)
        dock.stylePresetComboBox = _FakeComboBox(current_text="By activity type")
        dock.temporalModeComboBox = _FakeComboBox(current_text="By month")
        dock.backgroundMapCheckBox = _FakeCheckBox(True)
        dock.backgroundPresetComboBox = _FakeComboBox(current_text="Outdoors")
        dock._mapbox_access_token = MagicMock(return_value="token")
        dock.mapboxStyleOwnerLineEdit = _FakeLineEdit("mapbox")
        dock.mapboxStyleIdLineEdit = _FakeLineEdit("style-id")
        dock.tileModeComboBox = _FakeComboBox(current_text="Raster")
        dock.analysisModeComboBox = _FakeComboBox(current_text="Most frequent starting points")

        with patch.object(
            self.module,
            "build_visual_layer_refs",
            return_value="layers",
        ) as build_layers, patch.object(
            self.module,
            "build_visual_workflow_selection_state_handoff",
            return_value="selection",
        ) as build_selection_handoff, patch.object(
            self.module,
            "build_activity_preview_selection_state",
            return_value=selection_state,
        ) as build_selection, patch.object(
            self.module,
            "build_visual_workflow_settings_snapshot",
            return_value="settings",
        ) as build_settings, patch.object(
            self.module,
            "build_visual_workflow_background_inputs",
            return_value="background",
        ) as build_background:
            request = self.module.QfitDockWidget._current_visual_workflow_request(
                dock,
                apply_subset_filters=False,
            )

        self.assertEqual(request.layers, "layers")
        self.assertEqual(request.selection_state, "selection")
        self.assertEqual(request.settings, "settings")
        self.assertEqual(request.background, "background")
        self.assertFalse(request.apply_subset_filters)
        build_layers.assert_called_once_with(
            activities_layer="activities",
            starts_layer="starts",
            points_layer="points",
            atlas_layer="atlas",
        )
        build_selection.assert_called_once_with("preview-request")
        build_selection_handoff.assert_called_once_with(selection_state)
        build_settings.assert_called_once_with(
            style_preset="By activity type",
            temporal_mode=self.module.DEFAULT_TEMPORAL_MODE_LABEL,
            analysis_mode="Most frequent starting points",
        )
        build_background.assert_called_once_with(
            enabled=True,
            preset_name="Outdoors",
            access_token="token",
            style_owner="mapbox",
            style_id="style-id",
            tile_mode="Raster",
        )

    def test_build_visual_workflow_action_delegates_to_visual_workflow_coordinator(self):
        dock = object.__new__(self.module.QfitDockWidget)
        dock._dock_visual_workflow = MagicMock()
        dock._dock_visual_workflow.build_action.return_value = "action"
        dock._current_visual_workflow_request = MagicMock(return_value="request")

        action = self.module.QfitDockWidget._build_visual_workflow_action(
            dock,
            self.module.ApplyVisualizationAction,
        )

        self.assertEqual(action, "action")
        dock._current_visual_workflow_request.assert_called_once_with()
        dock._dock_visual_workflow.build_action.assert_called_once_with(
            self.module.ApplyVisualizationAction,
            "request",
        )

    def test_run_selected_analysis_delegates_to_analysis_workflow(self):
        dock = object.__new__(self.module.QfitDockWidget)
        dock.analysis_workflow = MagicMock()
        dock.analysis_workflow.build_request.return_value = "analysis-request"
        dock.analysis_workflow.run_request.return_value = SimpleNamespace(
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
        dock.analysis_workflow.build_request.assert_called_once_with(
            analysis_mode="Most frequent starting points",
            starts_layer="starts-layer",
            selection_state=selection_state,
            activities_layer="activities-layer",
            points_layer="points-layer",
        )
        dock.analysis_workflow.run_request.assert_called_once_with("analysis-request")

    def test_run_selected_analysis_adds_returned_layer_to_project(self):
        dock = object.__new__(self.module.QfitDockWidget)
        dock.analysis_workflow = MagicMock()
        dock.analysis_workflow.build_request.return_value = "analysis-request"
        analysis_layer = _FakeLayer(self.module.FREQUENT_STARTING_POINTS_LAYER_NAME)
        dock.analysis_workflow.run_request.return_value = SimpleNamespace(
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
        dock._dock_visual_workflow = MagicMock()
        dock._current_visual_workflow_request = MagicMock(return_value="request")
        dock._dock_visual_workflow.dispatch_action.return_value = SimpleNamespace(
            status="Applied styling",
            background_error="",
            background_layer="background-layer",
        )
        dock._show_error = MagicMock()

        status = self.module.QfitDockWidget._apply_visual_configuration(dock, False)

        dock._current_visual_workflow_request.assert_called_once_with(
            apply_subset_filters=False
        )
        dock._dock_visual_workflow.dispatch_action.assert_called_once_with(
            self.module.ApplyVisualizationAction,
            "request",
            require_layers=False,
        )
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

        build_options.assert_called_once_with(("a1", "a2"), current_value="Run")
        self.assertIs(build_options.call_args.args[0], dock.runtime_state.activities)
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
        preview_request = SimpleNamespace()

        with patch.object(
            self.module,
            "build_activity_preview_request",
            return_value=preview_request,
        ) as build_request:
            request = self.module.QfitDockWidget._current_activity_preview_request(dock)

        self.assertIs(request, preview_request)
        build_request.assert_called_once_with(
            activities=("a1", "a2"),
            activity_type="Run",
            date_from="2026-04-01",
            date_to="2026-04-30",
            min_distance_km=5,
            max_distance_km=42,
            search_text="lunch",
            detailed_route_filter="missing",
            sort_label="Name (A–Z)",
        )
        self.assertIs(build_request.call_args.kwargs["activities"], dock.runtime_state.activities)

    def test_refresh_activity_preview_delegates_and_updates_widgets(self):
        dock = object.__new__(self.module.QfitDockWidget)
        dock._current_activity_preview_request = MagicMock(return_value="preview-request")
        dock.activity_workflow = SimpleNamespace(build_preview_result=MagicMock())
        dock.querySummaryLabel = SimpleNamespace(setText=MagicMock())
        dock.activityPreviewPlainTextEdit = SimpleNamespace(setPlainText=MagicMock())
        preview_result = SimpleNamespace(
            query_summary_text="2 activities",
            preview_text="first\nsecond",
            fetched_activities=["first", "second"],
        )
        dock.activity_workflow.build_preview_result.return_value = preview_result

        result = self.module.QfitDockWidget._refresh_activity_preview(dock)

        self.assertEqual(result, ["first", "second"])
        dock.activity_workflow.build_preview_result.assert_called_once_with("preview-request")
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
        dock._current_activity_preview_request = MagicMock(return_value="preview-request")
        selection_state = self.module.ActivitySelectionState(query=object(), filtered_count=2)
        inputs = SimpleNamespace(
            analysis_mode="Most frequent starting points",
            starts_layer="starts-layer",
            selection_state=selection_state,
        )

        with patch.object(
            self.module,
            "build_apply_analysis_configuration_inputs",
            return_value=inputs,
        ) as build_inputs, patch.object(
            self.module,
            "build_activity_preview_selection_state",
            return_value=selection_state,
        ) as build_selection_state:
            status = self.module.QfitDockWidget._apply_analysis_configuration(dock)

        self.assertEqual(status, "status")
        dock._clear_analysis_layer.assert_called_once_with()
        build_selection_state.assert_called_once_with("preview-request")
        build_inputs.assert_called_once_with(
            current_mode="Most frequent starting points",
            current_starts_layer="starts-layer",
            current_selection_state=selection_state,
            analysis_mode=None,
            starts_layer=None,
            selection_state=None,
        )
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
        dock._current_activity_preview_request = MagicMock(return_value="preview-request")
        selection_state = self.module.ActivitySelectionState(query=object(), filtered_count=0)
        inputs = SimpleNamespace(
            analysis_mode="Most frequent starting points",
            starts_layer=None,
            selection_state=selection_state,
        )

        with patch.object(
            self.module,
            "build_apply_analysis_configuration_inputs",
            return_value=inputs,
        ), patch.object(
            self.module,
            "build_activity_preview_selection_state",
            return_value=selection_state,
        ):
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
        dock._atlas_export_completed = True

        with patch.object(self.module.QgsProject, "instance", return_value=project):
            self.module.QfitDockWidget._clear_analysis_layer(dock)

        self.assertIsNone(dock.analysis_layer)
        self.assertFalse(dock._atlas_export_completed)
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
        dock.load_workflow.build_write_request.assert_called_once_with(
            activities=dock.runtime_state.activities,
            output_path="/tmp/qfit.gpkg",
            write_activity_points=True,
            point_stride=2,
            sync_metadata={"provider": "strava"},
            last_sync_date="2026-04-07",
        )
        self.assertIs(
            dock.load_workflow.build_write_request.call_args.kwargs["activities"],
            dock.runtime_state.activities,
        )
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
        dock._atlas_export_completed = True
        result = SimpleNamespace(output_path="/tmp/qfit.gpkg", total_stored=12, status="Stored 12 activities")

        self.module.QfitDockWidget._handle_store_task_finished(dock, result, None, False)

        self.assertIsNone(dock._store_task)
        self.assertTrue(dock.loadButton.isEnabled())
        self.assertEqual(dock.loadButton.text(), "Store activities")
        self.assertEqual(dock.output_path, "/tmp/qfit.gpkg")
        self.assertFalse(dock._atlas_export_completed)
        dock._update_stored_activities_summary.assert_called_once_with(12)
        dock._set_status.assert_called_once_with("Stored 12 activities")

    def test_on_sync_routes_clicked_starts_background_route_task(self):
        dock = object.__new__(self.module.QfitDockWidget)
        dock._route_sync_task = None
        dock._save_settings = MagicMock()
        dock.outputPathLineEdit = _FakeLineEdit("/tmp/qfit.gpkg")
        dock.clientIdLineEdit = _FakeLineEdit("client-id")
        dock.clientSecretLineEdit = _FakeLineEdit("client-secret")
        dock.refreshTokenLineEdit = _FakeLineEdit("refresh-token")
        dock.perPageSpinBox = _FakeSpinBox(100)
        dock.maxPagesSpinBox = _FakeSpinBox(0)
        dock.cache = "cache"
        dock.syncRoutesButton = _FakeButton("Sync saved routes")
        dock.exchangeCodeButton = _FakeButton("Exchange")
        dock.openAuthorizeButton = _FakeButton("Authorize")
        dock._set_status = MagicMock()
        dock.sync_controller = MagicMock()
        dock.sync_controller.build_route_sync_task_request.return_value = "route-request"
        fake_task = object()
        dock.sync_controller.build_route_sync_task.return_value = fake_task
        fake_task_manager = SimpleNamespace(addTask=MagicMock())

        with patch.object(
            self.module.QgsApplication,
            "taskManager",
            return_value=fake_task_manager,
        ):
            self.module.QfitDockWidget.on_sync_routes_clicked(dock)

        dock._save_settings.assert_called_once_with()
        dock.sync_controller.build_route_sync_task_request.assert_called_once_with(
            client_id="client-id",
            client_secret="client-secret",
            refresh_token="refresh-token",
            cache="cache",
            output_path="/tmp/qfit.gpkg",
            per_page=100,
            max_pages=0,
            use_gpx_geometry=True,
            on_finished=dock._handle_route_sync_task_finished,
        )
        dock.sync_controller.build_route_sync_task.assert_called_once_with("route-request")
        self.assertIs(dock._route_sync_task, fake_task)
        self.assertEqual(dock.syncRoutesButton.text(), "Cancel route sync")
        self.assertFalse(dock.exchangeCodeButton.isEnabled())
        self.assertFalse(dock.openAuthorizeButton.isEnabled())
        dock._set_status.assert_called_once_with("Syncing saved Strava routes…")
        fake_task_manager.addTask.assert_called_once_with(fake_task)

    def test_on_sync_routes_clicked_requests_cancel_without_clearing_running_task(self):
        dock = object.__new__(self.module.QfitDockWidget)
        running_task = MagicMock()
        dock._route_sync_task = running_task
        dock.syncRoutesButton = _FakeButton("Cancel route sync")
        dock.exchangeCodeButton = _FakeButton("Exchange")
        dock.openAuthorizeButton = _FakeButton("Authorize")
        dock._set_status = MagicMock()

        self.module.QfitDockWidget.on_sync_routes_clicked(dock)

        running_task.cancel.assert_called_once_with()
        self.assertIs(dock._route_sync_task, running_task)
        self.assertEqual(dock.syncRoutesButton.text(), "Cancelling route sync…")
        self.assertFalse(dock.syncRoutesButton.isEnabled())
        dock._set_status.assert_called_once_with("Route sync cancellation requested…")

    def test_handle_route_sync_task_finished_loads_route_layers(self):
        dock = object.__new__(self.module.QfitDockWidget)
        dock._route_sync_task = object()
        dock.syncRoutesButton = _FakeButton("Cancel route sync")
        dock.exchangeCodeButton = _FakeButton("Exchange")
        dock.exchangeCodeButton.setEnabled(False)
        dock.openAuthorizeButton = _FakeButton("Authorize")
        dock.openAuthorizeButton.setEnabled(False)
        dock.layer_gateway = MagicMock()
        route_layers = ("route-tracks", "route-points", "route-profile-samples")
        dock.layer_gateway.load_route_layers.return_value = route_layers
        dock.sync_controller = MagicMock()
        dock.sync_controller._rate_limit_note.return_value = ""
        dock._mark_atlas_export_stale = MagicMock()
        dock._set_status = MagicMock()
        result = {
            "path": "/tmp/qfit.gpkg",
            "fetched_count": 2,
            "route_track_count": 2,
            "route_point_count": 6,
            "route_profile_sample_count": 10,
            "sync": SimpleNamespace(inserted=1, updated=1, unchanged=0, total_count=2),
        }
        provider = SimpleNamespace(last_rate_limit=None)

        self.module.QfitDockWidget._handle_route_sync_task_finished(
            dock,
            result,
            None,
            False,
            provider,
        )

        self.assertIsNone(dock._route_sync_task)
        self.assertEqual(dock.runtime_state.route_tracks_layer, route_layers[0])
        self.assertEqual(dock.runtime_state.route_points_layer, route_layers[1])
        self.assertEqual(dock.runtime_state.route_profile_samples_layer, route_layers[2])
        self.assertEqual(dock.syncRoutesButton.text(), "Sync saved routes")
        self.assertTrue(dock.exchangeCodeButton.isEnabled())
        self.assertTrue(dock.openAuthorizeButton.isEnabled())
        dock.layer_gateway.load_route_layers.assert_called_once_with("/tmp/qfit.gpkg")
        dock._mark_atlas_export_stale.assert_called_once_with()
        dock._set_status.assert_called_once()

    def test_handle_route_sync_task_finished_reports_missing_result_path(self):
        dock = object.__new__(self.module.QfitDockWidget)
        dock._route_sync_task = object()
        dock.syncRoutesButton = _FakeButton("Cancel route sync")
        dock.exchangeCodeButton = _FakeButton("Exchange")
        dock.openAuthorizeButton = _FakeButton("Authorize")
        dock.layer_gateway = MagicMock()
        dock._show_error = MagicMock()
        dock._set_status = MagicMock()

        self.module.QfitDockWidget._handle_route_sync_task_finished(
            dock,
            {},
            None,
            False,
            SimpleNamespace(last_rate_limit=None),
        )

        self.assertIsNone(dock._route_sync_task)
        dock.layer_gateway.load_route_layers.assert_not_called()
        dock._show_error.assert_called_once()
        dock._set_status.assert_called_once_with("Load route layers failed")

    def test_on_refresh_clicked_cancels_existing_fetch_task(self):
        dock = object.__new__(self.module.QfitDockWidget)
        running_task = MagicMock()
        dock._fetch_task = running_task
        dock._set_fetch_running = MagicMock()
        dock._set_status = MagicMock()

        self.module.QfitDockWidget.on_refresh_clicked(dock)

        running_task.cancel.assert_called_once_with()
        self.assertIsNone(dock._fetch_task)
        dock._set_fetch_running.assert_called_once_with(False)
        dock._set_status.assert_called_once_with("Fetch cancelled.")

    def test_on_fetch_finished_updates_runtime_state_on_success(self):
        dock = object.__new__(self.module.QfitDockWidget)
        dock._fetch_task = object()
        dock._set_fetch_running = MagicMock()
        dock.activityTypeComboBox = _FakeComboBox(current_text="All")
        dock._current_activity_preview_request = MagicMock(return_value="preview-request")
        dock.activity_workflow = MagicMock()
        dock.settings = _FakeSettings()
        dock._apply_activity_type_options = MagicMock()
        dock.countLabel = _FakeLabel("")
        dock.querySummaryLabel = SimpleNamespace(setText=MagicMock())
        dock.activityPreviewPlainTextEdit = SimpleNamespace(setPlainText=MagicMock())
        dock._set_status = MagicMock()
        result = SimpleNamespace(
            cancelled=False,
            error_message=None,
            activities=[{"id": 1}],
            metadata={"provider": "strava"},
            today_str="2026-04-16",
            activity_type_options=SimpleNamespace(options=["All"], selected_value="All"),
            count_label_text="Activities fetched: 1",
            preview_result=SimpleNamespace(
                query_summary_text="1 activity",
                preview_text="Morning Run",
            ),
            status_text="Fetched 1 activity",
        )
        dock.activity_workflow.build_fetch_completion_result.return_value = result

        self.module.QfitDockWidget._on_fetch_finished(dock, [{"id": 1}], None, False, object())

        self.assertIsNone(dock._fetch_task)
        self.assertEqual(dock.activities, [{"id": 1}])
        self.assertEqual(dock.last_fetch_context, {"provider": "strava"})
        self.assertEqual(dock.settings.get("last_sync_date"), "2026-04-16")
        dock._set_fetch_running.assert_called_once_with(False)
        dock._apply_activity_type_options.assert_called_once_with(result.activity_type_options)
        self.assertEqual(dock.countLabel.text(), "Activities fetched: 1")
        dock.querySummaryLabel.setText.assert_called_once_with("1 activity")
        dock.activityPreviewPlainTextEdit.setPlainText.assert_called_once_with("Morning Run")
        dock._set_status.assert_called_once_with("Fetched 1 activity")

    def test_on_load_layers_clicked_updates_runtime_state_from_result(self):
        dock = object.__new__(self.module.QfitDockWidget)
        dock._save_settings = MagicMock()
        dock.outputPathLineEdit = _FakeLineEdit("/tmp/qfit.gpkg")
        dock._populate_activity_types_from_layer = MagicMock()
        dock._apply_visual_configuration = MagicMock(return_value="Styled layers")
        dock._update_loaded_activities_summary = MagicMock()
        dock._set_status = MagicMock()
        dock._atlas_export_completed = True
        workflow = MagicMock()
        workflow.build_load_existing_request.return_value = "load-request"
        result = SimpleNamespace(
            output_path="/tmp/qfit.gpkg",
            activities_layer="activities-layer",
            starts_layer="starts-layer",
            points_layer="points-layer",
            atlas_layer="atlas-layer",
            total_stored=12,
            status="Loaded 12 activities",
        )
        workflow.load_existing_request.return_value = result
        dock.dataset_load_workflow = workflow

        self.module.QfitDockWidget.on_load_layers_clicked(dock)

        self.assertEqual(dock.output_path, "/tmp/qfit.gpkg")
        self.assertEqual(dock.activities_layer, "activities-layer")
        self.assertEqual(dock.starts_layer, "starts-layer")
        self.assertEqual(dock.points_layer, "points-layer")
        self.assertEqual(dock.atlas_layer, "atlas-layer")
        self.assertFalse(dock._atlas_export_completed)
        dock._populate_activity_types_from_layer.assert_called_once_with()
        dock._apply_visual_configuration.assert_called_once_with(apply_subset_filters=False)
        dock._update_loaded_activities_summary.assert_called_once_with(12)
        dock._set_status.assert_called_once_with("Loaded 12 activities Styled layers")

    def test_on_generate_atlas_pdf_clicked_cancels_existing_export_task(self):
        dock = object.__new__(self.module.QfitDockWidget)
        running_task = MagicMock()
        dock._atlas_export_task = running_task
        dock._atlas_export_task_output_path = "/tmp/running-atlas.pdf"
        dock._set_atlas_pdf_status = MagicMock()
        dock._set_atlas_export_running = MagicMock()
        dock._refresh_summary_status = MagicMock()

        self.module.QfitDockWidget.on_generate_atlas_pdf_clicked(dock)

        running_task.cancel.assert_called_once_with()
        self.assertIsNone(dock._atlas_export_task)
        self.assertIsNone(dock._atlas_export_task_output_path)
        dock._set_atlas_pdf_status.assert_called_once_with("Atlas PDF export cancelled.")
        dock._set_atlas_export_running.assert_called_once_with(False)
        dock._refresh_summary_status.assert_called_once_with()

    def test_current_atlas_export_request_uses_current_ui_state(self):
        dock = object.__new__(self.module.QfitDockWidget)
        dock.atlas_layer = "atlas-layer"
        dock._current_activity_preview_request = MagicMock(return_value="preview-request")
        dock.atlasPdfPathLineEdit = _FakeLineEdit(" /tmp/qfit-atlas.pdf ")
        dock.atlasTitleLineEdit = _FakeLineEdit(" Spring Atlas ")
        dock.atlasSubtitleLineEdit = _FakeLineEdit(" Road and trail ")
        dock.tileModeComboBox = _FakeComboBox(current_text="Raster")
        dock.backgroundPresetComboBox = _FakeComboBox(current_text="Outdoors")
        dock.backgroundMapCheckBox = _FakeCheckBox(True)
        dock.mapboxStyleOwnerLineEdit = _FakeLineEdit(" mapbox ")
        dock.mapboxStyleIdLineEdit = _FakeLineEdit(" outdoors-v12 ")
        dock.settings = _FakeSettings()
        dock._on_atlas_export_finished = MagicMock()
        dock._mapbox_access_token = MagicMock(return_value="token")

        with patch.object(
            self.module,
            "build_activity_preview_selection_state",
            return_value="selection",
        ) as build_selection, patch.object(
            self.module,
            "build_native_profile_plot_style_from_settings",
            return_value="profile-style",
        ) as build_profile_style:
            request = self.module.QfitDockWidget._current_atlas_export_request(dock)

        self.assertEqual(request.atlas_layer, "atlas-layer")
        self.assertEqual(request.selection_state, "selection")
        self.assertEqual(request.output_path, "/tmp/qfit-atlas.pdf")
        self.assertEqual(request.atlas_title, "Spring Atlas")
        self.assertEqual(request.atlas_subtitle, "Road and trail")
        self.assertIs(request.on_finished, dock._on_atlas_export_finished)
        self.assertEqual(request.pre_export_tile_mode, "Raster")
        self.assertEqual(request.preset_name, "Outdoors")
        self.assertEqual(request.access_token, "token")
        self.assertEqual(request.style_owner, "mapbox")
        self.assertEqual(request.style_id, "outdoors-v12")
        self.assertTrue(request.background_enabled)
        self.assertEqual(request.profile_plot_style, "profile-style")
        build_selection.assert_called_once_with("preview-request")
        build_profile_style.assert_called_once_with(dock.settings)

    def test_on_generate_atlas_pdf_clicked_builds_command_via_atlas_workflow(self):
        dock = object.__new__(self.module.QfitDockWidget)
        atlas_layer = MagicMock()
        atlas_layer.featureCount.return_value = 3
        dock.atlas_export_use_case = MagicMock()
        dock.atlas_export_use_case.prepare_export.return_value = SimpleNamespace(
            path_changed=False,
            is_ready=True,
            output_path="/tmp/qfit-atlas.pdf",
        )
        dock.atlas_export_use_case.start_export.return_value = "atlas-task"
        dock._save_settings = MagicMock()
        runtime_store = MagicMock()
        runtime_store.state = SimpleNamespace(
            tasks=SimpleNamespace(atlas_export=None),
            layers=SimpleNamespace(atlas=atlas_layer),
        )
        dock._runtime_state_store = runtime_store
        dock._set_atlas_export_running = MagicMock()
        dock._set_atlas_pdf_status = MagicMock()
        dock._set_status = MagicMock()
        atlas_workflow = MagicMock()
        atlas_workflow.build_export_command.return_value = "command"
        task_manager = MagicMock()

        with patch.object(
            self.module.QfitDockWidget,
            "_current_atlas_export_request",
            return_value="request",
        ) as current_request, patch.object(
            self.module.QfitDockWidget,
            "_atlas_workflow_service",
            return_value=atlas_workflow,
        ) as atlas_workflow_service, patch.object(
            self.module.QgsApplication,
            "taskManager",
            return_value=task_manager,
        ):
            self.module.QfitDockWidget.on_generate_atlas_pdf_clicked(dock)

        atlas_workflow_service.assert_called_once_with()
        current_request.assert_called_once_with()
        atlas_workflow.build_export_command.assert_called_once_with("request")
        dock.atlas_export_use_case.prepare_export.assert_called_once_with("command")
        dock._save_settings.assert_called_once_with()
        dock.atlas_export_use_case.start_export.assert_called_once_with(
            dock.atlas_export_use_case.prepare_export.return_value,
            "command",
        )
        runtime_store.begin_atlas_export.assert_called_once_with("atlas-task")
        self.assertEqual(dock._atlas_export_task_output_path, "/tmp/qfit-atlas.pdf")
        dock._set_atlas_export_running.assert_called_once_with(True)
        dock._set_atlas_pdf_status.assert_called_once_with("Exporting atlas (3 pages)…")
        dock._set_status.assert_called_once_with("Generating atlas PDF…")
        task_manager.addTask.assert_called_once_with("atlas-task")

    def test_set_atlas_export_running_restores_sentence_case_button_label(self):
        dock = object.__new__(self.module.QfitDockWidget)
        dock.generateAtlasPdfButton = _FakeButton("Generate atlas PDF")
        dock.loadButton = _FakeButton("Store activities")
        dock.loadLayersButton = _FakeButton("Load activity layers")
        dock.refreshButton = _FakeButton("Fetch activities")

        self.module.QfitDockWidget._set_atlas_export_running(dock, True)

        self.assertEqual(dock.generateAtlasPdfButton.text(), "Cancel export")
        self.assertFalse(dock.loadButton.isEnabled())
        self.assertFalse(dock.loadLayersButton.isEnabled())
        self.assertFalse(dock.refreshButton.isEnabled())

        self.module.QfitDockWidget._set_atlas_export_running(dock, False)

        self.assertEqual(dock.generateAtlasPdfButton.text(), "Generate atlas PDF")
        self.assertTrue(dock.loadButton.isEnabled())
        self.assertTrue(dock.loadLayersButton.isEnabled())
        self.assertTrue(dock.refreshButton.isEnabled())

    def test_on_atlas_export_finished_clears_task_and_updates_status(self):
        dock = object.__new__(self.module.QfitDockWidget)
        dock._atlas_export_task = object()
        dock._set_atlas_export_running = MagicMock()
        dock._set_atlas_pdf_status = MagicMock()
        dock._set_status = MagicMock()
        dock._show_error = MagicMock()
        dock.atlas_export_use_case = MagicMock()
        dock.atlas_export_use_case.finish_export.return_value = SimpleNamespace(
            output_path="/tmp/qfit-atlas.pdf",
            pdf_status="Atlas PDF ready",
            main_status="Atlas created",
            error=None,
            cancelled=False,
        )

        self.module.QfitDockWidget._on_atlas_export_finished(
            dock,
            "/tmp/qfit-atlas.pdf",
            None,
            False,
            3,
        )

        self.assertIsNone(dock._atlas_export_task)
        self.assertTrue(dock._atlas_export_completed)
        self.assertEqual(dock._atlas_export_output_path, "/tmp/qfit-atlas.pdf")
        self.assertIsNone(dock._atlas_export_task_output_path)
        dock._set_atlas_export_running.assert_called_once_with(False)
        dock._set_atlas_pdf_status.assert_called_once_with("Atlas PDF ready")
        dock._set_status.assert_called_once_with("Atlas created")
        dock._show_error.assert_not_called()

    def test_on_atlas_pdf_browse_marks_export_stale_and_refreshes_wizard(self):
        dock = object.__new__(self.module.QfitDockWidget)
        dock.atlasPdfPathLineEdit = _FakeLineEdit("/tmp/old-atlas.pdf")
        dock._atlas_export_completed = True
        dock._atlas_export_output_path = "/tmp/old-atlas.pdf"
        dock._atlas_export_task_output_path = "/tmp/old-running-atlas.pdf"
        dock._refresh_summary_status = MagicMock()

        with patch.object(
            self.module.QFileDialog,
            "getSaveFileName",
            return_value=("/tmp/new-atlas", "PDF files (*.pdf)"),
            create=True,
        ):
            self.module.QfitDockWidget.on_atlas_pdf_browse_clicked(dock)

        self.assertEqual(dock.atlasPdfPathLineEdit.text(), "/tmp/new-atlas.pdf")
        self.assertFalse(dock._atlas_export_completed)
        self.assertIsNone(dock._atlas_export_output_path)
        self.assertIsNone(dock._atlas_export_task_output_path)
        dock._refresh_summary_status.assert_called_once_with()

    def test_on_atlas_pdf_browse_preserves_running_export_output_path(self):
        dock = object.__new__(self.module.QfitDockWidget)
        dock._runtime_state_store = self.module.DockRuntimeStore()
        dock._runtime_store().set_atlas_export_task(object())
        dock.atlasPdfPathLineEdit = _FakeLineEdit("/tmp/old-atlas.pdf")
        dock._atlas_export_completed = True
        dock._atlas_export_output_path = "/tmp/old-atlas.pdf"
        dock._atlas_export_task_output_path = "/tmp/running-atlas.pdf"
        dock._refresh_summary_status = MagicMock()

        with patch.object(
            self.module.QFileDialog,
            "getSaveFileName",
            return_value=("/tmp/new-atlas", "PDF files (*.pdf)"),
            create=True,
        ):
            self.module.QfitDockWidget.on_atlas_pdf_browse_clicked(dock)

        self.assertEqual(dock.atlasPdfPathLineEdit.text(), "/tmp/new-atlas.pdf")
        self.assertFalse(dock._atlas_export_completed)
        self.assertIsNone(dock._atlas_export_output_path)
        self.assertEqual(dock._atlas_export_task_output_path, "/tmp/running-atlas.pdf")
        dock._refresh_summary_status.assert_called_once_with()

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
        dock._atlas_export_completed = True
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
        self.assertFalse(dock._atlas_export_completed)


if __name__ == "__main__":
    unittest.main()
