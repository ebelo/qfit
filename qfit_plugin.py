import os

from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import QAction

from .qfit_config_dialog import QfitConfigDialog
from .qfit_dockwidget import QfitDockWidget
from .ui.about_dock import QfitAboutDock
from .ui.qt_enum_compat import optional_qt_enum_value, qt_enum_value

MENU_NAME = "&qfit"
QT_RIGHT_DOCK_WIDGET_AREA = qt_enum_value(Qt, "DockWidgetArea", "RightDockWidgetArea")


class QfitPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.activities_action = None
        self.config_action = None
        self.about_action = None
        self.dockwidget = None
        self._config_dialog = None
        self._about_dock = None

    def initGui(self):
        icon_path = os.path.join(os.path.dirname(__file__), "icon.png")
        icon = QIcon(icon_path)

        self.activities_action = QAction(icon, "Activities", self.iface.mainWindow())
        self.activities_action.triggered.connect(self.show_dock)
        self.iface.addToolBarIcon(self.activities_action)
        self.iface.addPluginToMenu(MENU_NAME, self.activities_action)

        self.config_action = QAction(icon, "Configuration", self.iface.mainWindow())
        self.config_action.triggered.connect(self.show_config)
        self.iface.addPluginToMenu(MENU_NAME, self.config_action)

        self.about_action = QAction(icon, "About", self.iface.mainWindow())
        self.about_action.triggered.connect(self.show_about)
        self.iface.addPluginToMenu(MENU_NAME, self.about_action)

    def unload(self):
        if self.activities_action is not None:
            self.iface.removePluginMenu(MENU_NAME, self.activities_action)
            self.iface.removeToolBarIcon(self.activities_action)
            self.activities_action = None

        if self.config_action is not None:
            self.iface.removePluginMenu(MENU_NAME, self.config_action)
            self.config_action = None

        if self.about_action is not None:
            self.iface.removePluginMenu(MENU_NAME, self.about_action)
            self.about_action = None

        if self.dockwidget is not None:
            self.iface.removeDockWidget(self.dockwidget)
            self.dockwidget.deleteLater()
            self.dockwidget = None

        if self._about_dock is not None:
            self.iface.removeDockWidget(self._about_dock)
            self._about_dock.deleteLater()
            self._about_dock = None

        if self._config_dialog is not None:
            self._config_dialog.close()
            self._config_dialog.deleteLater()
            self._config_dialog = None

    def show_dock(self):
        if self.dockwidget is None:
            self.dockwidget = QfitDockWidget(
                self.iface,
                parent=self.iface.mainWindow(),
                open_configuration=self.show_config,
            )
            self.iface.addDockWidget(QT_RIGHT_DOCK_WIDGET_AREA, self.dockwidget)
        self.dockwidget.show()
        self.dockwidget.raise_()

    def show_config(self):
        if self._config_dialog is None:
            self._config_dialog = QfitConfigDialog(parent=self.iface.mainWindow())
            self._config_dialog.settingsSaved.connect(self._refresh_dock_configuration)
        self._present_config_dialog()

    def _present_config_dialog(self) -> None:
        dialog = self._config_dialog
        if dialog is None:
            return

        self._restore_dialog_window_state(dialog)
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    def _restore_dialog_window_state(self, dialog) -> None:
        window_state = getattr(dialog, "windowState", None)
        set_window_state = getattr(dialog, "setWindowState", None)
        minimized = optional_qt_enum_value(Qt, "WindowState", "WindowMinimized")
        active = optional_qt_enum_value(Qt, "WindowState", "WindowActive")
        if (
            not callable(window_state)
            or not callable(set_window_state)
            or minimized is None
            or active is None
        ):
            return

        state = window_state()
        if state & minimized:
            set_window_state((state & ~minimized) | active)

    def show_about(self):
        if self._about_dock is None:
            self._about_dock = QfitAboutDock(parent=self.iface.mainWindow())
            self.iface.addDockWidget(QT_RIGHT_DOCK_WIDGET_AREA, self._about_dock)
            self._about_dock.setFloating(True)
        self._about_dock.show()
        self._about_dock.raise_()
        self._about_dock.activateWindow()

    def _refresh_dock_configuration(self) -> None:
        if self.dockwidget is not None:
            self.dockwidget.refresh_configuration_from_settings()
