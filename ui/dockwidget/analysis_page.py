from __future__ import annotations

from dataclasses import dataclass

from qfit.ui.tokens import COLOR_ACCENT, COLOR_MUTED, COLOR_WARN

from ._qt_compat import import_qt_module
from .action_row import build_wizard_action_row, style_primary_action_button

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
class AnalysisPageState:
    """Render facts for the #609 spatial-analysis wizard page."""

    ready: bool = False
    status_text: str = "Analysis not run yet"
    detail_text: str = (
        "Use loaded activity layers to calculate heatmaps, corridors, and start points."
    )
    input_summary_text: str = "No loaded activity layers available for analysis"
    result_summary_text: str = "Analysis outputs will appear in the project once generated"
    primary_action_label: str = "Run analysis"


class AnalysisPageContent(QWidget):
    """Reusable fourth-page content for the wizard spatial-analysis step."""

    runAnalysisRequested = pyqtSignal()

    def __init__(self, state: AnalysisPageState | None = None, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("qfitWizardAnalysisPageContent")
        self.status_label = QLabel("", self)
        self.status_label.setObjectName("qfitWizardAnalysisStatus")
        self.detail_label = QLabel("", self)
        self.detail_label.setObjectName("qfitWizardAnalysisDetail")
        if hasattr(self.detail_label, "setWordWrap"):
            self.detail_label.setWordWrap(True)
        self.input_summary_label = QLabel("", self)
        self.input_summary_label.setObjectName("qfitWizardAnalysisInputSummary")
        self.result_summary_label = QLabel("", self)
        self.result_summary_label.setObjectName("qfitWizardAnalysisResultSummary")
        self.run_analysis_button = QToolButton(self)
        self.run_analysis_button.setObjectName("qfitWizardAnalysisRunButton")
        style_primary_action_button(
            self.run_analysis_button,
            action_name="run_analysis",
        )
        self.run_analysis_button.clicked.connect(self.runAnalysisRequested.emit)
        self.action_row = build_wizard_action_row(
            self.run_analysis_button,
            parent=self,
            object_name="qfitWizardAnalysisActionRow",
        )
        self._layout = self._build_layout()
        self.set_state(state or AnalysisPageState())

    def set_state(self, state: AnalysisPageState) -> None:
        """Refresh copy and state properties without rebuilding the page."""

        analysis_state = "ready" if state.ready else "not_ready"
        self.status_label.setText(state.status_text)
        self.status_label.setProperty("analysisState", analysis_state)
        self.status_label.setStyleSheet(_status_stylesheet(ready=state.ready))
        self.detail_label.setText(state.detail_text)
        self.detail_label.setStyleSheet(
            f"QLabel#qfitWizardAnalysisDetail {{ color: {COLOR_MUTED}; }}"
        )
        self.input_summary_label.setText(state.input_summary_text)
        self.input_summary_label.setProperty("analysisState", analysis_state)
        self.result_summary_label.setText(state.result_summary_text)
        self.result_summary_label.setProperty("analysisState", analysis_state)
        self.run_analysis_button.setText(state.primary_action_label)

    def outer_layout(self):
        """Expose the layout for adapter wiring and pure tests."""

        return self._layout

    def _build_layout(self):
        layout = QVBoxLayout(self)
        if hasattr(layout, "setObjectName"):
            layout.setObjectName("qfitWizardAnalysisPageContentLayout")
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        for widget in (
            self.status_label,
            self.detail_label,
            self.input_summary_label,
            self.result_summary_label,
            self.action_row,
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
    return content


def _status_stylesheet(*, ready: bool) -> str:
    color = COLOR_ACCENT if ready else COLOR_WARN
    return (
        "QLabel#qfitWizardAnalysisStatus { "
        f"color: {color}; "
        "font-weight: 700; "
        "}"
    )


__all__ = [
    "AnalysisPageContent",
    "AnalysisPageState",
    "build_analysis_page_content",
    "install_analysis_page_content",
]
