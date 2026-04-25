from __future__ import annotations

from collections.abc import Sequence

from qfit.ui.application.wizard_page_specs import (
    DockWizardPageSpec,
    build_default_wizard_page_specs,
)

from ._qt_compat import import_qt_module

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


class WizardPage(QWidget):
    """Reusable visible page container for the #609 wizard shell.

    The container supplies stable chrome for the future wizard pages while
    leaving real page controls to later focused slices. It is deliberately not
    wired into the current dock yet, so it remains compatible with the shell
    structure without locking in the old scroll layout.
    """

    def __init__(self, spec: DockWizardPageSpec, parent=None) -> None:
        super().__init__(parent)
        self.spec = spec
        self.setObjectName(spec.page_object_name)
        self.title_label = self._build_label(spec.title, spec.title_object_name)
        self.summary_label = self._build_label(spec.summary, spec.summary_object_name)
        self.body_container = self._build_body_container()
        self.primary_hint_label = self._build_label(
            spec.primary_action_hint,
            spec.primary_hint_object_name,
        )
        self._layout = self._build_layout()

    def body_layout(self):
        """Expose the empty content layout for future page-specific controls."""

        return self._body_layout

    def outer_layout(self):
        """Expose the page layout for adapter wiring and pure tests."""

        return self._layout

    def _build_label(self, text: str, object_name: str):
        label = QLabel(text, self)
        label.setObjectName(object_name)
        if hasattr(label, "setWordWrap"):
            label.setWordWrap(True)
        return label

    def _build_body_container(self):
        body = QWidget(self)
        body.setObjectName(self.spec.body_object_name)
        self._body_layout = QVBoxLayout(body)
        self._body_layout.setContentsMargins(0, 0, 0, 0)
        self._body_layout.setSpacing(8)
        return body

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


def build_wizard_pages(
    *,
    parent=None,
    specs: Sequence[DockWizardPageSpec] | None = None,
) -> tuple[WizardPage, ...]:
    """Build visible wizard page containers from render-neutral specs."""

    page_specs = build_default_wizard_page_specs() if specs is None else tuple(specs)
    return tuple(WizardPage(spec, parent) for spec in page_specs)


def install_wizard_pages(shell, specs: Sequence[DockWizardPageSpec] | None = None) -> tuple[WizardPage, ...]:
    """Create default wizard pages and append them to a :class:`WizardShell`."""

    pages = build_wizard_pages(parent=shell, specs=specs)
    for page in pages:
        shell.add_page(page)
    return pages


__all__ = ["WizardPage", "build_wizard_pages", "install_wizard_pages"]
