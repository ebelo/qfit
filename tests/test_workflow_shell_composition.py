import importlib
import sys
import unittest
from unittest.mock import patch

from tests import _path  # noqa: F401
from tests.test_wizard_shell import _fake_qt_modules


_WORKFLOW_COMPOSITION_MODULE = "qfit.ui.dockwidget.workflow_composition"
_WIZARD_COMPOSITION_MODULE = "qfit.ui.dockwidget.wizard_composition"


def _load_workflow_composition_module():
    for name in (
        _WIZARD_COMPOSITION_MODULE,
        _WORKFLOW_COMPOSITION_MODULE,
        "qfit.ui.dockwidget.workflow_page_state",
        "qfit.ui.dockwidget.analysis_page",
        "qfit.ui.dockwidget.atlas_page",
        "qfit.ui.dockwidget.connection_page",
        "qfit.ui.dockwidget.sync_page",
        "qfit.ui.dockwidget.map_page",
        "qfit.ui.dockwidget.step_page",
        "qfit.ui.dockwidget.wizard_shell_presenter",
        "qfit.ui.dockwidget.workflow_shell_presenter",
        "qfit.ui.dockwidget.wizard_page",
        "qfit.ui.dockwidget.wizard_shell",
        "qfit.ui.dockwidget.stepper_bar",
        "qfit.ui.dockwidget",
    ):
        sys.modules.pop(name, None)
    with patch.dict(sys.modules, _fake_qt_modules()):
        return importlib.import_module(_WORKFLOW_COMPOSITION_MODULE)


class WorkflowShellCompositionModuleTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.composition = _load_workflow_composition_module()

    def test_workflow_composition_is_canonical_import_path(self):
        self.assertEqual(self.composition.__name__, _WORKFLOW_COMPOSITION_MODULE)
        self.assertNotIn(_WIZARD_COMPOSITION_MODULE, sys.modules)
        self.assertEqual(
            self.composition.WorkflowShellComposition.__module__,
            _WORKFLOW_COMPOSITION_MODULE,
        )
        self.assertEqual(
            self.composition.build_placeholder_workflow_shell.__module__,
            _WORKFLOW_COMPOSITION_MODULE,
        )
        self.assertEqual(
            self.composition.refresh_workflow_shell_composition.__module__,
            _WORKFLOW_COMPOSITION_MODULE,
        )
        self.assertEqual(
            self.composition.connect_workflow_action_callbacks.__module__,
            _WORKFLOW_COMPOSITION_MODULE,
        )

    def test_workflow_composition_preserves_direct_wizard_aliases_and_object_names(self):
        assembled = self.composition.build_placeholder_workflow_shell(
            footer_text="Ready"
        )

        self.assertIs(
            self.composition.WizardShellComposition,
            self.composition.WorkflowShellComposition,
        )
        self.assertIs(
            self.composition.build_wizard_page_states_from_facts,
            self.composition.build_workflow_page_states_from_facts,
        )
        self.assertIs(
            self.composition.connect_wizard_action_callbacks,
            self.composition.connect_workflow_action_callbacks,
        )
        self.assertEqual(assembled.shell.objectName(), "qfitWizardShell")
        self.assertEqual(assembled.shell.footer_bar.objectName(), "qfitWizardFooterBar")
        self.assertEqual(assembled.pages[0].objectName(), "qfitWizardConnectionPage")

    def test_workflow_composition_resolves_simple_wizard_aliases_lazily(self):
        module = _load_workflow_composition_module()
        alias_targets = module._WIZARD_COMPAT_ALIAS_TARGETS

        for name in alias_targets:
            with self.subTest(name=name):
                self.assertNotIn(name, module.__dict__)
                self.assertIs(getattr(module, name), getattr(module, alias_targets[name]))

    def test_lazy_wizard_alias_reports_missing_canonical_target_as_attribute_error(self):
        module = _load_workflow_composition_module()
        module._WIZARD_COMPAT_ALIAS_TARGETS["BrokenWizardAlias"] = (
            "MissingWorkflowAlias"
        )
        try:
            self.assertFalse(hasattr(module, "BrokenWizardAlias"))
            with self.assertRaisesRegex(
                AttributeError,
                "BrokenWizardAlias.*MissingWorkflowAlias",
            ):
                module.__getattr__("BrokenWizardAlias")
        finally:
            module._WIZARD_COMPAT_ALIAS_TARGETS.pop("BrokenWizardAlias", None)
            module.__dict__.pop("BrokenWizardAlias", None)

    def test_workflow_composition_star_exports_only_canonical_workflow_names(self):
        for name in (
            "DockWizardPageSpec",
            "DockWizardProgress",
            "WizardActionCallbacks",
            "WizardCompositionPage",
            "WizardPage",
            "WizardPageStateSnapshots",
            "WizardProgressFacts",
            "WizardSettingsSnapshot",
            "WizardShell",
            "WizardShellComposition",
            "WizardShellPresenter",
            "build_default_wizard_page_specs",
            "build_placeholder_wizard_shell",
            "build_wizard_page_states_from_facts",
            "connect_wizard_action_callbacks",
            "refresh_wizard_shell_composition",
        ):
            self.assertNotIn(name, self.composition.__all__)


if __name__ == "__main__":
    unittest.main()
