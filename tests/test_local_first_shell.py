import importlib
import sys
import unittest
from unittest.mock import patch

from tests import _path  # noqa: F401
from tests.test_wizard_shell import _fake_qt_modules

from qfit.ui.application.local_first_navigation import build_local_first_dock_navigation_state
from qfit.ui.application.wizard_progress import WizardProgressFacts


def _load_local_first_shell_module():
    for name in (
        "qfit.ui.dockwidget.local_first_shell",
        "qfit.ui.dockwidget.footer_status_bar",
        "qfit.ui.dockwidget",
    ):
        sys.modules.pop(name, None)
    with patch.dict(sys.modules, _fake_qt_modules()):
        return importlib.import_module("qfit.ui.dockwidget.local_first_shell")


class LocalFirstDockShellTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.shell_module = _load_local_first_shell_module()

    def test_builds_standard_qt_shell_with_full_navigation_labels(self):
        shell = self.shell_module.LocalFirstDockShell(footer_text="Ready")

        self.assertEqual(shell.objectName(), "qfitLocalFirstDockShell")
        self.assertEqual(shell.navigation_container.objectName(), "qfitLocalFirstDockNavigation")
        self.assertEqual(shell.main_container.objectName(), "qfitLocalFirstDockMain")
        self.assertEqual(shell.separator.objectName(), "qfitLocalFirstDockSeparator")
        self.assertEqual(shell.pages_stack.objectName(), "qfitLocalFirstDockPagesStack")
        self.assertEqual(shell.footer_bar.text(), "Ready")
        self.assertEqual(
            [button.text() for button in shell.navigation_buttons()],
            ["Data", "Map", "Analysis", "Atlas", "Settings"],
        )
        self.assertFalse(any("..." in button.text() for button in shell.navigation_buttons()))
        self.assertTrue(all(button.isEnabled() for button in shell.navigation_buttons()))

    def test_outer_layout_keeps_navigation_content_and_footer_separate(self):
        shell = self.shell_module.LocalFirstDockShell()

        self.assertEqual(shell.outer_layout().object_name, "qfitLocalFirstDockOuterLayout")
        self.assertEqual(shell.outer_layout().widgets, [shell.main_container, shell.footer_bar])
        self.assertEqual(
            shell.main_layout().widgets,
            [shell.navigation_container, shell.separator, shell.pages_stack],
        )

    def test_navigation_state_sets_button_metadata_without_step_locking(self):
        navigation = build_local_first_dock_navigation_state(
            WizardProgressFacts(activities_stored=True, activity_layers_loaded=True),
            preferred_current_key="map",
        )
        shell = self.shell_module.LocalFirstDockShell(navigation_state=navigation)

        data_button = shell.button_for_key("data")
        map_button = shell.button_for_key("map")
        analysis_button = shell.button_for_key("analysis")

        self.assertTrue(data_button.property("ready"))
        self.assertEqual(data_button.property("navTone"), "ready")
        self.assertTrue(map_button.property("current"))
        self.assertEqual(map_button.property("navTone"), "current")
        self.assertFalse(analysis_button.property("ready"))
        self.assertEqual(analysis_button.property("navTone"), "available")
        self.assertTrue(analysis_button.isEnabled())

    def test_navigation_state_refreshes_dynamic_qss_properties(self):
        class FakeStyle:
            def __init__(self):
                self.calls = []

            def unpolish(self, widget):
                self.calls.append(("unpolish", widget.objectName()))

            def polish(self, widget):
                self.calls.append(("polish", widget.objectName()))

        shell = self.shell_module.LocalFirstDockShell()
        button = shell.button_for_key("atlas")
        style = FakeStyle()
        updates = []
        button.style = lambda: style
        button.update = lambda: updates.append(button.objectName())

        shell.show_page_key("atlas")

        self.assertIn(("unpolish", "qfitLocalFirstDockNav_atlas"), style.calls)
        self.assertIn(("polish", "qfitLocalFirstDockNav_atlas"), style.calls)
        self.assertIn("qfitLocalFirstDockNav_atlas", updates)

    def test_unknown_navigation_key_raises_descriptive_error(self):
        shell = self.shell_module.LocalFirstDockShell()

        with self.assertRaisesRegex(
            KeyError,
            "No navigation button registered for key 'missing'",
        ):
            shell.button_for_key("missing")

    def test_clicking_navigation_button_shows_matching_page_and_emits_key(self):
        shell = self.shell_module.LocalFirstDockShell()
        calls = []
        data_page = self.shell_module.QWidget()
        atlas_page = self.shell_module.QWidget()
        shell.add_page("data", data_page)
        shell.add_page("atlas", atlas_page)
        shell.pageRequested.connect(lambda key: calls.append(key))

        shell.button_for_key("atlas").clicked.emit()

        self.assertEqual(shell.current_key(), "atlas")
        self.assertEqual(shell.pages_stack.currentIndex(), 1)
        self.assertEqual(calls, ["atlas"])
        self.assertTrue(shell.button_for_key("atlas").property("current"))
        self.assertFalse(shell.button_for_key("data").property("current"))

    def test_new_current_page_selects_installed_page(self):
        shell = self.shell_module.LocalFirstDockShell(
            navigation_state=build_local_first_dock_navigation_state(
                preferred_current_key="settings"
            )
        )
        shell.add_page("data", self.shell_module.QWidget())
        shell.add_page("settings", self.shell_module.QWidget())

        self.assertEqual(shell.pages_stack.currentIndex(), 1)


if __name__ == "__main__":
    unittest.main()
