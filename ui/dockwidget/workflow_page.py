from __future__ import annotations

from collections.abc import Sequence

from qfit.ui.application.workflow_page_specs import (
    DockWorkflowPageSpec,
    build_default_workflow_page_specs,
)
from qfit.ui.tokens import COLOR_MUTED, COLOR_TEXT

from ._qt_compat import import_qt_module
from .page_content_style import configure_fluid_text_label

_qtwidgets = import_qt_module(
    "qgis.PyQt.QtWidgets",
    "PyQt5.QtWidgets",
    (
        "QLabel",
        "QVBoxLayout",
        "QWidget",
    ),
)

QLabel = _qtwidgets.QLabel
QVBoxLayout = _qtwidgets.QVBoxLayout
QWidget = _qtwidgets.QWidget

_TITLE_LABEL_QSS = (
    "QLabel { "
    f"color: {COLOR_TEXT}; "
    "font-size: 15px; "
    "font-weight: 700; "
    "}"
)
_SUMMARY_LABEL_QSS = f"QLabel {{ color: {COLOR_MUTED}; }}"
_PRIMARY_HINT_LABEL_QSS = f"QLabel {{ color: {COLOR_MUTED}; }}"


DockWizardPageSpec = DockWorkflowPageSpec
"""Compatibility alias for pre-#805 wizard page callers."""
build_default_wizard_page_specs = build_default_workflow_page_specs
"""Compatibility alias for pre-#805 wizard page builders."""


class WorkflowPage(QWidget):
    """Reusable visible page container for the workflow shell.

    The container supplies stable chrome for the workflow pages while leaving
    real page controls to focused slices. It preserves the stable
    ``qfitWizard*`` object names used by QSS and existing tests.
    """

    def __init__(self, spec: DockWorkflowPageSpec, parent=None) -> None:
        super().__init__(parent)
        self.spec = spec
        self.setObjectName(spec.page_object_name)
        self.title_label = self._build_label(
            spec.title,
            spec.title_object_name,
            style=_TITLE_LABEL_QSS,
        )
        self.summary_label = self._build_label(
            spec.summary,
            spec.summary_object_name,
            style=_SUMMARY_LABEL_QSS,
        )
        self.body_container, self._body_layout = self._build_body_container()
        self.primary_hint_label = self._build_label(
            spec.primary_action_hint,
            spec.primary_hint_object_name,
            style=_PRIMARY_HINT_LABEL_QSS,
        )
        self._layout = self._build_layout()

    def body_layout(self):
        """Expose the empty content layout for future page-specific controls."""

        return self._body_layout

    def retire_primary_action_hint(self) -> None:
        """Hide placeholder CTA copy once concrete page actions are installed.

        The first wizard slices used a textual primary-action hint as a safe
        placeholder. Once a page owns real action buttons, keeping that hint
        visible competes with the single primary CTA and adds the textual noise
        called out in #608.
        """

        self.primary_hint_label.setText("")
        self.primary_hint_label.setProperty("wizardPlaceholderHint", "retired")
        self.primary_hint_label.setVisible(False)

    def outer_layout(self):
        """Expose the page layout for adapter wiring and pure tests."""

        return self._layout

    def _build_label(self, text: str, object_name: str, *, style: str = ""):
        label = QLabel(text, self)
        label.setObjectName(object_name)
        configure_fluid_text_label(label)
        if style:
            label.setStyleSheet(style)
        return label

    def _build_body_container(self):
        body = QWidget(self)
        body.setObjectName(self.spec.body_object_name)
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(8)
        return body, body_layout

    def _build_layout(self):
        layout = QVBoxLayout(self)
        if hasattr(layout, "setObjectName"):
            layout.setObjectName(f"{self.spec.page_object_name}Layout")
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        layout.addWidget(self.title_label)
        layout.addWidget(self.summary_label)
        layout.addWidget(self.body_container)
        layout.addWidget(self.primary_hint_label)
        return layout


WizardPage = WorkflowPage
"""Compatibility alias for pre-#805 wizard page callers."""


def build_workflow_pages(
    *,
    parent=None,
    specs: Sequence[DockWorkflowPageSpec] | None = None,
) -> tuple[WorkflowPage, ...]:
    """Build visible workflow page containers from render-neutral specs."""

    page_specs = build_default_workflow_page_specs() if specs is None else tuple(specs)
    return tuple(WorkflowPage(spec, parent) for spec in page_specs)


build_wizard_pages = build_workflow_pages
"""Compatibility alias for pre-#805 wizard page callers."""


def install_workflow_pages(
    shell,
    specs: Sequence[DockWorkflowPageSpec] | None = None,
) -> tuple[WorkflowPage, ...]:
    """Create default workflow pages and append them to a shell."""

    pages = build_workflow_pages(parent=shell, specs=specs)
    for page in pages:
        shell.add_page(page)
    return pages


install_wizard_pages = install_workflow_pages
"""Compatibility alias for pre-#805 wizard page callers."""


__all__ = [
    "DockWorkflowPageSpec",
    "DockWizardPageSpec",
    "WorkflowPage",
    "WizardPage",
    "build_default_workflow_page_specs",
    "build_default_wizard_page_specs",
    "build_workflow_pages",
    "build_wizard_pages",
    "install_workflow_pages",
    "install_wizard_pages",
]
