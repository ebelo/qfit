import os
import sys
import unittest
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock, patch

from tests import _path  # noqa: F401

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


class FakeIface:
    """Minimal iface stub that records plugin menu and toolbar registrations."""

    def __init__(self):
        self._main_window = None
        self.menu_actions: list[tuple[str, object]] = []
        self.toolbar_actions: list[object] = []
        self.removed_menu_actions: list[tuple[str, object]] = []
        self.removed_toolbar_actions: list[object] = []
        self.dock_widgets: list[tuple[object, object]] = []
        self.removed_dock_widgets: list[object] = []

    def mainWindow(self):
        return self._main_window

    def addPluginToMenu(self, menu_name, action):
        self.menu_actions.append((menu_name, action))

    def removePluginMenu(self, menu_name, action):
        self.removed_menu_actions.append((menu_name, action))

    def addToolBarIcon(self, action):
        self.toolbar_actions.append(action)

    def removeToolBarIcon(self, action):
        self.removed_toolbar_actions.append(action)

    def addDockWidget(self, area, widget):
        self.dock_widgets.append((area, widget))

    def removeDockWidget(self, widget):
        self.removed_dock_widgets.append(widget)

    def mapCanvas(self):
        return None


class TestQfitPluginMenuStructure(unittest.TestCase):
    """Verify that initGui registers menu entries under &qfit."""

    @classmethod
    def setUpClass(cls):
        cls._module_names = cls._plugin_module_names() | set(cls._stub_modules())
        cls._saved_modules = {
            name: sys.modules.get(name) for name in cls._module_names
        }
        for name, module in cls._stub_modules().items():
            sys.modules[name] = module
        sys.modules.pop("qfit.qfit_plugin", None)
        from qfit.qfit_plugin import QfitPlugin

        cls.QfitPlugin = QfitPlugin

    @classmethod
    def tearDownClass(cls):
        for name in cls._module_names:
            original = cls._saved_modules.get(name)
            if original is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = original

    @staticmethod
    def _plugin_module_names():
        return {
            "qfit.qfit_plugin",
            "qfit.qfit_config_dialog",
            "qfit.qfit_dockwidget",
            "qfit.ui.about_dock",
        }

    @staticmethod
    def _stub_modules():
        qgis = ModuleType("qgis")
        qgis_pyqt = ModuleType("qgis.PyQt")
        qgis_qtcore = ModuleType("qgis.PyQt.QtCore")
        qgis_qtcore.Qt = SimpleNamespace(RightDockWidgetArea="right")
        qgis_qtgui = ModuleType("qgis.PyQt.QtGui")
        qgis_qtgui.QIcon = lambda path: ("icon", path)
        qgis_qtwidgets = ModuleType("qgis.PyQt.QtWidgets")

        class FakeSignal:
            def __init__(self):
                self.connected_slot = None

            def connect(self, slot):
                self.connected_slot = slot

        class FakeAction:
            def __init__(self, _icon, text, _parent=None):
                self._text = text
                self.triggered = FakeSignal()

            def text(self):
                return self._text

        qgis_qtwidgets.QAction = FakeAction

        config_dialog = ModuleType("qfit.qfit_config_dialog")
        config_dialog.QfitConfigDialog = object
        dockwidget = ModuleType("qfit.qfit_dockwidget")
        dockwidget.QfitDockWidget = object
        about_dock = ModuleType("qfit.ui.about_dock")
        about_dock.QfitAboutDock = object

        return {
            "qgis": qgis,
            "qgis.PyQt": qgis_pyqt,
            "qgis.PyQt.QtCore": qgis_qtcore,
            "qgis.PyQt.QtGui": qgis_qtgui,
            "qgis.PyQt.QtWidgets": qgis_qtwidgets,
            "qfit.qfit_config_dialog": config_dialog,
            "qfit.qfit_dockwidget": dockwidget,
            "qfit.ui.about_dock": about_dock,
        }

    def _make_plugin(self):
        iface = FakeIface()
        plugin = self.QfitPlugin(iface)
        return plugin, iface

    def test_init_gui_registers_activities_configuration_and_about_menu_entries(self):
        plugin, iface = self._make_plugin()
        plugin.initGui()

        menu_labels = [(name, action.text()) for name, action in iface.menu_actions]
        self.assertEqual(menu_labels, [
            ("&qfit", "Activities"),
            ("&qfit", "Configuration"),
            ("&qfit", "About"),
        ])

    def test_init_gui_adds_toolbar_icon_for_activities_only(self):
        plugin, iface = self._make_plugin()
        plugin.initGui()

        self.assertEqual(len(iface.toolbar_actions), 1)
        self.assertEqual(iface.toolbar_actions[0].text(), "Activities")

    def test_unload_removes_both_menu_entries(self):
        plugin, iface = self._make_plugin()
        plugin.initGui()
        plugin.unload()

        removed_labels = [(name, action.text()) for name, action in iface.removed_menu_actions]
        self.assertIn(("&qfit", "Activities"), removed_labels)
        self.assertIn(("&qfit", "Configuration"), removed_labels)
        self.assertIn(("&qfit", "About"), removed_labels)

    def test_unload_removes_toolbar_icon(self):
        plugin, iface = self._make_plugin()
        plugin.initGui()
        plugin.unload()

        self.assertEqual(len(iface.removed_toolbar_actions), 1)
        self.assertEqual(iface.removed_toolbar_actions[0].text(), "Activities")

    def test_unload_clears_action_references(self):
        plugin, iface = self._make_plugin()
        plugin.initGui()
        plugin.unload()

        self.assertIsNone(plugin.activities_action)
        self.assertIsNone(plugin.config_action)
        self.assertIsNone(plugin.about_action)
        self.assertIsNone(plugin.dockwidget)
        self.assertIsNone(plugin._about_dock)

    def test_show_about_creates_floating_about_dock(self):
        plugin, iface = self._make_plugin()

        class FakeAboutDock:
            created = []

            def __init__(self, parent=None):
                self.parent = parent
                self.setFloating = MagicMock()
                self.show = MagicMock()
                self.raise_ = MagicMock()
                self.activateWindow = MagicMock()
                self.deleteLater = MagicMock()
                FakeAboutDock.created.append(self)

        with patch("qfit.qfit_plugin.QfitAboutDock", FakeAboutDock):
            plugin.show_about()
            plugin.show_about()

        dock = FakeAboutDock.created[-1]
        self.assertIs(plugin._about_dock, dock)
        self.assertEqual(len(FakeAboutDock.created), 1)
        self.assertEqual(len(iface.dock_widgets), 1)
        dock.setFloating.assert_called_once_with(True)
        self.assertEqual(dock.show.call_count, 2)
        self.assertEqual(dock.raise_.call_count, 2)
        self.assertEqual(dock.activateWindow.call_count, 2)

    def test_show_dock_creates_activities_dock_once(self):
        plugin, iface = self._make_plugin()

        class FakeDockWidget:
            created = []

            def __init__(self, iface, parent=None, open_configuration=None):
                self.iface = iface
                self.parent = parent
                self.open_configuration = open_configuration
                self.show = MagicMock()
                self.raise_ = MagicMock()
                self.deleteLater = MagicMock()
                FakeDockWidget.created.append(self)

        with patch("qfit.qfit_plugin.QfitDockWidget", FakeDockWidget):
            plugin.show_dock()
            plugin.show_dock()

        dock = FakeDockWidget.created[-1]
        self.assertIs(plugin.dockwidget, dock)
        self.assertIs(dock.iface, iface)
        self.assertIs(dock.open_configuration.__self__, plugin)
        self.assertIs(dock.open_configuration.__func__, self.QfitPlugin.show_config)
        self.assertEqual(len(FakeDockWidget.created), 1)
        self.assertEqual(len(iface.dock_widgets), 1)
        self.assertEqual(dock.show.call_count, 2)
        self.assertEqual(dock.raise_.call_count, 2)

    def test_unload_removes_existing_docks_and_config_dialog(self):
        plugin, iface = self._make_plugin()
        dockwidget = MagicMock()
        about_dock = MagicMock()
        config_dialog = MagicMock()
        plugin.dockwidget = dockwidget
        plugin._about_dock = about_dock
        plugin._config_dialog = config_dialog

        plugin.unload()

        self.assertEqual(iface.removed_dock_widgets, [dockwidget, about_dock])
        dockwidget.deleteLater.assert_called_once_with()
        about_dock.deleteLater.assert_called_once_with()
        config_dialog.close.assert_called_once_with()
        config_dialog.deleteLater.assert_called_once_with()
        self.assertIsNone(plugin.dockwidget)
        self.assertIsNone(plugin._about_dock)
        self.assertIsNone(plugin._config_dialog)

    def test_config_dialog_save_signal_refreshes_existing_dock(self):
        plugin, _iface = self._make_plugin()
        plugin.dockwidget = MagicMock()

        class FakeSignal:
            def __init__(self):
                self.connected_slot = None

            def connect(self, slot):
                self.connected_slot = slot

        class FakeConfigDialog:
            created = []

            def __init__(self, parent=None):
                self.parent = parent
                self.settingsSaved = FakeSignal()
                self.show = MagicMock()
                self.raise_ = MagicMock()
                self.activateWindow = MagicMock()
                FakeConfigDialog.created.append(self)

        with patch("qfit.qfit_plugin.QfitConfigDialog", FakeConfigDialog):
            plugin.show_config()

        dialog = FakeConfigDialog.created[-1]
        self.assertIs(
            dialog.settingsSaved.connected_slot.__self__,
            plugin,
        )
        self.assertIs(
            dialog.settingsSaved.connected_slot.__func__,
            self.QfitPlugin._refresh_dock_configuration,
        )

        dialog.settingsSaved.connected_slot()

        plugin.dockwidget.refresh_configuration_from_settings.assert_called_once_with()

    def test_show_config_restores_and_raises_existing_dialog(self):
        plugin, _iface = self._make_plugin()
        plugin_module = sys.modules["qfit.qfit_plugin"]
        plugin_module.Qt.WindowMinimized = 0x01
        plugin_module.Qt.WindowActive = 0x02

        class FakeSignal:
            def connect(self, _slot):
                pass

        class FakeConfigDialog:
            created = []

            def __init__(self, parent=None):
                self.parent = parent
                self.settingsSaved = FakeSignal()
                self.show = MagicMock()
                self.raise_ = MagicMock()
                self.activateWindow = MagicMock()
                self.windowState = MagicMock(
                    side_effect=[
                        plugin_module.Qt.WindowMinimized,
                        plugin_module.Qt.WindowActive,
                    ]
                )
                self.setWindowState = MagicMock()
                FakeConfigDialog.created.append(self)

        with patch("qfit.qfit_plugin.QfitConfigDialog", FakeConfigDialog):
            plugin.show_config()
            plugin.show_config()

        dialog = FakeConfigDialog.created[-1]
        self.assertEqual(len(FakeConfigDialog.created), 1)
        dialog.setWindowState.assert_called_once_with(plugin_module.Qt.WindowActive)
        self.assertEqual(dialog.show.call_count, 2)
        self.assertEqual(dialog.raise_.call_count, 2)
        self.assertEqual(dialog.activateWindow.call_count, 2)


if __name__ == "__main__":
    unittest.main()
