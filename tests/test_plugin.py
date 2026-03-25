import os
import unittest

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


class FakeMainWindow:
    """Minimal stand-in for iface.mainWindow()."""
    pass


class FakeIface:
    """Minimal iface stub that records plugin menu and toolbar registrations."""

    def __init__(self):
        self._main_window = FakeMainWindow()
        self.menu_actions: list[tuple[str, object]] = []
        self.toolbar_actions: list[object] = []
        self.removed_menu_actions: list[tuple[str, object]] = []
        self.removed_toolbar_actions: list[object] = []

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
        pass

    def removeDockWidget(self, widget):
        pass

    def mapCanvas(self):
        return None


@unittest.skipUnless(
    QGIS_AVAILABLE,
    "PyQGIS is not available in this environment: {error}".format(error=QGIS_IMPORT_ERROR),
)
class TestQfitPluginMenuStructure(unittest.TestCase):
    """Verify that initGui registers two menu entries under &qfit."""

    def _make_plugin(self):
        iface = FakeIface()
        plugin = QfitPlugin(iface)
        return plugin, iface

    def test_init_gui_registers_activities_and_configuration_menu_entries(self):
        plugin, iface = self._make_plugin()
        plugin.initGui()

        menu_labels = [(name, action.text()) for name, action in iface.menu_actions]
        self.assertEqual(menu_labels, [
            ("&qfit", "Activities"),
            ("&qfit", "Configuration"),
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
        self.assertIsNone(plugin.dockwidget)


if __name__ == "__main__":
    unittest.main()
