import importlib
import sys
import unittest
from unittest.mock import patch

from tests import _path  # noqa: F401
from tests.test_wizard_shell import _fake_qt_modules


_ACTION_ROW_MODULES = (
    "qfit.ui.dockwidget.wizard_action_row",
    "qfit.ui.dockwidget.action_row",
    "qfit.ui.dockwidget",
)


def _clear_action_row_modules():
    for name in _ACTION_ROW_MODULES:
        sys.modules.pop(name, None)


def _load_action_row_module():
    _clear_action_row_modules()
    with patch.dict(sys.modules, _fake_qt_modules()):
        return importlib.import_module("qfit.ui.dockwidget.action_row")


def _load_action_row_modules():
    _clear_action_row_modules()
    with patch.dict(sys.modules, _fake_qt_modules()):
        return (
            importlib.import_module("qfit.ui.dockwidget.action_row"),
            importlib.import_module("qfit.ui.dockwidget.wizard_action_row"),
        )


class _FakeSize:
    def __init__(self, width):
        self._width = width

    def width(self):
        return self._width


class _FakeResizeEvent:
    def __init__(self, width):
        self._size = _FakeSize(width)

    def size(self):
        return self._size


class WizardActionRowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.action_row, cls.wizard_action_row = _load_action_row_modules()

    def test_workflow_names_are_canonical_exports_with_direct_wizard_aliases(self):
        button = self.action_row.QToolButton()

        row = self.action_row.build_workflow_action_row(button)

        self.assertIs(self.action_row.WizardActionRow, self.action_row.WorkflowActionRow)
        self.assertIs(
            self.action_row.build_wizard_action_row,
            self.action_row.build_workflow_action_row,
        )
        self.assertIs(
            self.action_row.set_wizard_action_availability,
            self.action_row.set_workflow_action_availability,
        )
        self.assertIs(
            self.action_row.set_wizard_action_role,
            self.action_row.set_workflow_action_role,
        )
        self.assertIsInstance(row, self.action_row.WorkflowActionRow)
        self.assertEqual(row.objectName(), "qfitWizardActionRow")

    def test_action_row_star_exports_only_workflow_names(self):
        for name in (
            "WizardActionRow",
            "build_wizard_action_row",
            "set_wizard_action_availability",
            "set_wizard_action_role",
        ):
            self.assertNotIn(name, self.action_row.__all__)

    def test_action_row_resolves_wizard_aliases_lazily(self):
        module = _load_action_row_module()
        alias_targets = module._WIZARD_COMPAT_ALIAS_TARGETS

        for name in alias_targets:
            with self.subTest(name=name):
                self.assertNotIn(name, module.__dict__)
                self.assertIs(getattr(module, name), getattr(module, alias_targets[name]))

    def test_lazy_wizard_alias_reports_missing_canonical_target_as_attribute_error(self):
        module = _load_action_row_module()
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

    def test_wizard_action_row_module_exports_compatibility_aliases(self):
        self.assertIs(
            self.wizard_action_row.WizardActionRow,
            self.action_row.WorkflowActionRow,
        )
        self.assertIs(
            self.wizard_action_row.build_wizard_action_row,
            self.action_row.build_workflow_action_row,
        )
        self.assertIs(
            self.wizard_action_row.set_wizard_action_availability,
            self.action_row.set_workflow_action_availability,
        )
        self.assertIs(
            self.wizard_action_row.set_wizard_action_role,
            self.action_row.set_workflow_action_role,
        )
        self.assertEqual(
            self.wizard_action_row.__all__,
            [
                "WizardActionRow",
                "build_wizard_action_row",
                "set_wizard_action_availability",
                "set_wizard_action_role",
            ],
        )

    def test_builds_scoped_row_with_supplied_buttons(self):
        primary = self.action_row.QToolButton()
        secondary = self.action_row.QToolButton()

        row = self.action_row.build_wizard_action_row(
            secondary,
            primary,
            object_name="qfitWizardMapActionRow",
        )

        self.assertEqual(row.objectName(), "qfitWizardMapActionRow")
        self.assertEqual(row.outer_layout().object_name, "qfitWizardActionRowLayout")
        self.assertEqual(row.outer_layout().contents_margins, (0, 4, 0, 0))
        self.assertEqual(row.outer_layout().spacing, 8)
        self.assertEqual(row.outer_layout().widgets, [secondary, primary])
        self.assertEqual(primary.minimumWidth(), 0)
        self.assertEqual(secondary.minimumWidth(), 0)

    def test_action_row_stacks_buttons_when_dock_is_narrow(self):
        primary = self.action_row.QToolButton()
        secondary = self.action_row.QToolButton()
        row = self.action_row.build_wizard_action_row(secondary, primary)

        row.set_responsive_width(320)

        self.assertEqual(row.property("responsiveMode"), "narrow")
        self.assertEqual(row.outer_layout().direction, self.action_row.QBoxLayout.TopToBottom)
        self.assertEqual(row.outer_layout().spacing, 6)

        row.set_responsive_width(600)

        self.assertEqual(row.property("responsiveMode"), "wide")
        self.assertEqual(row.outer_layout().direction, self.action_row.QBoxLayout.LeftToRight)
        self.assertEqual(row.outer_layout().spacing, 8)

    def test_resize_event_drives_narrow_action_row_mode(self):
        row = self.action_row.build_wizard_action_row(self.action_row.QToolButton())

        row.resizeEvent(_FakeResizeEvent(320))

        self.assertEqual(row.property("responsiveMode"), "narrow")
        self.assertEqual(row.outer_layout().direction, self.action_row.QBoxLayout.TopToBottom)

    def test_primary_action_button_gets_cta_role_and_chrome(self):
        button = self.action_row.QToolButton()

        returned = self.action_row.style_primary_action_button(
            button,
            action_name="sync_activities",
        )

        self.assertIs(returned, button)
        self.assertEqual(button.property("primaryAction"), "sync_activities")
        self.assertEqual(button.property("workflowActionRole"), "primary")
        self.assertEqual(button.property("wizardActionRole"), "primary")
        self.assertIn("font-weight: 700", button.styleSheet())
        self.assertIn("QToolButton:disabled", button.styleSheet())
        self.assertIsNotNone(button.cursor().shape())

    def test_secondary_action_button_gets_secondary_role_and_chrome(self):
        button = self.action_row.QToolButton()

        returned = self.action_row.style_secondary_action_button(
            button,
            action_name="load_activity_layers",
        )

        self.assertIs(returned, button)
        self.assertEqual(button.property("secondaryAction"), "load_activity_layers")
        self.assertEqual(button.property("workflowActionRole"), "secondary")
        self.assertEqual(button.property("wizardActionRole"), "secondary")
        self.assertEqual(button.styleSheet(), "")
        self.assertIsNotNone(button.cursor().shape())

    def test_destructive_action_button_gets_danger_role_and_chrome(self):
        button = self.action_row.QToolButton()

        returned = self.action_row.style_destructive_action_button(
            button,
            action_name="clear_database",
        )

        self.assertIs(returned, button)
        self.assertEqual(button.property("destructiveAction"), "clear_database")
        self.assertEqual(button.property("workflowActionRole"), "destructive")
        self.assertEqual(button.property("wizardActionRole"), "destructive")
        self.assertIn("#c01c28", button.styleSheet())
        self.assertNotIn("#589632", button.styleSheet())
        self.assertIsNotNone(button.cursor().shape())

    def test_unknown_action_role_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Unknown workflow action button role"):
            self.action_row._button_stylesheet(role="primray")

    def test_action_availability_marks_blocked_and_available_buttons(self):
        button = self.action_row.QToolButton()

        returned = self.action_row.set_wizard_action_availability(
            button,
            enabled=False,
            tooltip="Load activity layers first.",
        )

        self.assertIs(returned, button)
        self.assertFalse(button.isEnabled())
        self.assertEqual(button.property("workflowActionAvailability"), "blocked")
        self.assertEqual(button.property("wizardActionAvailability"), "blocked")
        self.assertEqual(button.toolTip(), "Load activity layers first.")

        self.action_row.set_wizard_action_availability(button, enabled=True)

        self.assertTrue(button.isEnabled())
        self.assertEqual(button.property("workflowActionAvailability"), "available")
        self.assertEqual(button.property("wizardActionAvailability"), "available")
        self.assertEqual(button.toolTip(), "")


if __name__ == "__main__":
    unittest.main()
