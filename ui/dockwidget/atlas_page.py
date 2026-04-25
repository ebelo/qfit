from __future__ import annotations

from dataclasses import dataclass

from qfit.ui.tokens import COLOR_ACCENT, COLOR_MUTED, COLOR_WARN

from ._qt_compat import import_qt_module
from .action_row import (
    build_wizard_action_row,
    set_wizard_action_availability,
    style_primary_action_button,
)

_qtcore = import_qt_module("qgis.PyQt.QtCore", "PyQt5.QtCore", ("pyqtSignal",))
_qtwidgets = import_qt_module(
    "qgis.PyQt.QtWidgets",
    "PyQt5.QtWidgets",
    (
        "QLabel",
        "QToolButton",
        "QVBoxLayout",
        "QWidget",
    ),
)

pyqtSignal = _qtcore.pyqtSignal
QLabel = _qtwidgets.QLabel
QToolButton = _qtwidgets.QToolButton
QVBoxLayout = _qtwidgets.QVBoxLayout
QWidget = _qtwidgets.QWidget


@dataclass(frozen=True)
class AtlasPageState:
    """Render facts for the #609 atlas-export wizard page."""

    ready: bool = False
    status_text: str = "Atlas PDF not exported yet"
    detail_text: str = "Configure PDF title, subtitle, page size, and export destination."
    input_summary_text: str = "No atlas layer selected for export"
    output_summary_text: str = "PDF output path will be chosen before generation"
    primary_action_label: str = "Export atlas PDF"
    primary_action_enabled: bool | None = None
    primary_action_blocked_tooltip: str = "Select atlas inputs before exporting PDF."


class AtlasPageContent(QWidget):
    """Reusable fifth-page content for the wizard atlas-export step."""

    exportAtlasRequested = pyqtSignal()

    def __init__(self, state: AtlasPageState | None = None, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("qfitWizardAtlasPageContent")
        self.status_label = QLabel("", self)
        self.status_label.setObjectName("qfitWizardAtlasStatus")
        self.detail_label = QLabel("", self)
        self.detail_label.setObjectName("qfitWizardAtlasDetail")
        if hasattr(self.detail_label, "setWordWrap"):
            self.detail_label.setWordWrap(True)
        self.input_summary_label = QLabel("", self)
        self.input_summary_label.setObjectName("qfitWizardAtlasInputSummary")
        self.output_summary_label = QLabel("", self)
        self.output_summary_label.setObjectName("qfitWizardAtlasOutputSummary")
        self.export_atlas_button = QToolButton(self)
        self.export_atlas_button.setObjectName("qfitWizardAtlasExportButton")
        style_primary_action_button(
            self.export_atlas_button,
            action_name="export_atlas_pdf",
        )
        self.export_atlas_button.clicked.connect(self.exportAtlasRequested.emit)
        self.action_row = build_wizard_action_row(
            self.export_atlas_button,
            parent=self,
            object_name="qfitWizardAtlasActionRow",
        )
        self._layout = self._build_layout()
        self.set_state(state or AtlasPageState())

    def set_state(self, state: AtlasPageState) -> None:
        """Refresh copy and state properties without rebuilding the page."""

        atlas_state = "ready" if state.ready else "not_ready"
        self.status_label.setText(state.status_text)
        self.status_label.setProperty("atlasState", atlas_state)
        self.status_label.setStyleSheet(_status_stylesheet(ready=state.ready))
        self.detail_label.setText(state.detail_text)
        self.detail_label.setStyleSheet(
            f"QLabel#qfitWizardAtlasDetail {{ color: {COLOR_MUTED}; }}"
        )
        self.input_summary_label.setText(state.input_summary_text)
        self.input_summary_label.setProperty("atlasState", atlas_state)
        self.output_summary_label.setText(state.output_summary_text)
        self.output_summary_label.setProperty("atlasState", atlas_state)
        self.export_atlas_button.setText(state.primary_action_label)
        primary_action_enabled = (
            state.ready
            if state.primary_action_enabled is None
            else state.primary_action_enabled
        )
        set_wizard_action_availability(
            self.export_atlas_button,
            enabled=primary_action_enabled,
            tooltip=state.primary_action_blocked_tooltip,
        )

    def outer_layout(self):
        """Expose the layout for adapter wiring and pure tests."""

        return self._layout

    def _build_layout(self):
        layout = QVBoxLayout(self)
        if hasattr(layout, "setObjectName"):
            layout.setObjectName("qfitWizardAtlasPageContentLayout")
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        for widget in (
            self.status_label,
            self.detail_label,
            self.input_summary_label,
            self.output_summary_label,
            self.action_row,
        ):
            layout.addWidget(widget)
        return layout


def build_atlas_page_content(
    *,
    parent=None,
    state: AtlasPageState | None = None,
) -> AtlasPageContent:
    """Build the reusable atlas-export-step content widget."""

    return AtlasPageContent(state=state, parent=parent)


def install_atlas_page_content(
    page,
    *,
    state: AtlasPageState | None = None,
) -> AtlasPageContent:
    """Append atlas-export content to the matching wizard page body layout."""

    if page.spec.key != "atlas":
        raise ValueError(
            "Atlas page content can only be installed on the atlas wizard page"
        )
    content = build_atlas_page_content(parent=page, state=state)
    page.body_layout().addWidget(content)
    page.retire_primary_action_hint()
    return content


def _status_stylesheet(*, ready: bool) -> str:
    color = COLOR_ACCENT if ready else COLOR_WARN
    return (
        "QLabel#qfitWizardAtlasStatus { "
        f"color: {color}; "
        "font-weight: 700; "
        "}"
    )


__all__ = [
    "AtlasPageContent",
    "AtlasPageState",
    "build_atlas_page_content",
    "install_atlas_page_content",
]
