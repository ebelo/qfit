from __future__ import annotations

from qfit.ui.application.dock_workflow_sections import (
    DockWizardProgress,
    build_progress_wizard_step_statuses,
)
from qfit.ui.application.stepper_presenter import (
    build_stepper_states,
    can_request_step,
    step_index_for_key,
    step_key_for_index,
)


class WizardShellPresenter:
    """Wire wizard progress state into a :class:`WizardShell`.

    The presenter is intentionally shell-focused: it coordinates the reusable
    stepper and page stack without knowing anything about the current long-scroll
    dock controls. Completion facts can be supplied later by page-specific
    workflows as those pages migrate into the shell.
    """

    def __init__(
        self,
        shell,
        progress: DockWizardProgress | None = None,
        *,
        page_indices_by_key: dict[str, int] | None = None,
    ) -> None:
        self._shell = shell
        self._page_indices_by_key = page_indices_by_key
        self._progress = progress or DockWizardProgress()
        self._render()
        self._shell.stepper_bar.stepRequested.connect(self.request_step)

    @property
    def progress(self) -> DockWizardProgress:
        """Return the current render-neutral wizard progress snapshot."""

        return self._progress

    def set_progress(self, progress: DockWizardProgress) -> None:
        """Replace the current progress snapshot and refresh the shell."""

        # Reuse the render path for validation so invalid workflow keys fail
        # before the shell state is mutated.
        build_progress_wizard_step_statuses(progress)
        if self._page_index_for_key(progress.current_key) is None:
            raise ValueError(f"No installed wizard page for {progress.current_key!r}")
        self._progress = progress
        self._render()

    def request_step(self, index: int) -> bool:
        """Move to ``index`` when the current workflow status allows it."""

        statuses = self._statuses()
        if not can_request_step(statuses, index):
            return False
        key = step_key_for_index(index)
        if self._page_index_for_key(key) is None:
            return False
        self._progress = DockWizardProgress(
            current_key=key,
            completed_keys=self._progress.completed_keys,
            visited_keys=self._progress.visited_keys | {key},
        )
        self._render()
        return True

    def mark_step_done(self, key: str) -> None:
        """Record real workflow completion for ``key`` and refresh the shell."""

        step_index_for_key(key)
        self._progress = DockWizardProgress(
            current_key=self._progress.current_key,
            completed_keys=self._progress.completed_keys | {key},
            visited_keys=self._progress.visited_keys,
        )
        self._render()

    def _statuses(self):
        return build_progress_wizard_step_statuses(self._progress)

    def _render(self) -> None:
        statuses = self._statuses()
        self._shell.set_step_states(build_stepper_states(statuses))
        page_index = self._page_index_for_key(self._progress.current_key)
        if page_index is not None:
            self._shell.show_page(page_index)

    def _page_index_for_key(self, key: str) -> int | None:
        if self._page_indices_by_key is None:
            return step_index_for_key(key)
        return self._page_indices_by_key.get(key)


__all__ = ["WizardShellPresenter"]
