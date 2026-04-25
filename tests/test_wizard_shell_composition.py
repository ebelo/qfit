import importlib
import sys
import unittest
from unittest.mock import patch

from tests import _path  # noqa: F401
from tests.test_wizard_shell import _fake_qt_modules

from qfit.ui.application.dock_workflow_sections import DockWizardProgress


def _load_wizard_composition_module():
    for name in (
        "qfit.ui.dockwidget.wizard_composition",
        "qfit.ui.dockwidget.wizard_shell_presenter",
        "qfit.ui.dockwidget.wizard_page",
        "qfit.ui.dockwidget.wizard_shell",
        "qfit.ui.dockwidget.stepper_bar",
        "qfit.ui.dockwidget",
    ):
        sys.modules.pop(name, None)
    with patch.dict(sys.modules, _fake_qt_modules()):
        return importlib.import_module("qfit.ui.dockwidget.wizard_composition")


class WizardShellCompositionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.composition = _load_wizard_composition_module()

    def test_builds_placeholder_shell_with_pages_before_presenter_renders(self):
        assembled = self.composition.build_placeholder_wizard_shell(footer_text="Ready")

        self.assertEqual(assembled.shell.objectName(), "qfitWizardShell")
        self.assertEqual(assembled.shell.footer_bar.text(), "Ready")
        self.assertEqual(assembled.shell.page_count(), 5)
        self.assertEqual(
            [page.spec.key for page in assembled.pages],
            ["connection", "sync", "map", "analysis", "atlas"],
        )
        self.assertEqual(assembled.shell.pages_stack.widgets, list(assembled.pages))
        self.assertEqual(assembled.presenter.progress.current_key, "connection")
        self.assertEqual(assembled.shell.pages_stack.currentIndex(), 0)
        self.assertEqual(
            assembled.shell.stepper_bar.states(),
            ("current", "locked", "locked", "locked", "locked"),
        )

    def test_initial_progress_selects_matching_installed_page(self):
        progress = DockWizardProgress(
            current_key="map",
            completed_keys=frozenset({"connection", "sync"}),
            visited_keys=frozenset({"map"}),
        )

        assembled = self.composition.build_placeholder_wizard_shell(progress=progress)

        self.assertEqual(assembled.shell.pages_stack.currentIndex(), 2)
        self.assertEqual(
            assembled.shell.stepper_bar.states(),
            ("done", "done", "current", "locked", "locked"),
        )

    def test_supports_explicit_empty_specs_without_binding_current_dock_controls(self):
        assembled = self.composition.build_placeholder_wizard_shell(specs=())

        self.assertEqual(assembled.pages, ())
        self.assertEqual(assembled.shell.page_count(), 0)
        self.assertEqual(assembled.shell.pages_stack.currentIndex(), -1)
        self.assertEqual(assembled.presenter.progress.current_key, "connection")


if __name__ == "__main__":
    unittest.main()
