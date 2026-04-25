import importlib
import sys
import unittest
from unittest.mock import patch

from tests import _path  # noqa: F401
from tests.test_wizard_shell import _fake_qt_modules


def _load_wizard_modules():
    for name in (
        "qfit.ui.dockwidget.wizard_shell_presenter",
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
            importlib.import_module("qfit.ui.dockwidget.wizard_shell_presenter"),
        )


class WizardShellPresenterTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.wizard_page, cls.wizard_shell, cls.presenter = _load_wizard_modules()

    def _build_shell_with_pages(self):
        shell = self.wizard_shell.WizardShell()
        self.wizard_page.install_wizard_pages(shell)
        return shell

    def test_renders_initial_progress_without_entrenching_current_dock(self):
        shell = self._build_shell_with_pages()

        presenter = self.presenter.WizardShellPresenter(shell)

        self.assertEqual(presenter.progress.current_key, "connection")
        self.assertEqual(
            shell.stepper_bar.states(),
            ("current", "locked", "locked", "locked", "locked"),
        )
        self.assertEqual(shell.pages_stack.currentIndex(), 0)

    def test_rejects_locked_step_requests_without_changing_page(self):
        shell = self._build_shell_with_pages()
        presenter = self.presenter.WizardShellPresenter(shell)

        accepted = presenter.request_step(2)

        self.assertFalse(accepted)
        self.assertEqual(presenter.progress.current_key, "connection")
        self.assertEqual(shell.pages_stack.currentIndex(), 0)
        self.assertEqual(
            shell.stepper_bar.states(),
            ("current", "locked", "locked", "locked", "locked"),
        )

    def test_completion_unlocks_next_page_and_stepper_signal_navigates(self):
        shell = self._build_shell_with_pages()
        presenter = self.presenter.WizardShellPresenter(shell)

        presenter.mark_step_done("connection")
        shell.stepper_bar.stepRequested.emit(1)

        self.assertEqual(presenter.progress.current_key, "sync")
        self.assertIn("sync", presenter.progress.visited_keys)
        self.assertEqual(shell.pages_stack.currentIndex(), 1)
        self.assertEqual(
            shell.stepper_bar.states(),
            ("done", "current", "locked", "locked", "locked"),
        )

    def test_visited_uncompleted_pages_stay_unlocked_without_being_done(self):
        shell = self._build_shell_with_pages()
        presenter = self.presenter.WizardShellPresenter(shell)

        presenter.mark_step_done("connection")
        self.assertTrue(presenter.request_step(1))
        self.assertTrue(presenter.request_step(0))

        self.assertEqual(presenter.progress.current_key, "connection")
        self.assertIn("sync", presenter.progress.visited_keys)
        self.assertEqual(shell.pages_stack.currentIndex(), 0)
        self.assertEqual(
            shell.stepper_bar.states(),
            ("current", "upcoming", "locked", "locked", "locked"),
        )

    def test_rejects_unknown_completed_step_key(self):
        shell = self._build_shell_with_pages()
        presenter = self.presenter.WizardShellPresenter(shell)

        with self.assertRaises(KeyError):
            presenter.mark_step_done("review")


if __name__ == "__main__":
    unittest.main()
