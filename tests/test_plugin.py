import os
import unittest
from unittest.mock import MagicMock, patch

from tests import _path  # noqa: F401

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from qgis.PyQt.QtWidgets import QAction
    from qfit.qfit_plugin import QfitPlugin

    QGIS_AVAILABLE = True
    QGIS_IMPORT_ERROR = None
except Exception as exc:
    QfitPlugin = None
    QGIS_AVAILABLE = False
    QGIS_IMPORT_ERROR = exc


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


@unittest.skipUnless(
    QGIS_AVAILABLE,
    "PyQGIS is not available in this environment: {error}".format(error=QGIS_IMPORT_ERROR),
)
class TestQfitPluginMenuStructure(unittest.TestCase):
    """Verify that initGui registers menu entries under &qfit."""

    def _make_plugin(self):
        iface = FakeIface()
        plugin = QfitPlugin(iface)
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
            QfitPlugin._refresh_dock_configuration,
        )

        dialog.settingsSaved.connected_slot()

        plugin.dockwidget.refresh_configuration_from_settings.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
