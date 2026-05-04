from __future__ import annotations

from dataclasses import dataclass

from ._qt_compat import import_qt_module
from .action_row import (
    build_wizard_action_row,
    set_wizard_action_availability,
    style_primary_action_button,
    style_secondary_action_button,
)
from .page_content_style import (
    style_detail_label,
    style_status_pill,
    style_summary_label,
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
    background_summary_text: str = "Basemap disabled"
    style_summary_text: str = "Default activity styling"
    filter_summary_text: str = "All stored activities visible once layers are loaded"
    load_action_label: str = "Load activity layers"
    load_action_enabled: bool = True
    load_action_blocked_tooltip: str = "Sync activities before loading map layers."
    primary_action_label: str = "Apply filters"
    apply_action_enabled: bool | None = None
    apply_action_blocked_tooltip: str = "Load activity layers before applying filters."


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
        style_detail_label(self.detail_label)
        self.layer_summary_label = QLabel("", self)
        self.layer_summary_label.setObjectName("qfitWizardMapLayerSummary")
        style_summary_label(self.layer_summary_label)
        self.background_summary_label = QLabel("", self)
        self.background_summary_label.setObjectName("qfitWizardMapBackgroundSummary")
        style_summary_label(self.background_summary_label)
        self.style_summary_label = QLabel("", self)
        self.style_summary_label.setObjectName("qfitWizardMapStyleSummary")
        style_summary_label(self.style_summary_label)
        self.filter_summary_label = QLabel("", self)
        self.filter_summary_label.setObjectName("qfitWizardMapFilterSummary")
        style_summary_label(self.filter_summary_label)
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
        self.filter_controls_panel = QWidget(self)
        self.filter_controls_panel.setObjectName("qfitWizardMapFilterControlsPanel")
        self.filter_controls_panel.setVisible(True)
        self.filter_controls_panel.setProperty("filterControlsState", "expanded")
        self._filter_controls_layout = self._build_filter_controls_layout()
        self._layout = self._build_layout()
        self.set_state(state or MapPageState())

    def set_state(self, state: MapPageState) -> None:
        """Refresh copy and state properties without rebuilding the page."""

        map_state = "loaded" if state.loaded else "not_loaded"
        self.status_label.setText(state.status_text)
        self.status_label.setProperty("mapState", map_state)
        style_status_pill(self.status_label, active=state.loaded)
        self.detail_label.setText(state.detail_text)
        self.layer_summary_label.setText(state.layer_summary_text)
        self.layer_summary_label.setProperty("mapState", map_state)
        self.background_summary_label.setText(state.background_summary_text)
        self.background_summary_label.setProperty("mapState", map_state)
        self.style_summary_label.setText(state.style_summary_text)
        self.style_summary_label.setProperty("mapState", map_state)
        self.filter_summary_label.setText(state.filter_summary_text)
        self.filter_summary_label.setProperty("mapState", map_state)
        self.load_layers_button.setText(state.load_action_label)
        set_wizard_action_availability(
            self.load_layers_button,
            enabled=state.load_action_enabled,
            tooltip=state.load_action_blocked_tooltip,
        )
        self.set_filter_controls_visible()
        self.apply_filters_button.setText(state.primary_action_label)
        apply_action_enabled = (
            state.loaded
            if state.apply_action_enabled is None
            else state.apply_action_enabled
        )
        set_wizard_action_availability(
            self.apply_filters_button,
            enabled=apply_action_enabled,
            tooltip=state.apply_action_blocked_tooltip,
        )

    def filter_controls_layout(self):
        """Expose the wizard panel slot for live map-filter controls."""

        return self._filter_controls_layout

    def set_filter_controls_visible(self) -> None:
        """Keep embedded filter controls visible without rebuilding the page."""

        self.filter_controls_panel.setVisible(True)
        self.filter_controls_panel.setProperty("filterControlsState", "expanded")

    def outer_layout(self):
        """Expose the layout for adapter wiring and pure tests."""

        return self._layout

    def _build_filter_controls_layout(self):
        layout = QVBoxLayout(self.filter_controls_panel)
        if hasattr(layout, "setObjectName"):
            layout.setObjectName("qfitWizardMapFilterControlsLayout")
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        return layout

    def _build_layout(self):
        layout = QVBoxLayout(self)
        if hasattr(layout, "setObjectName"):
            layout.setObjectName("qfitWizardMapPageContentLayout")
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(self.status_label)
        layout.addWidget(self.detail_label)
        layout.addWidget(self.layer_summary_label)
        layout.addWidget(self.background_summary_label)
        layout.addWidget(self.style_summary_label)
        layout.addWidget(self.filter_summary_label)
        layout.addWidget(self.filter_controls_panel)
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


__all__ = [
    "MapPageContent",
    "MapPageState",
    "build_map_page_content",
    "install_map_page_content",
]
