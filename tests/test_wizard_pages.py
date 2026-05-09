import importlib
import sys
import unittest
from unittest.mock import patch

from tests import _path  # noqa: F401
from tests.test_wizard_shell import _fake_qt_modules

from qfit.ui import application
from qfit.ui.application import workflow_page_specs
from qfit.ui.application.wizard_page_specs import (
    DockWizardPageSpec,
    build_default_wizard_page_specs,
)
from qfit.ui.application.workflow_page_specs import (
    DockWorkflowPageSpec,
    build_default_workflow_page_specs,
)
from qfit.ui.tokens import COLOR_MUTED, COLOR_TEXT


class WorkflowPageSpecsTests(unittest.TestCase):
    def test_default_specs_follow_stable_workflow_order(self):
        specs = build_default_workflow_page_specs()

        self.assertEqual(
            [(spec.key, spec.title) for spec in specs],
            [
                ("connection", "Connection"),
                ("sync", "Synchronization"),
                ("map", "Map & filters"),
                ("analysis", "Spatial analysis (optional)"),
                ("atlas", "Atlas PDF"),
            ],
        )
        self.assertEqual(specs[0].page_object_name, "qfitWizardConnectionPage")
        self.assertEqual(specs[0].body_object_name, "qfitWizardConnectionPageBody")
        self.assertIn("configure connection", specs[0].primary_action_hint)

    def test_default_specs_reject_missing_page_copy_with_clear_message(self):
        unknown_step = type("UnknownStep", (), {"key": "review", "title": "Review"})()

        with patch.object(workflow_page_specs, "WIZARD_WORKFLOW_STEPS", (unknown_step,)):
            with self.assertRaisesRegex(
                KeyError,
                "No page copy found for workflow step 'review'",
            ):
                build_default_workflow_page_specs()

    def test_application_package_exports_workflow_page_api(self):
        self.assertIs(application.DockWorkflowPageSpec, DockWorkflowPageSpec)
        self.assertEqual(
            application.build_default_workflow_page_specs(),
            build_default_workflow_page_specs(),
        )

    def test_wizard_named_api_remains_compatibility_alias(self):
        self.assertIs(DockWizardPageSpec, DockWorkflowPageSpec)
        self.assertEqual(
            build_default_wizard_page_specs(),
            build_default_workflow_page_specs(),
        )


def _load_wizard_modules():
    for name in (
        "qfit.ui.dockwidget.wizard_page",
        "qfit.ui.dockwidget.wizard_shell",
        "qfit.ui.dockwidget.stepper_bar",
        "qfit.ui.dockwidget",
    ):
        sys.modules.pop(name, None)
    with patch.dict(sys.modules, _fake_qt_modules()):
        return (
            importlib.import_module("qfit.ui.dockwidget.wizard_page"),
            importlib.import_module("qfit.ui.dockwidget.wizard_shell"),
        )


class WizardPageTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.wizard_page, cls.wizard_shell = _load_wizard_modules()

    def test_page_container_builds_visible_placeholder_chrome(self):
        spec = build_default_workflow_page_specs()[2]

        page = self.wizard_page.WizardPage(spec)

        self.assertEqual(page.objectName(), "qfitWizardMapPage")
        self.assertEqual(page.title_label.objectName(), "qfitWizardMapPageTitle")
        self.assertEqual(page.title_label.text(), "Map & filters")
        self.assertIn(COLOR_TEXT, page.title_label.styleSheet())
        self.assertIn("font-weight: 700", page.title_label.styleSheet())
        self.assertEqual(page.summary_label.objectName(), "qfitWizardMapPageSummary")
        self.assertIn("background map", page.summary_label.text())
        self.assertIn(COLOR_MUTED, page.summary_label.styleSheet())
        self.assertIn(COLOR_MUTED, page.primary_hint_label.styleSheet())
        self.assertNotIn("font-style: italic", page.primary_hint_label.styleSheet())
        for label in (page.title_label, page.summary_label, page.primary_hint_label):
            self.assertTrue(label.word_wrap)
            self.assertEqual(label.minimumWidth(), 0)
            self.assertEqual(label.size_policy, (3, 4))
        self.assertEqual(page.body_container.objectName(), "qfitWizardMapPageBody")
        self.assertEqual(page.body_layout().contents_margins, (0, 0, 0, 0))
        self.assertEqual(page.primary_hint_label.objectName(), "qfitWizardMapPagePrimaryHint")
        self.assertIn("apply map filters", page.primary_hint_label.text())
        self.assertEqual(
            page.outer_layout().widgets,
            [page.title_label, page.summary_label, page.body_container, page.primary_hint_label],
        )

    def test_retiring_primary_hint_removes_placeholder_copy(self):
        spec = build_default_workflow_page_specs()[1]
        page = self.wizard_page.WizardPage(spec)

        page.retire_primary_action_hint()

        self.assertEqual(page.primary_hint_label.text(), "")
        self.assertEqual(
            page.primary_hint_label.property("wizardPlaceholderHint"),
            "retired",
        )
        self.assertFalse(page.primary_hint_label.isVisible())

    def test_build_pages_preserves_explicit_empty_specs(self):
        pages = self.wizard_page.build_wizard_pages(specs=())

        self.assertEqual(pages, ())

    def test_installs_default_pages_into_wizard_shell(self):
        shell = self.wizard_shell.WizardShell()

        pages = self.wizard_page.install_wizard_pages(shell)

        self.assertEqual(shell.page_count(), 5)
        self.assertEqual([page.spec.key for page in pages], ["connection", "sync", "map", "analysis", "atlas"])
        self.assertEqual(shell.pages_stack.widgets, list(pages))

        shell.set_current_step(3)

        self.assertEqual(shell.pages_stack.currentIndex(), 3)


if __name__ == "__main__":
    unittest.main()
