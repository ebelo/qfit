from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from qfit.ui.application.dock_workflow_sections import DockWizardProgress
from qfit.ui.application.wizard_page_specs import DockWizardPageSpec

from .connection_page import (
    ConnectionPageContent,
    ConnectionPageState,
    install_connection_page_content,
)
from .sync_page import SyncPageContent, SyncPageState, install_sync_page_content
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
    connection_content: ConnectionPageContent | None = None
    sync_content: SyncPageContent | None = None


def build_placeholder_wizard_shell(
    *,
    parent=None,
    footer_text: str = "",
    progress: DockWizardProgress | None = None,
    specs: Sequence[DockWizardPageSpec] | None = None,
    connection_state: ConnectionPageState | None = None,
    sync_state: SyncPageState | None = None,
) -> WizardShellComposition:
    """Build the placeholder #609 wizard shell with pages and presenter wired.

    Pages are installed before the presenter renders so the initial progress
    snapshot selects the matching visible page immediately. The helper does not
    bind any current long-scroll dock controls into the shell; page content can
    migrate later through the stable ``WizardPage.body_layout()`` seams.
    """

    shell = WizardShell(parent=parent, footer_text=footer_text)
    pages = install_wizard_pages(shell, specs=specs)
    connection_content = _install_connection_content(
        pages,
        connection_state=connection_state,
    )
    sync_content = _install_sync_content(pages, sync_state=sync_state)
    presenter = WizardShellPresenter(shell, progress)
    return WizardShellComposition(
        shell=shell,
        pages=pages,
        presenter=presenter,
        connection_content=connection_content,
        sync_content=sync_content,
    )


def _install_connection_content(
    pages: Sequence[WizardPage],
    *,
    connection_state: ConnectionPageState | None,
) -> ConnectionPageContent | None:
    for page in pages:
        if page.spec.key == "connection":
            return install_connection_page_content(page, state=connection_state)
    return None


def _install_sync_content(
    pages: Sequence[WizardPage],
    *,
    sync_state: SyncPageState | None,
) -> SyncPageContent | None:
    for page in pages:
        if page.spec.key == "sync":
            return install_sync_page_content(page, state=sync_state)
    return None


__all__ = ["WizardShellComposition", "build_placeholder_wizard_shell"]
