from __future__ import annotations

from qfit.ui.tokens import COLOR_MUTED

from .dock_workflow_sections import build_current_dock_workflow_label


def configure_local_first_backing_controls(dock) -> None:
    """Prepare legacy widgets that still back the local-first dock pages."""

    dock.workflowLabel.setText(build_current_dock_workflow_label())
    dock.credentialsGroupBox.hide()
    for group_box in (
        dock.activitiesGroupBox,
        dock.styleGroupBox,
        dock.analysisWorkflowGroupBox,
        dock.publishGroupBox,
    ):
        group_box.setTitle("")
    dock.activitiesIntroLabel.setText(
        "Fetch your activities from Strava using the credentials saved in qfit → "
        "Configuration. Store or clear the local GeoPackage here too. Filters "
        "are applied later in the Visualize step — no re-fetch needed."
    )
    _move_store_section_under_fetch(dock)
    _move_load_layers_to_visualize(dock)
    _move_temporal_controls_to_visualize(dock)
    _move_clear_database_to_actions_menu(dock)
    dock.outputGroupBox.setTitle("Store / database")
    dock.publishGroupBox.setCheckable(False)
    dock.publishSettingsWidget.setVisible(True)
    _pin_summary_status_footer(dock)
    _hide_redundant_status_labels(dock)
    _style_legacy_feedback_labels(dock)
    _move_help_label_to_tooltip(
        dock.activitiesIntroLabel,
        dock.activitiesGroupBox,
    )
    _move_help_label_to_tooltip(dock.outputIntroLabel, dock.outputGroupBox)
    _move_help_label_to_tooltip(
        dock.atlasPdfHelpLabel,
        dock.atlasPdfGroupBox,
        dock.generateAtlasPdfButton,
    )
    dock.mapboxAccessTokenLabel.hide()
    dock.mapboxAccessTokenLineEdit.hide()


def configure_local_first_spinbox_unit_copy(dock) -> None:
    """Keep units in spin boxes instead of repeating them in form labels."""

    for label_name, label_text, spinbox_name, suffix in (
        (
            "pointSamplingStrideLabel",
            "Keep every Nth point",
            "pointSamplingStrideSpinBox",
            " points",
        ),
    ):
        _set_label_text(dock, label_name, label_text)
        _set_spinbox_suffix(dock, spinbox_name, suffix)


def _pin_summary_status_footer(dock) -> None:
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
            "font-style: italic; "
            "padding: 4px 8px; "
            "}"
        )

    outer_layout.addWidget(label)
    dock._summary_status_footer_pinned = True


def _hide_redundant_status_labels(dock) -> None:
    for name in ("countLabel", "statusLabel"):
        label = getattr(dock, name, None)
        if label is not None and hasattr(label, "hide"):
            label.hide()


def _style_legacy_feedback_labels(dock) -> None:
    for name in (
        "connectionStatusLabel",
        "querySummaryLabel",
        "atlasPdfStatusLabel",
    ):
        label = getattr(dock, name, None)
        if label is None or not hasattr(label, "setStyleSheet"):
            continue
        label.setStyleSheet(
            f"QLabel#{name} {{ "
            f"color: {COLOR_MUTED}; "
            "font-style: italic; "
            "padding: 1px 0; "
            "}"
        )


def _set_label_text(dock, name: str, text: str) -> None:
    label = getattr(dock, name, None)
    if label is not None and hasattr(label, "setText"):
        label.setText(text)


def _set_spinbox_suffix(dock, name: str, suffix: str) -> None:
    spinbox = getattr(dock, name, None)
    if spinbox is not None and hasattr(spinbox, "setSuffix"):
        spinbox.setSuffix(suffix)


def _move_clear_database_to_actions_menu(dock) -> None:
    if hasattr(dock, "databaseActionsButton"):
        return

    clear_button = getattr(dock, "clearDatabaseButton", None)
    output_layout = getattr(dock, "outputGroupLayout", None)
    if clear_button is None or output_layout is None:
        return

    from qgis.PyQt.QtCore import Qt
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


def _move_help_label_to_tooltip(label, *widgets) -> None:
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


def _move_store_section_under_fetch(dock) -> None:
    outer_layout = getattr(dock, "verticalLayout", None)
    activities_layout = getattr(dock, "activitiesGroupLayout", None)
    if outer_layout is None or activities_layout is None:
        return
    if dock.outputGroupBox.parent() is dock.activitiesGroupBox:
        return
    outer_layout.removeWidget(dock.outputGroupBox)
    dock.outputGroupBox.setParent(dock.activitiesGroupBox)
    activities_layout.addWidget(dock.outputGroupBox)


def _move_load_layers_to_visualize(dock) -> None:
    output_layout = getattr(dock, "outputGroupLayout", None)
    style_layout = getattr(dock, "styleGroupLayout", None)
    if output_layout is None or style_layout is None:
        return
    if dock.loadLayersButton.parent() is dock.styleGroupBox:
        return
    output_layout.removeWidget(dock.loadLayersButton)
    dock.loadLayersButton.setParent(dock.styleGroupBox)
    style_layout.insertWidget(0, dock.loadLayersButton)


def _move_temporal_controls_to_visualize(dock) -> None:
    analysis_layout = getattr(dock, "analysisWorkflowLayout", None)
    style_layout = getattr(dock, "styleGroupLayout", None)
    temporal_row = getattr(dock, "analysisTemporalModeRow", None)
    temporal_help = getattr(dock, "temporalHelpLabel", None)
    if (
        analysis_layout is None
        or style_layout is None
        or temporal_row is None
        or temporal_help is None
    ):
        return
    if temporal_row.parent() is dock.styleGroupBox:
        return
    analysis_layout.removeWidget(temporal_row)
    analysis_layout.removeWidget(temporal_help)
    temporal_row.setParent(dock.styleGroupBox)
    temporal_help.setParent(dock.styleGroupBox)
    style_layout.addWidget(temporal_row)
    style_layout.addWidget(temporal_help)


__all__ = [
    "configure_local_first_backing_controls",
    "configure_local_first_spinbox_unit_copy",
]
