from __future__ import annotations

from collections.abc import Callable
from inspect import Parameter, signature

from qfit.ui.application.dock_workflow_sections import (
    DockWorkflowProgress,
    build_progress_workflow_step_statuses,
)
from qfit.ui.application.stepper_presenter import (
    build_stepper_states,
    can_request_step,
    step_index_for_key,
    step_key_for_index,
)


class WorkflowShellPresenter:
    """Wire workflow progress state into a dock shell.

    The presenter is intentionally shell-focused: it coordinates the reusable
    stepper and page stack without knowing anything about the current long-scroll
    dock controls. Completion facts can be supplied later by page-specific
    workflows as those pages migrate into the shell.
    """

    def __init__(
        self,
        shell,
        progress: DockWorkflowProgress | None = None,
        *,
        page_indices_by_key: dict[str, int] | None = None,
        on_current_step_changed: Callable[..., None] | None = None,
    ) -> None:
        self._shell = shell
        self._page_indices_by_key = page_indices_by_key
        self._on_current_step_changed = on_current_step_changed
        self._progress = progress or DockWorkflowProgress()
        self._render()
        self._shell.stepper_bar.stepRequested.connect(self.request_step)

    @property
    def progress(self) -> DockWorkflowProgress:
        """Return the current render-neutral workflow progress snapshot."""

        return self._progress

    def set_progress(self, progress: DockWorkflowProgress) -> None:
        """Replace the current progress snapshot and refresh the shell.

        The optional step-change callback is notified only when the current
        workflow key changes. This gives the future dock a small persistence seam
        for ``ui/last_step_index`` without writing settings during initial
        presenter construction.
        """

        # Reuse the render path for validation so invalid workflow keys fail
        # before the shell state is mutated.
        build_progress_workflow_step_statuses(progress)
        if self._page_index_for_key(progress.current_key) is None:
            raise ValueError(f"No installed workflow page for {progress.current_key!r}")
        previous_key = self._progress.current_key
        self._progress = progress
        self._render()
        self._notify_current_step_changed(
            previous_key=previous_key,
            user_selected=False,
        )

    def request_step(self, index: int) -> bool:
        """Move to ``index`` when the current workflow status allows it."""

        statuses = self._statuses()
        if not can_request_step(statuses, index):
            return False
        key = step_key_for_index(index)
        if self._page_index_for_key(key) is None:
            return False
        previous_key = self._progress.current_key
        self._progress = DockWorkflowProgress(
            current_key=key,
            completed_keys=self._progress.completed_keys,
            visited_keys=self._progress.visited_keys | {key},
        )
        self._render()
        self._notify_current_step_changed(
            previous_key=previous_key,
            user_selected=True,
        )
        return True

    def mark_step_done(self, key: str) -> None:
        """Record real workflow completion for ``key`` and refresh the shell.

        Completion remains prerequisite-aware: downstream milestones cannot be
        marked done until every earlier workflow step has actually completed.
        """

        missing_prerequisites = _missing_completion_prerequisites(
            key,
            completed_keys=self._progress.completed_keys,
        )
        if missing_prerequisites:
            missing = ", ".join(missing_prerequisites)
            raise ValueError(f"Cannot mark {key!r} done before {missing}")
        self._progress = DockWorkflowProgress(
            current_key=self._progress.current_key,
            completed_keys=self._progress.completed_keys | {key},
            visited_keys=self._progress.visited_keys,
        )
        self._render()

    def _statuses(self):
        return build_progress_workflow_step_statuses(self._progress)

    def _render(self) -> None:
        statuses = self._statuses()
        self._shell.set_step_states(build_stepper_states(statuses))
        page_index = self._page_index_for_key(self._progress.current_key)
        if page_index is not None:
            self._shell.show_page(page_index)

    def _notify_current_step_changed(
        self,
        *,
        previous_key: str,
        user_selected: bool,
    ) -> None:
        if self._on_current_step_changed is None:
            return
        current_key = self._progress.current_key
        if current_key == previous_key:
            return
        step_index = step_index_for_key(current_key)
        if _accepts_user_selected_keyword(self._on_current_step_changed):
            self._on_current_step_changed(
                step_index,
                user_selected=user_selected,
            )
            return
        self._on_current_step_changed(step_index)

    def _page_index_for_key(self, key: str) -> int | None:
        if self._page_indices_by_key is None:
            return step_index_for_key(key)
        return self._page_indices_by_key.get(key)


def _accepts_user_selected_keyword(callback: Callable[..., None]) -> bool:
    try:
        callback_signature = signature(callback)
    except (TypeError, ValueError):
        return False
    return any(
        parameter.kind is Parameter.VAR_KEYWORD
        or (
            parameter.name == "user_selected"
            and parameter.kind
            in (Parameter.KEYWORD_ONLY, Parameter.POSITIONAL_OR_KEYWORD)
        )
        for parameter in callback_signature.parameters.values()
    )


def _missing_completion_prerequisites(
    key: str,
    *,
    completed_keys: frozenset[str],
) -> tuple[str, ...]:
    target_index = step_index_for_key(key)
    prerequisite_keys = tuple(
        step_key_for_index(index) for index in range(target_index)
    )
    return tuple(
        prerequisite_key
        for prerequisite_key in prerequisite_keys
        if prerequisite_key not in completed_keys
    )


DockWizardProgress = DockWorkflowProgress
"""Compatibility alias for pre-#805 wizard shell presenter tests/callers."""

__all__ = [
    "DockWorkflowProgress",
    "DockWizardProgress",
    "WorkflowShellPresenter",
]
