import importlib
import sys
import unittest
from unittest.mock import patch

from tests import _path  # noqa: F401
from tests.test_wizard_shell import _fake_qt_modules


def _load_action_row_module():
    for name in (
        "qfit.ui.dockwidget.action_row",
        "qfit.ui.dockwidget",
    ):
        sys.modules.pop(name, None)
    with patch.dict(sys.modules, _fake_qt_modules()):
        return importlib.import_module("qfit.ui.dockwidget.action_row")


class WizardActionRowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.action_row = _load_action_row_module()

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

    def test_primary_action_button_gets_cta_role_and_chrome(self):
        button = self.action_row.QToolButton()

        returned = self.action_row.style_primary_action_button(
            button,
            action_name="sync_activities",
        )

        self.assertIs(returned, button)
        self.assertEqual(button.property("primaryAction"), "sync_activities")
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
        self.assertEqual(button.property("wizardActionRole"), "secondary")
        self.assertIn("font-weight: 500", button.styleSheet())
        self.assertIsNotNone(button.cursor().shape())

    def test_action_availability_marks_blocked_and_available_buttons(self):
        button = self.action_row.QToolButton()

        returned = self.action_row.set_wizard_action_availability(
            button,
            enabled=False,
            tooltip="Load activity layers first.",
        )

        self.assertIs(returned, button)
        self.assertFalse(button.isEnabled())
        self.assertEqual(button.property("wizardActionAvailability"), "blocked")
        self.assertEqual(button.toolTip(), "Load activity layers first.")

        self.action_row.set_wizard_action_availability(button, enabled=True)

        self.assertTrue(button.isEnabled())
        self.assertEqual(button.property("wizardActionAvailability"), "available")
        self.assertEqual(button.toolTip(), "")


if __name__ == "__main__":
    unittest.main()
