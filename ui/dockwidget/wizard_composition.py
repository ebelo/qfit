from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from qfit.ui.application.dock_workflow_sections import DockWizardProgress
from qfit.ui.application.wizard_page_specs import DockWizardPageSpec

from .wizard_page import WizardPage, install_wizard_pages
from .wizard_shell import WizardShell
from .wizard_shell_presenter import WizardShellPresenter


@dataclass(frozen=True)
class WizardShellComposition:
    """Concrete placeholder wizard assembly for the future dock replacement.

    The composition keeps the shell, page placeholders, and presenter wiring in
    one reusable unit without replacing the current production dock yet. That
    gives #609 a safe integration seam for the eventual dock swap while keeping
    this slice focused on wizard-forward UI structure.
    """

    shell: WizardShell
    pages: tuple[WizardPage, ...]
    presenter: WizardShellPresenter


def build_placeholder_wizard_shell(
    *,
    parent=None,
    footer_text: str = "",
    progress: DockWizardProgress | None = None,
    specs: Sequence[DockWizardPageSpec] | None = None,
) -> WizardShellComposition:
    """Build the placeholder #609 wizard shell with pages and presenter wired.

    Pages are installed before the presenter renders so the initial progress
    snapshot selects the matching visible page immediately. The helper does not
    bind any current long-scroll dock controls into the shell; page content can
    migrate later through the stable ``WizardPage.body_layout()`` seams.
    """

    shell = WizardShell(parent=parent, footer_text=footer_text)
    pages = install_wizard_pages(shell, specs=specs)
    presenter = WizardShellPresenter(shell, progress)
    return WizardShellComposition(shell=shell, pages=pages, presenter=presenter)


__all__ = ["WizardShellComposition", "build_placeholder_wizard_shell"]
