import importlib
import sys
import unittest
from unittest.mock import patch

from tests import _path  # noqa: F401
from tests.test_wizard_shell import _fake_qt_modules


def _load_wizard_modules():
    for name in (
        "qfit.ui.dockwidget.wizard_shell_presenter",
        "qfit.ui.dockwidget.workflow_shell_presenter",
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
            importlib.import_module("qfit.ui.dockwidget.workflow_shell_presenter"),
            importlib.import_module("qfit.ui.dockwidget"),
        )


class WizardShellPresenterTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        (
            cls.wizard_page,
            cls.wizard_shell,
            cls.presenter,
            cls.workflow_presenter,
            cls.dockwidget_package,
        ) = _load_wizard_modules()

    def test_workflow_presenter_is_canonical_identity_preserving_export(self):
        self.assertIs(
            self.presenter.WorkflowShellPresenter,
            self.workflow_presenter.WorkflowShellPresenter,
        )
        self.assertIs(
            self.presenter.WizardShellPresenter,
            self.workflow_presenter.WorkflowShellPresenter,
        )
        self.assertIs(
            self.dockwidget_package.WorkflowShellPresenter,
            self.workflow_presenter.WorkflowShellPresenter,
        )
        self.assertIs(
            self.dockwidget_package.WizardShellPresenter,
            self.workflow_presenter.WorkflowShellPresenter,
        )
        self.assertIn("WorkflowShellPresenter", self.workflow_presenter.__all__)
        self.assertIn("WizardShellPresenter", self.presenter.__all__)

    def _build_shell_with_pages(self):
        shell = self.wizard_shell.WizardShell()
        self.wizard_page.install_wizard_pages(shell)
        return shell

    def test_renders_initial_progress_without_entrenching_current_dock(self):
        shell = self._build_shell_with_pages()
        persisted_step_indexes = []

        presenter = self.presenter.WizardShellPresenter(
            shell,
            on_current_step_changed=persisted_step_indexes.append,
        )

        self.assertEqual(presenter.progress.current_key, "connection")
        self.assertEqual(
            shell.stepper_bar.states(),
            ("current", "locked", "locked", "locked", "locked"),
        )
        self.assertEqual(shell.pages_stack.currentIndex(), 0)
        self.assertEqual(persisted_step_indexes, [])

    def test_rejects_locked_step_requests_without_changing_page(self):
        shell = self._build_shell_with_pages()
        persisted_step_indexes = []
        presenter = self.presenter.WizardShellPresenter(
            shell,
            on_current_step_changed=persisted_step_indexes.append,
        )

        accepted = presenter.request_step(2)

        self.assertFalse(accepted)
        self.assertEqual(presenter.progress.current_key, "connection")
        self.assertEqual(shell.pages_stack.currentIndex(), 0)
        self.assertEqual(
            shell.stepper_bar.states(),
            ("current", "locked", "locked", "locked", "locked"),
        )
        self.assertEqual(persisted_step_indexes, [])

    def test_completion_unlocks_next_page_and_stepper_signal_navigates(self):
        shell = self._build_shell_with_pages()
        persisted_step_indexes = []
        presenter = self.presenter.WizardShellPresenter(
            shell,
            on_current_step_changed=persisted_step_indexes.append,
        )

        presenter.mark_step_done("connection")
        shell.stepper_bar.stepRequested.emit(1)

        self.assertEqual(presenter.progress.current_key, "sync")
        self.assertIn("sync", presenter.progress.visited_keys)
        self.assertEqual(shell.pages_stack.currentIndex(), 1)
        self.assertEqual(
            shell.stepper_bar.states(),
            ("done", "current", "locked", "locked", "locked"),
        )
        self.assertEqual(persisted_step_indexes, [1])

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

    def test_set_progress_refreshes_stepper_and_visible_page(self):
        shell = self._build_shell_with_pages()
        persisted_step_indexes = []
        presenter = self.presenter.WizardShellPresenter(
            shell,
            on_current_step_changed=persisted_step_indexes.append,
        )
        progress = self.presenter.DockWizardProgress(
            current_key="analysis",
            completed_keys=frozenset({"connection", "sync", "map"}),
            visited_keys=frozenset({"analysis"}),
        )

        presenter.set_progress(progress)

        self.assertEqual(presenter.progress, progress)
        self.assertEqual(shell.pages_stack.currentIndex(), 3)
        self.assertEqual(
            shell.stepper_bar.states(),
            ("done", "done", "done", "current", "upcoming"),
        )
        self.assertEqual(persisted_step_indexes, [3])

    def test_step_change_callback_marks_only_requested_steps_as_user_selected(self):
        shell = self._build_shell_with_pages()
        persisted_steps = []
        presenter = self.presenter.WizardShellPresenter(
            shell,
            on_current_step_changed=(
                lambda index, *, user_selected: persisted_steps.append(
                    (index, user_selected)
                )
            ),
        )

        presenter.set_progress(
            self.presenter.DockWizardProgress(
                current_key="sync",
                completed_keys=frozenset({"connection"}),
                visited_keys=frozenset({"sync"}),
            )
        )
        presenter.request_step(0)

        self.assertEqual(persisted_steps, [(1, False), (0, True)])

    def test_step_change_callback_does_not_swallow_type_errors(self):
        shell = self._build_shell_with_pages()

        def persist_step(_index, *, user_selected):
            raise TypeError("persistence failed")

        presenter = self.presenter.WizardShellPresenter(
            shell,
            on_current_step_changed=persist_step,
        )

        with self.assertRaisesRegex(TypeError, "persistence failed"):
            presenter.set_progress(
                self.presenter.DockWizardProgress(
                    current_key="sync",
                    completed_keys=frozenset({"connection"}),
                    visited_keys=frozenset({"sync"}),
                )
            )

    def test_set_progress_rejects_unknown_keys_without_mutating_shell(self):
        shell = self._build_shell_with_pages()
        presenter = self.presenter.WizardShellPresenter(shell)

        with self.assertRaises(KeyError):
            presenter.set_progress(
                self.presenter.DockWizardProgress(
                    current_key="review",
                    completed_keys=frozenset(),
                    visited_keys=frozenset(),
                )
            )

        self.assertEqual(presenter.progress.current_key, "connection")
        self.assertEqual(shell.pages_stack.currentIndex(), 0)
        self.assertEqual(
            shell.stepper_bar.states(),
            ("current", "locked", "locked", "locked", "locked"),
        )

    def test_partial_page_mapping_renders_installed_page_stack_index(self):
        shell = self.wizard_shell.WizardShell()
        pages = self.wizard_page.install_wizard_pages(
            shell,
            specs=(
                self.wizard_page.DockWizardPageSpec(
                    key="connection",
                    title="Connection",
                    summary="Connect qfit to Strava.",
                    primary_action_hint="Primary action: configure connection",
                ),
                self.wizard_page.DockWizardPageSpec(
                    key="atlas",
                    title="Atlas PDF",
                    summary="Export a PDF atlas.",
                    primary_action_hint="Primary action: export atlas PDF",
                ),
            ),
        )
        page_indices = {page.spec.key: index for index, page in enumerate(pages)}
        presenter = self.presenter.WizardShellPresenter(
            shell,
            page_indices_by_key=page_indices,
        )

        presenter.set_progress(
            self.presenter.DockWizardProgress(
                current_key="atlas",
                completed_keys=frozenset({"connection", "sync", "map", "analysis"}),
                visited_keys=frozenset({"atlas"}),
            )
        )

        self.assertEqual(shell.pages_stack.currentIndex(), 1)
        self.assertEqual(presenter.progress.current_key, "atlas")

    def test_partial_page_mapping_rejects_uninstalled_current_step(self):
        shell = self.wizard_shell.WizardShell()
        pages = self.wizard_page.install_wizard_pages(
            shell,
            specs=(
                self.wizard_page.DockWizardPageSpec(
                    key="connection",
                    title="Connection",
                    summary="Connect qfit to Strava.",
                    primary_action_hint="Primary action: configure connection",
                ),
            ),
        )
        page_indices = {page.spec.key: index for index, page in enumerate(pages)}
        presenter = self.presenter.WizardShellPresenter(
            shell,
            page_indices_by_key=page_indices,
        )

        with self.assertRaises(ValueError):
            presenter.set_progress(self.presenter.DockWizardProgress(current_key="sync"))

        self.assertEqual(presenter.progress.current_key, "connection")
        self.assertEqual(shell.pages_stack.currentIndex(), 0)

    def test_rejects_completion_before_prerequisites_are_done(self):
        shell = self._build_shell_with_pages()
        presenter = self.presenter.WizardShellPresenter(shell)

        with self.assertRaises(ValueError):
            presenter.mark_step_done("map")

        self.assertEqual(presenter.progress.completed_keys, frozenset())
        self.assertEqual(shell.pages_stack.currentIndex(), 0)
        self.assertEqual(
            shell.stepper_bar.states(),
            ("current", "locked", "locked", "locked", "locked"),
        )

    def test_allows_completion_when_prerequisites_are_done(self):
        shell = self._build_shell_with_pages()
        presenter = self.presenter.WizardShellPresenter(shell)

        presenter.mark_step_done("connection")
        presenter.mark_step_done("sync")

        self.assertEqual(
            presenter.progress.completed_keys,
            frozenset({"connection", "sync"}),
        )
        self.assertEqual(
            shell.stepper_bar.states(),
            ("current", "done", "upcoming", "locked", "locked"),
        )

    def test_rejects_unknown_completed_step_key(self):
        shell = self._build_shell_with_pages()
        presenter = self.presenter.WizardShellPresenter(shell)

        with self.assertRaises(KeyError):
            presenter.mark_step_done("review")


if __name__ == "__main__":
    unittest.main()
