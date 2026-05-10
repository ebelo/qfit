import importlib
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from tests import _path  # noqa: F401
from tests.test_wizard_shell import _FakeWidget, _fake_qt_modules


class _FakeDockWidget(_FakeWidget):
    DockWidgetClosable = 1
    DockWidgetMovable = 2
    DockWidgetFloatable = 4

    def __init__(self, parent=None):
        super().__init__(parent)
        self._widget = None
        self._features = None
        self._allowed_areas = None
        self._window_title = ""

    def setWidget(self, widget):  # noqa: N802
        self._widget = widget

    def widget(self):
        return self._widget

    def setFeatures(self, features):  # noqa: N802
        self._features = features

    def features(self):
        return self._features

    def setAllowedAreas(self, allowed_areas):  # noqa: N802
        self._allowed_areas = allowed_areas

    def allowedAreas(self):  # noqa: N802
        return self._allowed_areas

    def setWindowTitle(self, title):  # noqa: N802
        self._window_title = title

    def windowTitle(self):  # noqa: N802
        return self._window_title


def _load_workflow_dock_module():
    for name in (
        "qfit.ui.dockwidget.workflow_dock",
        "qfit.ui.dockwidget._qt_compat",
    ):
        sys.modules.pop(name, None)
    package = sys.modules.get("qfit.ui.dockwidget")
    if package is not None and hasattr(package, "workflow_dock"):
        delattr(package, "workflow_dock")
    modules = _fake_qt_modules()
    modules["qgis.PyQt.QtCore"].Qt.LeftDockWidgetArea = 8
    modules["qgis.PyQt.QtCore"].Qt.RightDockWidgetArea = 16
    modules["qgis.PyQt.QtWidgets"].QDockWidget = _FakeDockWidget
    with patch.dict(sys.modules, modules):
        return importlib.import_module("qfit.ui.dockwidget.workflow_dock")


class WorkflowDockWidgetTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow_dock = _load_workflow_dock_module()

    def test_workflow_dock_keeps_stable_qfit_wizard_object_name(self):
        self.assertEqual(
            self.workflow_dock.WORKFLOW_DOCK_OBJECT_NAME,
            "qfitWizardDockWidget",
        )
        self.assertNotIn("WIZARD_DOCK_OBJECT_NAME", self.workflow_dock.__all__)
        self.assertFalse(hasattr(self.workflow_dock, "WIZARD_DOCK_OBJECT_NAME"))

    def test_builds_qgis_dock_container_for_workflow_shell_composition(self):
        shell = _FakeWidget()
        parent = _FakeWidget()
        composition = SimpleNamespace(shell=shell)

        dock = self.workflow_dock.build_workflow_dock_widget(
            composition,
            parent=parent,
            title="qfit workflow",
        )

        self.assertEqual(dock.objectName(), "qfitWizardDockWidget")
        self.assertEqual(dock.windowTitle(), "qfit workflow")
        self.assertIs(dock.parent, parent)
        self.assertIs(dock.composition, composition)
        self.assertIs(dock.widget(), shell)
        self.assertEqual(
            dock.features(),
            _FakeDockWidget.DockWidgetClosable
            | _FakeDockWidget.DockWidgetMovable
            | _FakeDockWidget.DockWidgetFloatable,
        )
        self.assertEqual(dock.allowedAreas(), 8 | 16)
        self.assertIsInstance(dock, self.workflow_dock.WorkflowDockWidget)

    def test_can_replace_hosted_workflow_composition_without_recreating_dock(self):
        first = SimpleNamespace(shell=_FakeWidget())
        second = SimpleNamespace(shell=_FakeWidget())
        dock = self.workflow_dock.WorkflowDockWidget(first)

        dock.set_composition(second)

        self.assertIs(dock.composition, second)
        self.assertIs(dock.widget(), second.shell)

    def test_rejects_compositions_without_shell_widget(self):
        with self.assertRaisesRegex(ValueError, "must expose a shell"):
            self.workflow_dock.WorkflowDockWidget(SimpleNamespace(shell=None))

    def test_workflow_dock_exports_only_workflow_names(self):
        self.assertNotIn("WizardDockWidget", self.workflow_dock.__all__)
        self.assertNotIn("WizardShellCompositionLike", self.workflow_dock.__all__)
        self.assertNotIn("build_wizard_dock_widget", self.workflow_dock.__all__)
        self.assertFalse(hasattr(self.workflow_dock, "WizardDockWidget"))
        self.assertFalse(hasattr(self.workflow_dock, "WizardShellCompositionLike"))
        self.assertFalse(hasattr(self.workflow_dock, "build_wizard_dock_widget"))


if __name__ == "__main__":
    unittest.main()
