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
        dock.workflowLabel.setText("Sections: Fetch & store · Visualize · Analyze · Publish")
        dock.credentialsGroupBox.hide()
        dock.activitiesGroupBox.setTitle("")
        dock.activitiesIntroLabel.setText(
            "Fetch your activities from Strava using the credentials saved in qfit → Configuration. "
            "Store or clear the local GeoPackage here too. Filters are applied later in the Visualize step — no re-fetch needed."
        )
        self._configure_spinbox_unit_copy()
        self._move_store_section_under_fetch()
        self._move_load_layers_to_visualize()
        self._move_temporal_controls_to_visualize()
        self._move_clear_database_to_actions_menu()
        dock.outputGroupBox.setTitle("Store / database")
        dock.publishGroupBox.setCheckable(False)
        dock.publishSettingsWidget.setVisible(True)
        self._pin_summary_status_footer()
        self._hide_redundant_status_labels()
        self.install_collapsible_section(
            dock.activitiesGroupBox,
            "activitiesGroupLayout",
            "Fetch and store",
            "activities",
        )
        self.install_collapsible_section(dock.styleGroupBox, "styleGroupLayout", "Visualize", "style")
        self.install_collapsible_section(
            dock.analysisWorkflowGroupBox,
            "analysisWorkflowLayout",
            "Analyze",
            "analysis",
        )
        self.install_collapsible_section(
            dock.publishGroupBox,
            "publishGroupLayout",
            "Publish / atlas",
            "publish",
        )
        self._move_help_label_to_tooltip(
            dock.activitiesIntroLabel,
            getattr(dock, "activitiesSectionToggleButton", None),
            dock.activitiesGroupBox,
        )
        self._move_help_label_to_tooltip(dock.outputIntroLabel, dock.outputGroupBox)
        self._move_help_label_to_tooltip(
            dock.atlasPdfHelpLabel,
            dock.atlasPdfGroupBox,
            dock.generateAtlasPdfButton,
        )
        dock.mapboxAccessTokenLabel.hide()
        dock.mapboxAccessTokenLineEdit.hide()

    def _pin_summary_status_footer(self) -> None:
        dock = self.dock_widget
        if getattr(dock, "_summary_status_footer_pinned", False):
            return

        label = getattr(dock, "summaryStatusLabel", None)
        outer_layout = getattr(dock, "outerLayout", None)
        if label is None or outer_layout is None:
            return

        scroll_layout = getattr(dock, "verticalLayout", None)
        if scroll_layout is not None and hasattr(scroll_layout, "removeWidget"):
            scroll_layout.removeWidget(label)

        parent = getattr(dock, "dockWidgetContents", None)
        if parent is not None and hasattr(label, "setParent"):
            label.setParent(parent)

        if hasattr(label, "setMinimumHeight"):
            label.setMinimumHeight(28)
        if hasattr(label, "setStyleSheet"):
            label.setStyleSheet(
                "QLabel#summaryStatusLabel { "
                "border-top: 1px solid palette(mid); "
                "padding: 4px 8px; "
                "}"
            )

        outer_layout.addWidget(label)
        dock._summary_status_footer_pinned = True

    def _hide_redundant_status_labels(self) -> None:
        for name in ("countLabel", "statusLabel"):
            label = getattr(self.dock_widget, name, None)
            if label is not None and hasattr(label, "hide"):
                label.hide()

    def _configure_spinbox_unit_copy(self) -> None:
        """Keep units in spin boxes instead of repeating them in form labels."""

        for label_name, label_text, spinbox_name, suffix in (
            ("perPageLabel", "Page size", "perPageSpinBox", " activities"),
            ("maxPagesLabel", "Pages to fetch", "maxPagesSpinBox", " pages"),
            (
                "maxDetailedActivitiesLabel",
                "Detailed route limit",
                "maxDetailedActivitiesSpinBox",
                " routes",
            ),
            (
                "pointSamplingStrideLabel",
                "Point sampling stride",
                "pointSamplingStrideSpinBox",
                " points",
            ),
        ):
            self._set_label_text(label_name, label_text)
            self._set_spinbox_suffix(spinbox_name, suffix)

    def _set_label_text(self, name: str, text: str) -> None:
        label = getattr(self.dock_widget, name, None)
        if label is not None and hasattr(label, "setText"):
            label.setText(text)

    def _set_spinbox_suffix(self, name: str, suffix: str) -> None:
        spinbox = getattr(self.dock_widget, name, None)
        if spinbox is not None and hasattr(spinbox, "setSuffix"):
            spinbox.setSuffix(suffix)

    def _move_clear_database_to_actions_menu(self) -> None:
        dock = self.dock_widget
        if hasattr(dock, "databaseActionsButton"):
            return

        clear_button = getattr(dock, "clearDatabaseButton", None)
        output_layout = getattr(dock, "outputGroupLayout", None)
        if clear_button is None or output_layout is None:
            return

        from qgis.PyQt.QtWidgets import QMenu, QToolButton

        menu = QMenu(getattr(dock, "outputGroupBox", None))
        if hasattr(menu, "setObjectName"):
            menu.setObjectName("databaseActionsMenu")
        clear_action = menu.addAction("Clear database…")
        clear_action.setToolTip(
            "Delete qfit's stored activities and derived layers after confirmation."
        )
        clear_action.triggered.connect(clear_button.click)

        menu_button = QToolButton(getattr(dock, "outputGroupBox", None))
        menu_button.setObjectName("databaseActionsButton")
        menu_button.setText("Database actions")
        menu_button.setToolTip(
            "Less common database operations; destructive actions ask for confirmation."
        )
        menu_button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        menu_button.setPopupMode(QToolButton.InstantPopup)
        menu_button.setMenu(menu)

        output_layout.removeWidget(clear_button)
        clear_button.hide()
        output_layout.addWidget(menu_button)

        dock.databaseActionsMenu = menu
        dock.databaseActionsButton = menu_button
        dock.clearDatabaseAction = clear_action

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

    def _move_help_label_to_tooltip(self, label, *widgets) -> None:
        if label is None:
            return

        text = getattr(label, "text", None)
        if callable(text):
            text = text()
        if not text:
            return

        for widget in widgets:
            if widget is not None and hasattr(widget, "setToolTip"):
                widget.setToolTip(text)

        if hasattr(label, "hide"):
            label.hide()

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
