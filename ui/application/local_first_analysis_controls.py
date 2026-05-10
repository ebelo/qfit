from __future__ import annotations

from ...analysis.application.analysis_execution_dispatch import (
    FREQUENT_STARTING_POINTS_MODE,
    HEATMAP_MODE,
    SLOPE_GRADE_MODE,
)


NONE_ANALYSIS_MODE_LABEL = "None"
ANALYSIS_MODE_LABELS = (
    NONE_ANALYSIS_MODE_LABEL,
    FREQUENT_STARTING_POINTS_MODE,
    HEATMAP_MODE,
    SLOPE_GRADE_MODE,
)


def configure_local_first_analysis_mode_backing_controls(dock) -> None:
    """Install the analysis-mode backing controls used by local-first pages.

    The visible local-first analysis page owns the user-facing selector, but the
    dock still keeps a hidden combo/button row as the persistence and workflow
    bridge during consolidation. Keep that bridge setup with the rest of the
    local-first analysis control policy instead of growing QfitDockWidget.
    """

    from qgis.PyQt.QtWidgets import (
        QComboBox,
        QHBoxLayout,
        QLabel,
        QPushButton,
        QWidget,
    )

    content_widget = dock.analysisWorkflowGroupBox
    content_layout = content_widget.layout()

    row = QWidget(content_widget)
    row.setObjectName("analysisModeRow")
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(6)

    label = QLabel("Analysis", row)
    label.setObjectName("analysisModeLabel")
    layout.addWidget(label)

    combo = QComboBox(row)
    combo.setObjectName("analysisModeComboBox")
    for mode_label in ANALYSIS_MODE_LABELS:
        combo.addItem(mode_label)
    layout.addWidget(combo)

    button = QPushButton("Run analysis", row)
    button.setObjectName("runAnalysisButton")
    layout.addWidget(button)
    layout.addStretch(1)

    content_layout.insertWidget(0, row)
    dock.analysisModeLabel = label
    dock.analysisModeComboBox = combo
    dock.runAnalysisButton = button


def bind_local_first_analysis_mode_controls(dock, composition) -> None:
    """Bind the local-first analysis page mode selector to dock state.

    The visible local-first analysis page owns mode selection, while the legacy
    combo remains the settings/workflow backing control during the dock
    consolidation. Keep that bridge in application code instead of embedding the
    binding policy in QfitDockWidget.
    """

    analysis_content = getattr(composition, "analysis_content", None)
    mode_combo = getattr(dock, "analysisModeComboBox", None)
    set_options = getattr(analysis_content, "set_analysis_mode_options", None)
    if mode_combo is None or not callable(set_options):
        return

    options = local_first_analysis_mode_options(mode_combo)
    if not options:
        return

    selected_mode = mode_combo.currentText()
    if selected_mode == NONE_ANALYSIS_MODE_LABEL or selected_mode not in options:
        selected_mode = options[0]

    set_options(options, selected=selected_mode)
    set_local_first_analysis_mode(dock, selected_mode)


def local_first_analysis_mode_options(mode_combo) -> tuple[str, ...]:
    """Return user-facing analysis modes from the backing combo box."""

    return tuple(
        mode
        for mode in (mode_combo.itemText(index) for index in range(mode_combo.count()))
        if mode != NONE_ANALYSIS_MODE_LABEL
    )


def set_local_first_analysis_mode(dock, mode: str) -> None:
    """Mirror the local-first analysis selection into the backing dock combo."""

    mode_combo = getattr(dock, "analysisModeComboBox", None)
    if mode_combo is None or not mode:
        return
    mode_combo.setCurrentText(mode)


__all__ = [
    "ANALYSIS_MODE_LABELS",
    "NONE_ANALYSIS_MODE_LABEL",
    "bind_local_first_analysis_mode_controls",
    "configure_local_first_analysis_mode_backing_controls",
    "local_first_analysis_mode_options",
    "set_local_first_analysis_mode",
]
