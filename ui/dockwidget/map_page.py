from __future__ import annotations

from dataclasses import dataclass

from qfit.ui.tokens import COLOR_ACCENT, COLOR_MUTED, COLOR_WARN

from ._qt_compat import import_qt_module
from .action_row import (
    build_wizard_action_row,
    style_primary_action_button,
    style_secondary_action_button,
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
class MapPageState:
    """Render facts for the #609 map-and-filters wizard page."""

    loaded: bool = False
    status_text: str = "Activity layers not loaded"
    detail_text: str = "Load stored activities, choose map context, then apply filters."
    layer_summary_text: str = "No activity layers on the map"
    filter_summary_text: str = "All stored activities visible once layers are loaded"
    load_action_label: str = "Load activity layers"
    primary_action_label: str = "Apply filters"


class MapPageContent(QWidget):
    """Reusable third-page content for the wizard map-and-filters step."""

    loadLayersRequested = pyqtSignal()
    applyFiltersRequested = pyqtSignal()

    def __init__(self, state: MapPageState | None = None, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("qfitWizardMapPageContent")
        self.status_label = QLabel("", self)
        self.status_label.setObjectName("qfitWizardMapStatus")
        self.detail_label = QLabel("", self)
        self.detail_label.setObjectName("qfitWizardMapDetail")
        if hasattr(self.detail_label, "setWordWrap"):
            self.detail_label.setWordWrap(True)
        self.layer_summary_label = QLabel("", self)
        self.layer_summary_label.setObjectName("qfitWizardMapLayerSummary")
        self.filter_summary_label = QLabel("", self)
        self.filter_summary_label.setObjectName("qfitWizardMapFilterSummary")
        self.load_layers_button = QToolButton(self)
        self.load_layers_button.setObjectName("qfitWizardMapLoadLayersButton")
        style_secondary_action_button(
            self.load_layers_button,
            action_name="load_activity_layers",
        )
        self.load_layers_button.clicked.connect(self.loadLayersRequested.emit)
        self.apply_filters_button = QToolButton(self)
        self.apply_filters_button.setObjectName("qfitWizardMapApplyFiltersButton")
        style_primary_action_button(
            self.apply_filters_button,
            action_name="apply_map_filters",
        )
        self.apply_filters_button.clicked.connect(self.applyFiltersRequested.emit)
        self.action_row = build_wizard_action_row(
            self.load_layers_button,
            self.apply_filters_button,
            parent=self,
            object_name="qfitWizardMapActionRow",
        )
        self._layout = self._build_layout()
        self.set_state(state or MapPageState())

    def set_state(self, state: MapPageState) -> None:
        """Refresh copy and state properties without rebuilding the page."""

        map_state = "loaded" if state.loaded else "not_loaded"
        self.status_label.setText(state.status_text)
        self.status_label.setProperty("mapState", map_state)
        self.status_label.setStyleSheet(_status_stylesheet(loaded=state.loaded))
        self.detail_label.setText(state.detail_text)
        self.detail_label.setStyleSheet(
            f"QLabel#qfitWizardMapDetail {{ color: {COLOR_MUTED}; }}"
        )
        self.layer_summary_label.setText(state.layer_summary_text)
        self.layer_summary_label.setProperty("mapState", map_state)
        self.filter_summary_label.setText(state.filter_summary_text)
        self.filter_summary_label.setProperty("mapState", map_state)
        self.load_layers_button.setText(state.load_action_label)
        self.apply_filters_button.setText(state.primary_action_label)

    def outer_layout(self):
        """Expose the layout for adapter wiring and pure tests."""

        return self._layout

    def _build_layout(self):
        layout = QVBoxLayout(self)
        if hasattr(layout, "setObjectName"):
            layout.setObjectName("qfitWizardMapPageContentLayout")
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(self.status_label)
        layout.addWidget(self.detail_label)
        layout.addWidget(self.layer_summary_label)
        layout.addWidget(self.filter_summary_label)
        layout.addWidget(self.action_row)
        return layout


def build_map_page_content(
    *,
    parent=None,
    state: MapPageState | None = None,
) -> MapPageContent:
    """Build the reusable map-and-filters-step content widget."""

    return MapPageContent(state=state, parent=parent)


def install_map_page_content(
    page,
    *,
    state: MapPageState | None = None,
) -> MapPageContent:
    """Append map-and-filters content to the matching wizard page body layout."""

    if page.spec.key != "map":
        raise ValueError("Map page content can only be installed on the map wizard page")
    content = build_map_page_content(parent=page, state=state)
    page.body_layout().addWidget(content)
    page.retire_primary_action_hint()
    return content


def _status_stylesheet(*, loaded: bool) -> str:
    color = COLOR_ACCENT if loaded else COLOR_WARN
    return (
        "QLabel#qfitWizardMapStatus { "
        f"color: {color}; "
        "font-weight: 700; "
        "}"
    )


__all__ = [
    "MapPageContent",
    "MapPageState",
    "build_map_page_content",
    "install_map_page_content",
]
