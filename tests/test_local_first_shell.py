import importlib
import sys
import unittest
from unittest.mock import patch

from tests import _path  # noqa: F401
from tests.test_wizard_shell import _fake_qt_modules

from qfit.ui.application.local_first_navigation import build_local_first_dock_navigation_state
from qfit.ui.application.wizard_progress import WizardProgressFacts
from qfit.ui.tokens import COLOR_GROUP_BORDER, COLOR_TITLE_BAR


class _FakeMouseEvent:
    def __init__(self, button, pos="inside"):
        self._button = button
        self._pos = pos

    def button(self):
        return self._button

    def pos(self):
        return self._pos


class _FakeKeyEvent:
    def __init__(self, key, *, auto_repeat=False):
        self._auto_repeat = auto_repeat
        self._key = key
        self.accepted = False

    def isAutoRepeat(self):  # noqa: N802
        return self._auto_repeat

    def key(self):
        return self._key

    def accept(self):
        self.accepted = True


class _FakeRect:
    def contains(self, pos):
        return pos == "inside"


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
            [item.text() for item in shell.navigation_items()],
            ["Data", "Map", "Analysis", "Atlas", "Settings"],
        )
        self.assertFalse(any("..." in item.text() for item in shell.navigation_items()))
        self.assertTrue(all(item.isEnabled() for item in shell.navigation_items()))
        self.assertTrue(all(item.minimumWidth() == 88 for item in shell.navigation_items()))
        self.assertTrue(
            all(
                item.focusPolicy() == self.shell_module.Qt.StrongFocus
                for item in shell.navigation_items()
            )
        )
        self.assertTrue(
            all(
                isinstance(item, self.shell_module.LocalFirstNavigationItem)
                for item in shell.navigation_items()
            )
        )

    def test_outer_layout_keeps_navigation_content_and_footer_separate(self):
        shell = self.shell_module.LocalFirstDockShell()

        self.assertEqual(shell.outer_layout().object_name, "qfitLocalFirstDockOuterLayout")
        self.assertEqual(shell.outer_layout().widgets, [shell.main_container, shell.footer_bar])
        self.assertEqual(
            shell.main_layout().widgets,
            [shell.navigation_container, shell.separator, shell.pages_stack],
        )

    def test_navigation_state_sets_selection_metadata_without_step_locking(self):
        navigation = build_local_first_dock_navigation_state(
            WizardProgressFacts(activities_stored=True, activity_layers_loaded=True),
            preferred_current_key="map",
        )
        shell = self.shell_module.LocalFirstDockShell(navigation_state=navigation)

        data_item = shell.navigation_item_for_key("data")
        map_item = shell.navigation_item_for_key("map")
        analysis_item = shell.navigation_item_for_key("analysis")

        self.assertTrue(data_item.property("ready"))
        self.assertEqual(data_item.property("navTone"), "ready")
        self.assertIn("font-weight: 500", data_item.styleSheet())
        self.assertTrue(map_item.property("current"))
        self.assertEqual(map_item.property("navTone"), "current")
        self.assertIn("font-weight: 700", map_item.styleSheet())
        self.assertTrue(map_item.isChecked())
        self.assertFalse(data_item.isChecked())
        self.assertIn(f"background-color: {COLOR_TITLE_BAR}", map_item.styleSheet())
        self.assertIn("border: none", map_item.styleSheet())
        self.assertIn(
            "#qfitLocalFirstDockNav_map[navTone='current']:hover:enabled "
            f"{{ background-color: {COLOR_GROUP_BORDER}",
            map_item.styleSheet(),
        )
        self.assertNotIn("QWidget {", map_item.styleSheet())
        self.assertNotIn("QToolButton", map_item.styleSheet())
        self.assertNotIn("background: #589632", map_item.styleSheet())
        self.assertFalse(analysis_item.property("ready"))
        self.assertEqual(analysis_item.property("navTone"), "available")
        self.assertTrue(analysis_item.isEnabled())

    def test_navigation_state_refreshes_dynamic_qss_properties(self):
        class FakeStyle:
            def __init__(self):
                self.calls = []

            def unpolish(self, widget):
                self.calls.append(("unpolish", widget.objectName()))

            def polish(self, widget):
                self.calls.append(("polish", widget.objectName()))

        shell = self.shell_module.LocalFirstDockShell()
        button = shell.navigation_item_for_key("atlas")
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
            "No navigation item registered for key 'missing'",
        ):
            shell.navigation_item_for_key("missing")

    def test_navigation_item_mouse_activation_matches_button_safety(self):
        item = self.shell_module.LocalFirstNavigationItem()
        item.rect = lambda: _FakeRect()
        calls = []
        item.clicked.connect(lambda: calls.append("clicked"))

        item.mousePressEvent(_FakeMouseEvent(self.shell_module.Qt.LeftButton))
        item.mouseReleaseEvent(_FakeMouseEvent(self.shell_module.Qt.LeftButton, pos="outside"))
        item.mousePressEvent(_FakeMouseEvent(button=999))
        item.mouseReleaseEvent(_FakeMouseEvent(button=999))

        self.assertEqual(calls, [])

        item.mousePressEvent(_FakeMouseEvent(self.shell_module.Qt.LeftButton))
        item.mouseReleaseEvent(_FakeMouseEvent(self.shell_module.Qt.LeftButton))

        self.assertEqual(calls, ["clicked"])

    def test_navigation_item_keyboard_activation_preserves_accessibility(self):
        item = self.shell_module.LocalFirstNavigationItem()
        calls = []
        item.clicked.connect(lambda: calls.append("clicked"))

        return_press = _FakeKeyEvent(self.shell_module.Qt.Key_Return)
        return_release = _FakeKeyEvent(self.shell_module.Qt.Key_Return)
        item.keyPressEvent(return_press)
        item.keyPressEvent(_FakeKeyEvent(self.shell_module.Qt.Key_Return, auto_repeat=True))
        item.keyReleaseEvent(_FakeKeyEvent(self.shell_module.Qt.Key_Return, auto_repeat=True))
        item.keyReleaseEvent(return_release)
        item.keyPressEvent(_FakeKeyEvent(key=999))

        self.assertEqual(calls, ["clicked"])
        self.assertTrue(return_press.accepted)
        self.assertTrue(return_release.accepted)

    def test_clicking_navigation_item_shows_matching_page_and_emits_key(self):
        shell = self.shell_module.LocalFirstDockShell()
        calls = []
        data_page = self.shell_module.QWidget()
        atlas_page = self.shell_module.QWidget()
        shell.add_page("data", data_page)
        shell.add_page("atlas", atlas_page)
        shell.pageRequested.connect(lambda key: calls.append(key))

        shell.navigation_item_for_key("atlas").clicked.emit()

        self.assertEqual(shell.current_key(), "atlas")
        self.assertEqual(shell.pages_stack.currentIndex(), 1)
        self.assertEqual(calls, ["atlas"])
        self.assertTrue(shell.navigation_item_for_key("atlas").property("current"))
        self.assertFalse(shell.navigation_item_for_key("data").property("current"))

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
