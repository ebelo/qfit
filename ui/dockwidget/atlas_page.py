from __future__ import annotations

from dataclasses import dataclass

from ._qt_compat import import_qt_module
from .action_row import (
    build_workflow_action_row,
    set_workflow_action_availability,
    style_primary_action_button,
)
from .page_content_style import (
    configure_fluid_text_label,
    configure_top_aligned_panel_layout,
    style_detail_label,
    style_status_pill,
    style_feedback_label,
)

_qtcore = import_qt_module("qgis.PyQt.QtCore", "PyQt5.QtCore", ("pyqtSignal",))
_qtwidgets = import_qt_module(
    "qgis.PyQt.QtWidgets",
    "PyQt5.QtWidgets",
    (
        "QLabel",
        "QLineEdit",
        "QToolButton",
        "QVBoxLayout",
        "QWidget",
    ),
)

pyqtSignal = _qtcore.pyqtSignal
QLabel = _qtwidgets.QLabel
QLineEdit = _qtwidgets.QLineEdit
QToolButton = _qtwidgets.QToolButton
QVBoxLayout = _qtwidgets.QVBoxLayout
QWidget = _qtwidgets.QWidget

_DEFAULT_ATLAS_TITLE = "qfit Activity Atlas"


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
    primary_action_blocked_tooltip: str = "Load activity layers before exporting atlas PDF."


class AtlasPageContent(QWidget):
    """Reusable fifth-page content for the wizard atlas-export step."""

    exportAtlasRequested = pyqtSignal()
    atlasDocumentSettingsChanged = pyqtSignal(str, str)

    def __init__(
        self,
        state: AtlasPageState | None = None,
        parent=None,
        *,
        atlas_title: str = _DEFAULT_ATLAS_TITLE,
        atlas_subtitle: str = "",
    ) -> None:
        super().__init__(parent)
        self._updating_document_settings = False
        self.setObjectName("qfitWizardAtlasPageContent")
        self.status_label = QLabel("", self)
        self.status_label.setObjectName("qfitWizardAtlasStatus")
        self.detail_label = QLabel("", self)
        self.detail_label.setObjectName("qfitWizardAtlasDetail")
        configure_fluid_text_label(self.detail_label)
        style_detail_label(self.detail_label)
        self.input_summary_label = QLabel("", self)
        self.input_summary_label.setObjectName("qfitWizardAtlasInputSummary")
        configure_fluid_text_label(self.input_summary_label)
        style_feedback_label(self.input_summary_label)
        self.output_summary_label = QLabel("", self)
        self.output_summary_label.setObjectName("qfitWizardAtlasOutputSummary")
        configure_fluid_text_label(self.output_summary_label)
        style_feedback_label(self.output_summary_label)
        self.title_label = QLabel("Atlas title", self)
        self.title_label.setObjectName("qfitWizardAtlasTitleLabel")
        style_detail_label(self.title_label)
        self.title_line_edit = QLineEdit(self)
        self.title_line_edit.setObjectName("qfitWizardAtlasTitleLineEdit")
        self.title_line_edit.setText(atlas_title)
        self.subtitle_label = QLabel("Atlas subtitle", self)
        self.subtitle_label.setObjectName("qfitWizardAtlasSubtitleLabel")
        style_detail_label(self.subtitle_label)
        self.subtitle_line_edit = QLineEdit(self)
        self.subtitle_line_edit.setObjectName("qfitWizardAtlasSubtitleLineEdit")
        if hasattr(self.subtitle_line_edit, "setPlaceholderText"):
            self.subtitle_line_edit.setPlaceholderText("Optional subtitle…")
        self.subtitle_line_edit.setText(atlas_subtitle)
        self.title_line_edit.textChanged.connect(self._emit_document_settings_changed)
        self.subtitle_line_edit.textChanged.connect(self._emit_document_settings_changed)
        self.export_atlas_button = QToolButton(self)
        self.export_atlas_button.setObjectName("qfitWizardAtlasExportButton")
        style_primary_action_button(
            self.export_atlas_button,
            action_name="export_atlas_pdf",
        )
        self.export_atlas_button.clicked.connect(self.exportAtlasRequested.emit)
        self.action_row = build_workflow_action_row(
            self.export_atlas_button,
            parent=self,
            object_name="qfitWizardAtlasActionRow",
        )
        self._layout = self._build_layout()
        self.set_state(state or AtlasPageState())

    def set_document_settings(self, *, atlas_title: str, atlas_subtitle: str) -> None:
        """Refresh visible cover settings without emitting a user-change signal."""

        self._updating_document_settings = True
        try:
            if self.title_line_edit.text() != atlas_title:
                self.title_line_edit.setText(atlas_title)
            if self.subtitle_line_edit.text() != atlas_subtitle:
                self.subtitle_line_edit.setText(atlas_subtitle)
        finally:
            self._updating_document_settings = False

    def _emit_document_settings_changed(self, *_args) -> None:
        if self._updating_document_settings:
            return
        self.atlasDocumentSettingsChanged.emit(
            self.title_line_edit.text(),
            self.subtitle_line_edit.text(),
        )

    def set_state(self, state: AtlasPageState) -> None:
        """Refresh copy and state properties without rebuilding the page."""

        atlas_state = "ready" if state.ready else "not_ready"
        self.status_label.setText(state.status_text)
        self.status_label.setProperty("atlasState", atlas_state)
        style_status_pill(self.status_label, active=state.ready)
        self.detail_label.setText(state.detail_text)
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
        set_workflow_action_availability(
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
        configure_top_aligned_panel_layout(layout)
        for widget in (
            self.status_label,
            self.detail_label,
            self.title_label,
            self.title_line_edit,
            self.subtitle_label,
            self.subtitle_line_edit,
            self.input_summary_label,
            self.action_row,
            self.output_summary_label,
        ):
            layout.addWidget(widget)
        return layout


def build_atlas_page_content(
    *,
    parent=None,
    state: AtlasPageState | None = None,
    atlas_title: str = _DEFAULT_ATLAS_TITLE,
    atlas_subtitle: str = "",
) -> AtlasPageContent:
    """Build the reusable atlas-export-step content widget."""

    return AtlasPageContent(
        state=state,
        parent=parent,
        atlas_title=atlas_title,
        atlas_subtitle=atlas_subtitle,
    )


def install_atlas_page_content(
    page,
    *,
    state: AtlasPageState | None = None,
    atlas_title: str = _DEFAULT_ATLAS_TITLE,
    atlas_subtitle: str = "",
) -> AtlasPageContent:
    """Append atlas-export content to the matching wizard page body layout."""

    if page.spec.key != "atlas":
        raise ValueError(
            "Atlas page content can only be installed on the atlas wizard page"
        )
    content = build_atlas_page_content(
        parent=page,
        state=state,
        atlas_title=atlas_title,
        atlas_subtitle=atlas_subtitle,
    )
    page.body_layout().addWidget(content)
    page.retire_primary_action_hint()
    return content


__all__ = [
    "AtlasPageContent",
    "AtlasPageState",
    "build_atlas_page_content",
    "install_atlas_page_content",
]
