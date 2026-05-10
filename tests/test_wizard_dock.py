import importlib
import sys
import unittest
from unittest.mock import patch

from tests import _path  # noqa: F401
from tests.test_wizard_shell import _fake_qt_modules
from tests.test_workflow_dock import _FakeDockWidget


def _load_wizard_dock_module():
    for name in (
        "qfit.ui.dockwidget.wizard_dock",
        "qfit.ui.dockwidget.workflow_dock",
        "qfit.ui.dockwidget._qt_compat",
    ):
        sys.modules.pop(name, None)
    package = sys.modules.get("qfit.ui.dockwidget")
    if package is not None:
        for attribute in ("wizard_dock", "workflow_dock"):
            if hasattr(package, attribute):
                delattr(package, attribute)
    modules = _fake_qt_modules()
    modules["qgis.PyQt.QtCore"].Qt.LeftDockWidgetArea = 8
    modules["qgis.PyQt.QtCore"].Qt.RightDockWidgetArea = 16
    modules["qgis.PyQt.QtWidgets"].QDockWidget = _FakeDockWidget
    with patch.dict(sys.modules, modules):
        return importlib.import_module("qfit.ui.dockwidget.wizard_dock")


class WizardDockWidgetTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.wizard_dock = _load_wizard_dock_module()

    def test_wizard_module_reexports_workflow_dock_api(self):
        self.assertEqual(
            self.wizard_dock.WorkflowDockWidget.__module__,
            "qfit.ui.dockwidget.workflow_dock",
        )
        self.assertEqual(
            self.wizard_dock.build_workflow_dock_widget.__module__,
            "qfit.ui.dockwidget.workflow_dock",
        )

    def test_wizard_names_remain_stable_compatibility_aliases(self):
        self.assertIs(self.wizard_dock.WizardDockWidget, self.wizard_dock.WorkflowDockWidget)
        self.assertIs(
            self.wizard_dock.WizardShellCompositionLike,
            self.wizard_dock.WorkflowShellCompositionLike,
        )
        self.assertIs(
            self.wizard_dock.build_wizard_dock_widget,
            self.wizard_dock.build_workflow_dock_widget,
        )
        self.assertEqual(
            self.wizard_dock.WIZARD_DOCK_OBJECT_NAME,
            self.wizard_dock.WORKFLOW_DOCK_OBJECT_NAME,
        )


if __name__ == "__main__":
    unittest.main()
