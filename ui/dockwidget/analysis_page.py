from __future__ import annotations

from dataclasses import dataclass

from qfit.analysis.application.analysis_execution_dispatch import (
    FREQUENT_STARTING_POINTS_MODE,
    HEATMAP_MODE,
    SLOPE_GRADE_MODE,
)

from ._qt_compat import import_qt_module
from .action_row import (
    build_workflow_action_row,
    set_workflow_action_availability,
    style_primary_action_button,
    style_secondary_action_button,
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
        "QComboBox",
        "QLabel",
        "QToolButton",
        "QVBoxLayout",
        "QWidget",
    ),
)

pyqtSignal = _qtcore.pyqtSignal
QComboBox = _qtwidgets.QComboBox
QLabel = _qtwidgets.QLabel
QToolButton = _qtwidgets.QToolButton
QVBoxLayout = _qtwidgets.QVBoxLayout
QWidget = _qtwidgets.QWidget


@dataclass(frozen=True)
class AnalysisPageState:
    """Render facts for the #609 spatial-analysis wizard page."""

    ready: bool = False
    status_text: str = "Analysis not run yet"
    detail_text: str = (
        "Optional: calculate heatmaps, corridors, and start points from loaded data."
    )
    input_summary_text: str = "No loaded activity layers available for analysis"
    result_summary_text: str = "No analysis displayed"
    primary_action_label: str = "Run analysis"
    primary_action_enabled: bool | None = None
    primary_action_blocked_tooltip: str = "Load activity layers before running analysis."
    clear_action_label: str = "Clear analysis"
    clear_action_enabled: bool = True


class AnalysisPageContent(QWidget):
    """Reusable fourth-page content for the wizard spatial-analysis step."""

    runAnalysisRequested = pyqtSignal()
    clearAnalysisRequested = pyqtSignal()
    analysisModeChanged = pyqtSignal(str)

    def __init__(self, state: AnalysisPageState | None = None, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("qfitWizardAnalysisPageContent")
        self.status_label = QLabel("", self)
        self.status_label.setObjectName("qfitWizardAnalysisStatus")
        self.detail_label = QLabel("", self)
        self.detail_label.setObjectName("qfitWizardAnalysisDetail")
        configure_fluid_text_label(self.detail_label)
        style_detail_label(self.detail_label)
        self.input_summary_label = QLabel("", self)
        self.input_summary_label.setObjectName("qfitWizardAnalysisInputSummary")
        configure_fluid_text_label(self.input_summary_label)
        style_feedback_label(self.input_summary_label)
        self.result_summary_label = QLabel("", self)
        self.result_summary_label.setObjectName("qfitWizardAnalysisResultSummary")
        configure_fluid_text_label(self.result_summary_label)
        style_feedback_label(self.result_summary_label)
        self.analysis_mode_label = QLabel("Analysis mode", self)
        self.analysis_mode_label.setObjectName("qfitWizardAnalysisModeLabel")
        style_detail_label(self.analysis_mode_label)
        self.analysis_mode_combo = QComboBox(self)
        self.analysis_mode_combo.setObjectName("qfitWizardAnalysisModeComboBox")
        self.set_analysis_mode_options(
            (HEATMAP_MODE, FREQUENT_STARTING_POINTS_MODE, SLOPE_GRADE_MODE)
        )
        if hasattr(self.analysis_mode_combo, "currentTextChanged"):
            self.analysis_mode_combo.currentTextChanged.connect(
                self.analysisModeChanged.emit
            )
        self.run_analysis_button = QToolButton(self)
        self.run_analysis_button.setObjectName("qfitWizardAnalysisRunButton")
        style_primary_action_button(
            self.run_analysis_button,
            action_name="run_analysis",
        )
        self.run_analysis_button.clicked.connect(self.runAnalysisRequested.emit)
        self.clear_analysis_button = QToolButton(self)
        self.clear_analysis_button.setObjectName("qfitWizardAnalysisClearButton")
        style_secondary_action_button(
            self.clear_analysis_button,
            action_name="clear_analysis",
        )
        self.clear_analysis_button.clicked.connect(self.clearAnalysisRequested.emit)
        self.action_row = build_workflow_action_row(
            self.run_analysis_button,
            self.clear_analysis_button,
            parent=self,
            object_name="qfitWizardAnalysisActionRow",
        )
        self._layout = self._build_layout()
        self.set_state(state or AnalysisPageState())

    def set_analysis_mode_options(
        self,
        options: tuple[str, ...],
        *,
        selected: str | None = None,
    ) -> None:
        """Expose selectable analysis modes in the live wizard surface."""

        if hasattr(self.analysis_mode_combo, "clear"):
            self.analysis_mode_combo.clear()
        for option in options:
            self.analysis_mode_combo.addItem(option)
        if selected:
            self.analysis_mode_combo.setCurrentText(selected)

    def current_analysis_mode(self) -> str:
        """Return the wizard-selected analysis mode."""

        return self.analysis_mode_combo.currentText()

    def set_state(self, state: AnalysisPageState) -> None:
        """Refresh copy and state properties without rebuilding the page."""

        analysis_state = "ready" if state.ready else "not_ready"
        self.status_label.setText(state.status_text)
        self.status_label.setProperty("analysisState", analysis_state)
        style_status_pill(self.status_label, active=state.ready)
        self.detail_label.setText(state.detail_text)
        self.input_summary_label.setText(state.input_summary_text)
        self.input_summary_label.setProperty("analysisState", analysis_state)
        self.result_summary_label.setText(state.result_summary_text)
        self.result_summary_label.setProperty("analysisState", analysis_state)
        self.run_analysis_button.setText(state.primary_action_label)
        primary_action_enabled = (
            state.ready
            if state.primary_action_enabled is None
            else state.primary_action_enabled
        )
        set_workflow_action_availability(
            self.run_analysis_button,
            enabled=primary_action_enabled,
            tooltip=state.primary_action_blocked_tooltip,
        )
        self.clear_analysis_button.setText(state.clear_action_label)
        set_workflow_action_availability(
            self.clear_analysis_button,
            enabled=state.clear_action_enabled,
        )

    def outer_layout(self):
        """Expose the layout for adapter wiring and pure tests."""

        return self._layout

    def _build_layout(self):
        layout = QVBoxLayout(self)
        if hasattr(layout, "setObjectName"):
            layout.setObjectName("qfitWizardAnalysisPageContentLayout")
        configure_top_aligned_panel_layout(layout)
        for widget in (
            self.status_label,
            self.detail_label,
            self.input_summary_label,
            self.analysis_mode_label,
            self.analysis_mode_combo,
            self.action_row,
            self.result_summary_label,
        ):
            layout.addWidget(widget)
        return layout


def build_analysis_page_content(
    *,
    parent=None,
    state: AnalysisPageState | None = None,
) -> AnalysisPageContent:
    """Build the reusable spatial-analysis-step content widget."""

    return AnalysisPageContent(state=state, parent=parent)


def install_analysis_page_content(
    page,
    *,
    state: AnalysisPageState | None = None,
) -> AnalysisPageContent:
    """Append spatial-analysis content to the matching wizard page body layout."""

    if page.spec.key != "analysis":
        raise ValueError(
            "Analysis page content can only be installed on the analysis wizard page"
        )
    content = build_analysis_page_content(parent=page, state=state)
    page.body_layout().addWidget(content)
    page.retire_primary_action_hint()
    return content


__all__ = [
    "AnalysisPageContent",
    "AnalysisPageState",
    "build_analysis_page_content",
    "install_analysis_page_content",
]
