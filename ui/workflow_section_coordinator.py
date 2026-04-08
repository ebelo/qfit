from __future__ import annotations

from qgis.PyQt.QtCore import Qt

from ..mapbox_config import preset_requires_custom_style


class WorkflowSectionCoordinator:
    """Coordinate dock-widget workflow sections and conditional field visibility.

    This keeps section layout/visibility rules out of ``QfitDockWidget`` so the
    dock widget can focus more on wiring signals and rendering user feedback.
    """

    def __init__(self, dock_widget):
        self.dock_widget = dock_widget

    def configure_starting_sections(self) -> None:
        dock = self.dock_widget
        dock.workflowLabel.setText("Workflow: Fetch & store → Visualize → Analyze → Publish")
        dock.credentialsGroupBox.hide()
        dock.activitiesGroupBox.setTitle("")
        dock.activitiesIntroLabel.setText(
            "Fetch your activities from Strava using the credentials saved in qfit → Configuration. "
            "Store or clear the local GeoPackage here too. Filters are applied later in the Visualize step — no re-fetch needed."
        )
        self._move_store_section_under_fetch()
        self._move_load_layers_to_visualize()
        self._move_temporal_controls_to_visualize()
        dock.outputGroupBox.setTitle("Store / database")
        dock.publishGroupBox.setCheckable(False)
        dock.publishSettingsWidget.setVisible(True)
        self.install_collapsible_section(
            dock.activitiesGroupBox,
            "activitiesGroupLayout",
            "1. Fetch and store activities",
            "activities",
        )
        self.install_collapsible_section(dock.styleGroupBox, "styleGroupLayout", "2. Visualize", "style")
        self.install_collapsible_section(
            dock.analysisWorkflowGroupBox,
            "analysisWorkflowLayout",
            "3. Analyze",
            "analysis",
        )
        self.install_collapsible_section(
            dock.publishGroupBox,
            "publishGroupLayout",
            "4. Publish / atlas",
            "publish",
        )
        dock.mapboxAccessTokenLabel.hide()
        dock.mapboxAccessTokenLineEdit.hide()

    def install_collapsible_section(self, group_box, layout_attr: str, title: str, key: str) -> None:
        dock = self.dock_widget
        layout = getattr(dock, layout_attr, None)
        toggle_attr = f"{key}SectionToggleButton"
        content_attr = f"{key}SectionContentWidget"
        if layout is None or hasattr(dock, toggle_attr):
            return

        group_box.setTitle("")

        from qgis.PyQt.QtWidgets import QToolButton, QVBoxLayout, QWidget

        content_widget = QWidget(group_box)
        content_widget.setObjectName(f"{key}SectionContentWidget")
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(layout.spacing())

        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            child_layout = item.layout()
            spacer = item.spacerItem()
            if widget is not None:
                content_layout.addWidget(widget)
            elif child_layout is not None:
                content_layout.addLayout(child_layout)
            elif spacer is not None:
                content_layout.addItem(spacer)

        toggle = QToolButton(group_box)
        toggle.setObjectName(f"{key}SectionToggleButton")
        toggle.setText(title)
        toggle.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        toggle.setArrowType(Qt.DownArrow)
        toggle.setCheckable(True)
        toggle.setChecked(True)
        toggle.setStyleSheet("QToolButton { border: none; font-weight: bold; }")
        toggle.toggled.connect(lambda expanded, section_key=key: self.set_section_expanded(section_key, expanded))

        setattr(dock, toggle_attr, toggle)
        setattr(dock, content_attr, content_widget)
        layout.addWidget(toggle)
        layout.addWidget(content_widget)

    def set_section_expanded(self, key: str, expanded: bool) -> None:
        dock = self.dock_widget
        toggle = getattr(dock, f"{key}SectionToggleButton", None)
        content = getattr(dock, f"{key}SectionContentWidget", None)
        if toggle is not None:
            toggle.setArrowType(Qt.DownArrow if expanded else Qt.RightArrow)
        if content is not None:
            content.setVisible(expanded)

    def configure_workflow_sections(self) -> None:
        dock = self.dock_widget
        self.update_detailed_fetch_visibility(dock.detailedStreamsCheckBox.isChecked())
        self.update_point_sampling_visibility(dock.writeActivityPointsCheckBox.isChecked())
        self.update_advanced_fetch_visibility(dock.advancedFetchGroupBox.isChecked())
        self.update_mapbox_advanced_visibility(dock.backgroundPresetComboBox.currentText())

    def update_detailed_fetch_visibility(self, enabled: bool) -> None:
        dock = self.dock_widget
        backfill_button = getattr(dock, "backfillMissingDetailedRoutesButton", None)
        if backfill_button is not None:
            backfill_button.setVisible(enabled)
        dock.detailedRouteStrategyLabel.setVisible(enabled)
        dock.detailedRouteStrategyComboBox.setVisible(enabled)
        strategy_helper = getattr(dock, "detailedRouteStrategyComboBoxContextHelpLabel", None)
        if strategy_helper is not None:
            strategy_helper.setVisible(enabled)
        strategy_wrapper = getattr(dock, "detailedRouteStrategyComboBoxHelpField", None)
        if strategy_wrapper is not None:
            strategy_wrapper.setVisible(enabled)
        dock.maxDetailedActivitiesLabel.setVisible(enabled)
        dock.maxDetailedActivitiesSpinBox.setVisible(enabled)
        helper = getattr(dock, "maxDetailedActivitiesSpinBoxContextHelpLabel", None)
        if helper is not None:
            helper.setVisible(enabled)
        wrapper = getattr(dock, "maxDetailedActivitiesSpinBoxHelpField", None)
        if wrapper is not None:
            wrapper.setVisible(enabled)

    def update_point_sampling_visibility(self, enabled: bool) -> None:
        dock = self.dock_widget
        dock.pointSamplingStrideLabel.setVisible(enabled)
        dock.pointSamplingStrideSpinBox.setVisible(enabled)
        helper = getattr(dock, "pointSamplingStrideSpinBoxContextHelpLabel", None)
        if helper is not None:
            helper.setVisible(enabled)
        wrapper = getattr(dock, "pointSamplingStrideSpinBoxHelpField", None)
        if wrapper is not None:
            wrapper.setVisible(enabled)

    def update_advanced_fetch_visibility(self, expanded: bool) -> None:
        widget = getattr(self.dock_widget, "advancedFetchSettingsWidget", None)
        if widget is not None:
            widget.setVisible(expanded)

    def update_mapbox_advanced_visibility(self, preset_name: str) -> None:
        dock = self.dock_widget
        show_advanced = preset_requires_custom_style(preset_name)
        dock.mapboxStyleOwnerLabel.setVisible(show_advanced)
        dock.mapboxStyleOwnerLineEdit.setVisible(show_advanced)
        dock.mapboxStyleIdLabel.setVisible(show_advanced)
        dock.mapboxStyleIdLineEdit.setVisible(show_advanced)
        owner_helper = getattr(dock, "mapboxStyleOwnerLineEditContextHelpLabel", None)
        if owner_helper is not None:
            owner_helper.setVisible(show_advanced)
        style_helper = getattr(dock, "mapboxStyleIdLineEditContextHelpLabel", None)
        if style_helper is not None:
            style_helper.setVisible(show_advanced)
        style_wrapper = getattr(dock, "mapboxStyleIdLineEditHelpField", None)
        if style_wrapper is not None:
            style_wrapper.setVisible(show_advanced)

    def _move_store_section_under_fetch(self) -> None:
        dock = self.dock_widget
        outer_layout = getattr(dock, "verticalLayout", None)
        activities_layout = getattr(dock, "activitiesGroupLayout", None)
        if outer_layout is None or activities_layout is None:
            return
        if dock.outputGroupBox.parent() is dock.activitiesGroupBox:
            return
        outer_layout.removeWidget(dock.outputGroupBox)
        dock.outputGroupBox.setParent(dock.activitiesGroupBox)
        activities_layout.addWidget(dock.outputGroupBox)

    def _move_load_layers_to_visualize(self) -> None:
        dock = self.dock_widget
        output_layout = getattr(dock, "outputGroupLayout", None)
        style_layout = getattr(dock, "styleGroupLayout", None)
        if output_layout is None or style_layout is None:
            return
        if dock.loadLayersButton.parent() is dock.styleGroupBox:
            return
        output_layout.removeWidget(dock.loadLayersButton)
        dock.loadLayersButton.setParent(dock.styleGroupBox)
        style_layout.insertWidget(0, dock.loadLayersButton)

    def _move_temporal_controls_to_visualize(self) -> None:
        dock = self.dock_widget
        analysis_layout = getattr(dock, "analysisWorkflowLayout", None)
        style_layout = getattr(dock, "styleGroupLayout", None)
        temporal_row = getattr(dock, "analysisTemporalModeRow", None)
        temporal_help = getattr(dock, "temporalHelpLabel", None)
        if analysis_layout is None or style_layout is None or temporal_row is None or temporal_help is None:
            return
        if temporal_row.parent() is dock.styleGroupBox:
            return
        analysis_layout.removeWidget(temporal_row)
        analysis_layout.removeWidget(temporal_help)
        temporal_row.setParent(dock.styleGroupBox)
        temporal_help.setParent(dock.styleGroupBox)
        style_layout.addWidget(temporal_row)
        style_layout.addWidget(temporal_help)
