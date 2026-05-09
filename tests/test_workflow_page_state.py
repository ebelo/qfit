import importlib
import sys
import unittest
from unittest.mock import patch

from tests import _path  # noqa: F401
from tests.test_wizard_shell import _fake_qt_modules


def _load_workflow_page_state_module():
    for name in (
        "qfit.ui.dockwidget.workflow_page_state",
        "qfit.ui.dockwidget.analysis_page",
        "qfit.ui.dockwidget.atlas_page",
        "qfit.ui.dockwidget.connection_page",
        "qfit.ui.dockwidget.map_page",
        "qfit.ui.dockwidget.sync_page",
        "qfit.ui.dockwidget.action_row",
        "qfit.ui.dockwidget",
    ):
        sys.modules.pop(name, None)
    with patch.dict(sys.modules, _fake_qt_modules()):
        return importlib.import_module("qfit.ui.dockwidget.workflow_page_state")


class WorkflowPageStatePublicNamesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = _load_workflow_page_state_module()

    def test_exports_canonical_workflow_names(self):
        self.assertIn("DockWorkflowActionCallbacks", self.module.__all__)
        self.assertIn("WorkflowPageStateSnapshots", self.module.__all__)
        self.assertIn("build_workflow_page_states_from_facts", self.module.__all__)

    def test_keeps_wizard_names_as_identity_preserving_compatibility_aliases(self):
        self.assertIs(
            self.module.WizardActionCallbacks,
            self.module.DockWorkflowActionCallbacks,
        )
        self.assertIs(
            self.module.WizardPageStateSnapshots,
            self.module.WorkflowPageStateSnapshots,
        )
        self.assertIs(
            self.module.build_wizard_page_states_from_facts,
            self.module.build_workflow_page_states_from_facts,
        )
        self.assertIn("WizardActionCallbacks", self.module.__all__)
        self.assertIn("WizardPageStateSnapshots", self.module.__all__)
        self.assertIn("build_wizard_page_states_from_facts", self.module.__all__)


if __name__ == "__main__":
    unittest.main()
