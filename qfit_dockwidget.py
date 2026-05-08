import logging
import os
import sqlite3
from collections.abc import Callable
from dataclasses import replace
from datetime import date

logger = logging.getLogger(__name__)

from qgis.core import QgsApplication, QgsProject
from qgis.PyQt import uic
from qgis.PyQt.QtCore import QDate, Qt, QUrl
from qgis.PyQt.QtGui import QDesktopServices
from qgis.PyQt.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QDockWidget,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .activities.domain.activity_query import (
    DEFAULT_SORT_LABEL,
    DETAILED_ROUTE_FILTER_ANY,
    DETAILED_ROUTE_FILTER_MISSING,
    DETAILED_ROUTE_FILTER_PRESENT,
    SORT_OPTIONS,
)
from .activities.application import (
    ActivitySelectionState,
    ActivityTypeOptionsResult,
    build_activity_preview_request,
    build_activity_preview_selection_state,
    build_activity_type_options_from_activities,
    build_activity_type_options_from_records,
)
from .activities.application.clear_database_messages import (
    build_clear_database_confirmation_body,
    build_clear_database_confirmation_title,
    build_clear_database_delete_failure_error_title,
    build_clear_database_delete_failure_status,
    build_clear_database_load_workflow_error_title,
    build_missing_output_path_error,
)
from .activities.application.layer_summary import (
    build_cleared_activities_summary,
    build_last_sync_summary,
    build_loaded_activities_summary,
    build_stored_activities_summary,
)
from .activities.application.load_workflow import LoadWorkflowError
from .activities.application.sync_strategy import ActivitySyncMode, plan_activity_sync
from .activities.application.store_task import build_store_task
from .analysis.infrastructure.activity_heatmap_layer import (
    ACTIVITY_HEATMAP_LAYER_NAME,
)
from .analysis.application.analysis_request_builder import (
    build_apply_analysis_configuration_inputs,
)
from .analysis.infrastructure.frequent_start_points_layer import (
    FREQUENT_STARTING_POINTS_LAYER_NAME,
)
from .atlas.export_service import (
    AtlasExportResult,
    AtlasExportService,
)
from .atlas.profile_style import build_native_profile_plot_style_from_settings
from .ui.application import (
    ApplyVisualizationAction,
    DockActionDispatcher,
    DockAtlasExportRequest,
    DockAtlasWorkflowCoordinator,
    DockFetchCompletionRequest,
    DockFetchRequest,
    DockRuntimeStore,
    DockVisualWorkflowCoordinator,
    DockVisualWorkflowRequest,
    RunAnalysisAction,
    build_dock_summary_status,
    build_startup_wizard_progress_facts,
    build_visual_layer_refs,
    build_wizard_filter_description,
    build_wizard_progress_facts_from_runtime_state,
    ensure_wizard_settings,
    load_wizard_settings,
    save_last_step_index,
    step_index_for_key,
    build_visual_workflow_background_inputs,
    build_visual_workflow_selection_state_handoff,
    build_visual_workflow_settings_snapshot,
)
from .ui.contextual_help import ContextualHelpBinder, build_dock_help_entries
from .detailed_route_strategy import (
    DETAILED_ROUTE_STRATEGY_MISSING,
    detailed_route_strategy_labels,
)
from .mapbox_config import (
    TILE_MODES,
    MapboxConfigError,
    background_preset_names,
    preset_requires_custom_style,
)
from .visualization.application import (
    LayerRefs,
    build_background_map_failure_status,
    build_background_map_failure_title,
)
from .providers.domain.provider import ProviderError
from .providers.infrastructure.strava_provider import StravaProvider
from .visualization.application import DEFAULT_TEMPORAL_MODE_LABEL, temporal_mode_labels
from .ui.dockwidget_dependencies import DockWidgetDependencies, build_dockwidget_dependencies
from .ui.dock_startup_coordinator import DockStartupCoordinator
from .ui.workflow_section_coordinator import WorkflowSectionCoordinator
from .configuration.application.connection_status import build_strava_connection_status
from .configuration.application.dock_settings_bindings import build_dock_settings_bindings
from .configuration.application.ui_settings_binding import load_bindings, save_bindings
from .sync_repository import SyncRepository

FORM_CLASS, _ = uic.loadUiType(
    __import__("os").path.join(__import__("os").path.dirname(__file__), "qfit_dockwidget_base.ui")
)


def _fetch_status_for_sync_plan(status_text, sync_plan):
    if sync_plan.mode != ActivitySyncMode.INCREMENTAL_UPDATE or sync_plan.after_epoch is None:
        return status_text
    return "Fetching recent activities from Strava with GeoPackage sync overlap…"


class QfitDockWidget(QDockWidget, FORM_CLASS):
    SETTINGS_PREFIX = "qfit"
    LEGACY_SETTINGS_PREFIX = "QFIT"
    DEFAULT_DOCK_FEATURES = (
        QDockWidget.DockWidgetClosable
        | QDockWidget.DockWidgetMovable
        | QDockWidget.DockWidgetFloatable
    )
    STARTUP_ALLOWED_AREAS = Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea

    def __init__(
        self,
        iface,
        parent=None,
        dependencies: DockWidgetDependencies | None = None,
        open_configuration: Callable[[], None] | None = None,
    ):
        if parent is None and iface is not None and hasattr(iface, "mainWindow"):
            parent = iface.mainWindow()
        super().__init__(parent)
        self.iface = iface
        self._open_configuration = open_configuration
        self._runtime_state_store = DockRuntimeStore()
        self._atlas_export_completed = False
        self._atlas_export_output_path = None
        self._atlas_export_task_output_path = None
        self._dependencies = dependencies or build_dockwidget_dependencies(iface)
        self._bind_dependencies(self._dependencies)
        self.setupUi(self)
        self._workflow_section_coordinator = WorkflowSectionCoordinator(self)
        self._dock_startup_coordinator = DockStartupCoordinator(
            self,
            workflow_section_coordinator=self._workflow_section_coordinator,
        )
        self._startup_result = self._dock_startup_coordinator.run()
        self._dock_action_dispatcher = DockActionDispatcher(
            visual_apply=self.visual_apply,
            save_settings=self._save_settings,
            run_analysis=self._apply_analysis_configuration,
        )
        self._dock_visual_workflow = DockVisualWorkflowCoordinator(
            dispatcher=self._dock_action_dispatcher,
        )
        self._install_live_local_first_dock()

    def _ensure_wizard_settings(self):
        """Persist first-launch wizard defaults for the #609 dock migration."""

        return ensure_wizard_settings(self.settings)

    def _persist_wizard_step_index(
        self,
        index: int,
        *,
        user_selected: bool = True,
    ) -> int:
        """Persist the optional #609 wizard shell's current step."""

        return save_last_step_index(
            self.settings,
            index,
            user_selected=user_selected,
        )

    def _persist_wizard_startup_step_index(self, index: int) -> int:
        """Persist a startup-derived wizard step without marking it user-chosen."""

        return save_last_step_index(self.settings, index, user_selected=False)

    def _show_connection_configuration_hint(self) -> None:
        """Open or describe the dedicated qfit configuration dialog for wizard users."""

        open_configuration = getattr(self, "_open_configuration", None)
        if open_configuration is not None:
            open_configuration()
            self._set_status("qfit configuration opened; save credentials to continue.")
            return

        self._show_info(
            "Configure qfit connection",
            "Open qfit → Configuration from the QGIS plugin menu to edit Strava "
            "credentials, then return to the dock to continue the workflow.",
        )
        self._set_status("Open qfit → Configuration to edit Strava credentials.")

    def refresh_configuration_from_settings(self) -> None:
        """Reload saved configuration and refresh live wizard connection state."""

        self._load_settings()
        self._update_connection_status()
        self._set_status("Configuration saved; qfit dock connection state refreshed.")

    def _run_wizard_sync_step(self) -> None:
        """Run the next concrete action for the wizard synchronization step."""

        if self.runtime_state.activities:
            self.on_load_clicked()
            return
        self.on_refresh_clicked()

    def _run_wizard_map_step(self) -> None:
        """Run the next concrete action for the wizard map-and-filters step."""

        if self.runtime_state.activities_layer is None:
            self.on_load_layers_clicked()
            return
        self.on_apply_filters_clicked()

    def _current_wizard_progress_facts(self):
        """Return render-neutral #609 wizard facts from the live dock state."""

        runtime_state = self._wizard_runtime_state_with_selected_output_path()
        atlas_exported = bool(getattr(self, "_atlas_export_completed", False))
        atlas_export_output_path = self._current_wizard_atlas_output_path(
            runtime_state=runtime_state,
            atlas_exported=atlas_exported,
        )
        (
            background_enabled,
            background_layer_loaded,
            background_name,
        ) = self._current_wizard_background_facts(runtime_state)
        (
            filters_active,
            filtered_activity_count,
            filter_description,
        ) = self._current_wizard_filter_facts()
        return build_wizard_progress_facts_from_runtime_state(
            runtime_state,
            connection_configured=self._has_configured_strava_connection(),
            atlas_exported=atlas_exported,
            atlas_output_path=atlas_export_output_path,
            background_enabled=background_enabled,
            background_layer_loaded=background_layer_loaded,
            background_name=background_name,
            filters_active=filters_active,
            filtered_activity_count=filtered_activity_count,
            filter_description=filter_description,
            activity_style_preset=self._current_wizard_activity_style_preset(),
            last_sync_date=self._current_wizard_last_sync_date(),
        )

    def _current_wizard_last_sync_date(self) -> str | None:
        """Return the persisted last sync date for wizard status summaries."""

        settings = getattr(self, "settings", None)
        get_value = getattr(settings, "get", None)
        if not callable(get_value):
            return None
        value = get_value("last_sync_date", None)
        if not isinstance(value, str):
            return None
        return value.strip() or None

    def _wizard_runtime_state_with_selected_output_path(self):
        """Reflect the visible GeoPackage path in wizard availability facts."""

        runtime_state = self.runtime_state
        selected_output_path = self._widget_text("outputPathLineEdit").strip()
        if not selected_output_path or selected_output_path == runtime_state.output_path:
            return runtime_state
        return replace(runtime_state, output_path=selected_output_path)

    def _on_output_path_changed(self, value: str) -> None:
        """Keep live local-load actions in sync with the selected GeoPackage path."""

        self._runtime_store().select_output_path((value or "").strip() or None)
        self._refresh_live_dock_navigation_from_runtime()

    def _current_wizard_activity_style_preset(self) -> str | None:
        """Return current activity style copy for the optional wizard map page."""

        preset_combo = getattr(self, "stylePresetComboBox", None)
        if preset_combo is None or not hasattr(preset_combo, "currentText"):
            return None
        try:
            preset_name = preset_combo.currentText()
        except RuntimeError:
            logger.debug("Failed to read wizard activity style preset", exc_info=True)
            return None
        if not isinstance(preset_name, str):
            return None
        stripped = preset_name.strip()
        return stripped or None

    def _current_wizard_background_facts(self, runtime_state) -> tuple[bool, bool, str | None]:
        """Return current basemap facts for the optional wizard map page."""

        background_layer_loaded = runtime_state.background_layer is not None
        if background_layer_loaded:
            return True, True, self._current_wizard_layer_name(
                runtime_state.background_layer,
                log_message="Failed to read wizard background layer name",
            )

        checkbox = getattr(self, "backgroundMapCheckBox", None)
        background_enabled = bool(
            checkbox is not None
            and hasattr(checkbox, "isChecked")
            and checkbox.isChecked()
        )
        if not background_enabled:
            return False, False, None
        return True, False, self._current_wizard_background_name()

    def _current_wizard_layer_name(self, layer, *, log_message: str) -> str | None:
        if layer is None:
            return None
        name_method = getattr(layer, "name", None)
        if not callable(name_method):
            return None
        try:
            layer_name = name_method()
        except RuntimeError:
            logger.debug(log_message, exc_info=True)
            return None
        if not isinstance(layer_name, str):
            return None
        stripped = layer_name.strip()
        return stripped or None

    def _current_wizard_background_name(self) -> str | None:
        preset_combo = getattr(self, "backgroundPresetComboBox", None)
        if preset_combo is None or not hasattr(preset_combo, "currentText"):
            return None
        try:
            preset_name = preset_combo.currentText()
        except RuntimeError:
            logger.debug("Failed to read wizard background preset", exc_info=True)
            return None
        if not isinstance(preset_name, str):
            return None
        stripped = preset_name.strip()
        return stripped or None

    def _current_wizard_filter_facts(self) -> tuple[bool, int | None, str | None]:
        """Return the current map-filter facts the optional wizard can summarize."""

        layer_filter_facts = self._current_wizard_layer_filter_facts()
        if layer_filter_facts is not None:
            filters_active, filtered_activity_count = layer_filter_facts
            filter_description = "layer subset" if filters_active else None
            return filters_active, filtered_activity_count, filter_description

        activities = tuple(self.runtime_state.activities)
        if not activities:
            return False, None, None
        preview_request = self._current_activity_preview_request()
        selection_state = build_activity_preview_selection_state(preview_request)
        filters_active = selection_state.filtered_count != len(activities)
        if not filters_active:
            return False, None, None
        return (
            True,
            selection_state.filtered_count,
            build_wizard_filter_description(preview_request),
        )

    def _current_wizard_layer_filter_facts(self) -> tuple[bool, int | None] | None:
        layer = self.runtime_state.activities_layer
        if layer is None or not hasattr(layer, "subsetString"):
            return None
        try:
            subset = (layer.subsetString() or "").strip()
        except RuntimeError:
            logger.debug("Failed to read activity layer subset", exc_info=True)
            return None
        if not subset:
            return False, None
        return True, self._current_wizard_layer_feature_count(layer)

    def _current_wizard_layer_feature_count(self, layer) -> int | None:
        if not hasattr(layer, "featureCount"):
            return None
        try:
            count = layer.featureCount()
        except RuntimeError:
            logger.debug("Failed to read activity layer feature count", exc_info=True)
            return None
        if not isinstance(count, int):
            return None
        return max(count, 0)

    def _current_wizard_atlas_output_path(self, *, runtime_state, atlas_exported: bool):
        """Return the atlas output path the optional wizard should describe."""

        if runtime_state.atlas_export_task is not None:
            return (
                getattr(self, "_atlas_export_task_output_path", None)
                or self._widget_text("atlasPdfPathLineEdit")
            )
        completed_output_path = getattr(self, "_atlas_export_output_path", None)
        if atlas_exported and completed_output_path:
            return completed_output_path
        return self._widget_text("atlasPdfPathLineEdit")

    def _build_wizard_shell_from_runtime(self, *, parent=None):
        """Build the optional #609 wizard shell from current dock runtime facts.

        The shell is not installed into the production dock yet; this seam lets
        the eventual wizard-style dock swap create a live composition with
        persisted navigation and concrete CTA callbacks without coupling the
        reusable wizard widgets to ``QfitDockWidget``.
        """

        from .ui.dockwidget.wizard_composition import (
            WizardActionCallbacks,
            build_placeholder_wizard_shell,
            connect_wizard_action_callbacks,
        )

        progress_facts = self._current_wizard_progress_facts()
        wizard_settings = load_wizard_settings(self.settings)
        startup_progress_facts = build_startup_wizard_progress_facts(
            progress_facts,
            wizard_settings,
        )
        self._persist_startup_wizard_step_if_needed(
            progress_facts=progress_facts,
            startup_progress_facts=startup_progress_facts,
        )
        composition = build_placeholder_wizard_shell(
            parent=self if parent is None else parent,
            progress_facts=startup_progress_facts,
            wizard_settings=wizard_settings,
            use_step_pages=True,
            on_current_step_changed=self._persist_wizard_step_index,
        )
        self._wizard_shell_composition = connect_wizard_action_callbacks(
            composition,
            WizardActionCallbacks(
                configure_connection=self._show_connection_configuration_hint,
                sync_activities=self._run_wizard_sync_step,
                sync_saved_routes=self.on_sync_routes_clicked,
                clear_database=self.on_clear_database_clicked,
                load_activity_layers=self.on_load_layers_clicked,
                apply_map_filters=self._run_wizard_map_step,
                run_analysis=self.on_run_analysis_clicked,
                clear_analysis=self.on_clear_analysis_clicked,
                set_analysis_mode=self._set_wizard_analysis_mode,
                export_atlas=self.on_generate_atlas_pdf_clicked,
                update_atlas_document_settings=self._update_atlas_document_settings,
            ),
        )
        self._sync_atlas_document_settings_controls(self._wizard_shell_composition)
        self._install_wizard_style_controls(self._wizard_shell_composition)
        self._install_wizard_filter_controls(self._wizard_shell_composition)
        self._bind_wizard_analysis_mode_controls(self._wizard_shell_composition)
        return self._wizard_shell_composition

    def _build_local_first_dock_from_runtime(self, *, parent=None):
        """Build the #748 local-first dock composition from live runtime facts.

        This keeps the production swap small: the reusable local-first shell can
        now be assembled with the same mature workflow callbacks as the wizard,
        while keeping each action independent instead of routing through a
        linear next-step helper.
        """

        from .ui.dockwidget.local_first_composition import (
            WizardActionCallbacks,
            build_local_first_dock_composition,
            connect_local_first_action_callbacks,
        )

        composition = build_local_first_dock_composition(
            parent=self if parent is None else parent,
            progress_facts=self._current_wizard_progress_facts(),
            atlas_title=self.atlasTitleLineEdit.text(),
            atlas_subtitle=self.atlasSubtitleLineEdit.text(),
        )
        self._local_first_dock_composition = connect_local_first_action_callbacks(
            composition,
            WizardActionCallbacks(
                configure_connection=self._show_connection_configuration_hint,
                sync_activities=self._run_wizard_sync_step,
                sync_saved_routes=self.on_sync_routes_clicked,
                clear_database=self.on_clear_database_clicked,
                load_activity_layers=self.on_load_layers_clicked,
                apply_map_filters=self.on_apply_filters_clicked,
                run_analysis=self.on_run_analysis_clicked,
                clear_analysis=self.on_clear_analysis_clicked,
                set_analysis_mode=self._set_wizard_analysis_mode,
                export_atlas=self.on_generate_atlas_pdf_clicked,
                update_atlas_document_settings=self._update_atlas_document_settings,
            ),
        )
        self._install_wizard_style_controls(self._local_first_dock_composition)
        self._install_wizard_filter_controls(self._local_first_dock_composition)
        self._install_local_first_basemap_controls(self._local_first_dock_composition)
        self._install_local_first_storage_controls(self._local_first_dock_composition)
        self._bind_wizard_analysis_mode_controls(self._local_first_dock_composition)
        return self._local_first_dock_composition

    def _sync_atlas_document_settings_controls(self, composition) -> None:
        atlas_content = getattr(composition, "atlas_content", None)
        set_document_settings = getattr(atlas_content, "set_document_settings", None)
        if not callable(set_document_settings):
            return
        set_document_settings(
            atlas_title=self.atlasTitleLineEdit.text(),
            atlas_subtitle=self.atlasSubtitleLineEdit.text(),
        )

    def _update_atlas_document_settings(self, atlas_title: str, atlas_subtitle: str) -> None:
        """Mirror visible atlas-page title fields into the export settings widgets."""

        title_line_edit = getattr(self, "atlasTitleLineEdit", None)
        subtitle_line_edit = getattr(self, "atlasSubtitleLineEdit", None)
        title_changed = title_line_edit is not None and title_line_edit.text() != atlas_title
        subtitle_changed = (
            subtitle_line_edit is not None
            and subtitle_line_edit.text() != atlas_subtitle
        )
        if title_line_edit is not None:
            title_line_edit.setText(atlas_title)
        if subtitle_line_edit is not None:
            subtitle_line_edit.setText(atlas_subtitle)
        if title_changed or subtitle_changed:
            self._mark_atlas_export_stale()
            self._refresh_summary_status()

    def _persist_startup_wizard_step_if_needed(
        self,
        *,
        progress_facts,
        startup_progress_facts,
    ) -> None:
        startup_key = startup_progress_facts.preferred_current_key
        if startup_key is None or startup_key == progress_facts.preferred_current_key:
            return
        self._persist_wizard_startup_step_index(step_index_for_key(startup_key))

    def _install_wizard_filter_controls(self, composition) -> None:
        """Move the live map-filter controls into the wizard map page."""

        map_content = getattr(composition, "map_content", None)
        filter_group = getattr(self, "filterGroupBox", None)
        if map_content is None or filter_group is None:
            return
        installed_target = getattr(self, "_wizard_filter_controls_installed_target", None)
        current_target = id(map_content)
        if getattr(self, "_wizard_filter_controls_installed", False) and (
            installed_target == current_target
        ):
            return
        filter_controls_layout = getattr(map_content, "filter_controls_layout", None)
        if not callable(filter_controls_layout):
            return

        self._remove_widget_from_current_layout(filter_group)
        parent_panel = getattr(map_content, "filter_controls_panel", map_content)
        if hasattr(filter_group, "setParent"):
            filter_group.setParent(parent_panel)
        filter_controls_layout().addWidget(filter_group)
        if hasattr(filter_group, "show"):
            filter_group.show()
        elif hasattr(filter_group, "setVisible"):
            filter_group.setVisible(True)
        map_content.set_filter_controls_visible()
        self._wizard_filter_controls_installed = True
        self._wizard_filter_controls_installed_target = current_target

    def _install_wizard_style_controls(self, composition) -> None:
        """Move the live activity-style selector into the wizard map page."""

        map_content = getattr(composition, "map_content", None)
        style_label = getattr(self, "stylePresetLabel", None)
        style_combo = getattr(self, "stylePresetComboBox", None)
        if map_content is None or style_label is None or style_combo is None:
            return
        installed_target = getattr(self, "_wizard_style_controls_installed_target", None)
        current_target = id(map_content)
        if getattr(self, "_wizard_style_controls_installed", False) and (
            installed_target == current_target
        ):
            return
        style_controls_layout = getattr(map_content, "style_controls_layout", None)
        if not callable(style_controls_layout):
            return

        target_layout = style_controls_layout()
        parent_panel = getattr(map_content, "style_controls_panel", map_content)
        for widget in (style_label, style_combo):
            self._remove_widget_from_current_layout(widget)
            if hasattr(widget, "setParent"):
                widget.setParent(parent_panel)
            target_layout.addWidget(widget)
            if hasattr(widget, "show"):
                widget.show()
            elif hasattr(widget, "setVisible"):
                widget.setVisible(True)
        set_visible = getattr(map_content, "set_style_controls_visible", None)
        if callable(set_visible):
            set_visible()
        self._wizard_style_controls_installed = True
        self._wizard_style_controls_installed_target = current_target

    def _remove_widget_from_current_layout(self, widget) -> None:
        parent_widget = (
            widget.parentWidget() if hasattr(widget, "parentWidget") else None
        )
        parent_layout = parent_widget.layout() if parent_widget is not None else None
        if parent_layout is not None and hasattr(parent_layout, "removeWidget"):
            parent_layout.removeWidget(widget)

    def _install_local_first_basemap_controls(self, composition) -> None:
        """Expose the backing Mapbox basemap controls in the Settings tab."""

        settings_content = getattr(composition, "connection_content", None)
        background_group = getattr(self, "backgroundGroupBox", None)
        if settings_content is None or background_group is None:
            return
        installed_target = getattr(self, "_local_first_basemap_controls_installed_target", None)
        current_target = id(settings_content)
        if getattr(self, "_local_first_basemap_controls_installed", False) and (
            installed_target == current_target
        ):
            return

        layout_getter = getattr(settings_content, "outer_layout", None)
        layout = layout_getter() if callable(layout_getter) else None
        if layout is None or not hasattr(layout, "addWidget"):
            return

        self._remove_widget_from_current_layout(background_group)
        if hasattr(background_group, "setParent"):
            background_group.setParent(settings_content)
        if hasattr(background_group, "setTitle"):
            background_group.setTitle("Mapbox basemap")
        layout.addWidget(background_group)
        if hasattr(background_group, "show"):
            background_group.show()
        elif hasattr(background_group, "setVisible"):
            background_group.setVisible(True)

        self._local_first_basemap_controls_installed = True
        self._local_first_basemap_controls_installed_target = current_target

    def _install_local_first_storage_controls(self, composition) -> None:
        """Expose the backing GeoPackage storage controls in the Settings tab."""

        settings_content = getattr(composition, "connection_content", None)
        storage_group = getattr(self, "outputGroupBox", None)
        if settings_content is None or storage_group is None:
            return
        installed_target = getattr(
            self,
            "_local_first_storage_controls_installed_target",
            None,
        )
        current_target = id(settings_content)
        if getattr(self, "_local_first_storage_controls_installed", False) and (
            installed_target == current_target
        ):
            return

        layout_getter = getattr(settings_content, "outer_layout", None)
        layout = layout_getter() if callable(layout_getter) else None
        if layout is None or not hasattr(layout, "addWidget"):
            return

        self._remove_widget_from_current_layout(storage_group)
        if hasattr(storage_group, "setParent"):
            storage_group.setParent(settings_content)
        if hasattr(storage_group, "setTitle"):
            storage_group.setTitle("Data storage")
        layout.addWidget(storage_group)
        if hasattr(storage_group, "show"):
            storage_group.show()
        elif hasattr(storage_group, "setVisible"):
            storage_group.setVisible(True)

        self._local_first_storage_controls_installed = True
        self._local_first_storage_controls_installed_target = current_target

    def _bind_wizard_analysis_mode_controls(self, composition) -> None:
        """Expose the hidden backing analysis selector in the live wizard path."""

        analysis_content = getattr(composition, "analysis_content", None)
        mode_combo = getattr(self, "analysisModeComboBox", None)
        if analysis_content is None or mode_combo is None:
            return
        options = tuple(
            mode_combo.itemText(index)
            for index in range(mode_combo.count())
            if mode_combo.itemText(index) != "None"
        )
        if not options:
            return
        selected_mode = mode_combo.currentText()
        if selected_mode == "None" or selected_mode not in options:
            selected_mode = options[0]
        analysis_content.set_analysis_mode_options(options, selected=selected_mode)
        self._set_wizard_analysis_mode(selected_mode)

    def _set_wizard_analysis_mode(self, mode: str) -> None:
        """Mirror the wizard analysis mode selector into the backing dock combo."""

        mode_combo = getattr(self, "analysisModeComboBox", None)
        if mode_combo is None or not mode:
            return
        mode_combo.setCurrentText(mode)

    def _build_wizard_dock_from_runtime(self, *, parent=None):
        """Build the optional #609 QDockWidget container from runtime facts.

        This is the dock-level seam for the eventual wizard swap: the reusable
        shell composition remains independent, while this helper wraps it in the
        real QDockWidget shape required by the Option B spec.
        """

        from .ui.dockwidget.wizard_dock import build_wizard_dock_widget

        return build_wizard_dock_widget(
            self._build_wizard_shell_from_runtime(parent=parent),
            parent=parent,
        )

    def _install_live_wizard_shell(self) -> None:
        """Make the #609 wizard shell the visible dock path.

        The legacy ``.ui`` controls still back settings and workflow actions, but
        they are no longer the user's default dock surface. Keeping them hidden in
        the existing dock content lets the wizard CTAs reuse the mature workflow
        code while closing the long-scroll UX path from #608.
        """

        if getattr(self, "_wizard_live_path_installed", False):
            return

        parent = getattr(self, "dockWidgetContents", self)
        composition = self._build_wizard_shell_from_runtime(parent=parent)
        shell = getattr(composition, "shell", None)
        if shell is None:
            raise RuntimeError("Wizard shell composition must expose a shell widget")

        outer_layout = getattr(self, "outerLayout", None)
        if outer_layout is None:
            raise RuntimeError("Wizard dock requires the base outer layout")

        self._hide_legacy_scroll_dock_content()
        outer_layout.addWidget(shell)

        self._wizard_live_shell = shell
        self._wizard_live_path_installed = True

    def _install_live_local_first_dock(self) -> None:
        """Make the #748 local-first navigation shell the visible dock path."""

        if getattr(self, "_local_first_live_path_installed", False):
            return

        parent = getattr(self, "dockWidgetContents", self)
        composition = self._build_local_first_dock_from_runtime(parent=parent)
        shell = getattr(composition, "shell", None)
        if shell is None:
            raise RuntimeError("Local-first dock composition must expose a shell widget")

        outer_layout = getattr(self, "outerLayout", None)
        if outer_layout is None:
            raise RuntimeError("Local-first dock requires the base outer layout")

        self._hide_legacy_scroll_dock_content()
        outer_layout.addWidget(shell)

        self._local_first_live_shell = shell
        self._local_first_live_path_installed = True

    def _hide_legacy_scroll_dock_content(self) -> None:
        """Hide the replaced long-scroll dock widgets without deleting them."""

        for widget_name in ("scrollArea", "summaryStatusLabel"):
            widget = getattr(self, widget_name, None)
            if widget is not None and hasattr(widget, "hide"):
                widget.hide()


    def _refresh_wizard_shell_from_runtime(self):
        """Refresh an optional #609 wizard shell composition from dock runtime facts."""

        composition = getattr(self, "_wizard_shell_composition", None)
        if composition is None:
            return None

        from .ui.dockwidget.wizard_composition import refresh_wizard_shell_composition

        self._wizard_shell_composition = refresh_wizard_shell_composition(
            composition,
            progress_facts=self._current_wizard_progress_facts(),
            wizard_settings=load_wizard_settings(self.settings),
        )
        return self._wizard_shell_composition

    def _refresh_local_first_dock_from_runtime(self):
        """Refresh an optional #748 local-first dock composition from runtime facts."""

        composition = getattr(self, "_local_first_dock_composition", None)
        if composition is None:
            return None

        from .ui.dockwidget.local_first_composition import (
            refresh_local_first_dock_composition,
        )

        self._local_first_dock_composition = refresh_local_first_dock_composition(
            composition,
            progress_facts=self._current_wizard_progress_facts(),
        )
        return self._local_first_dock_composition

    def _refresh_live_dock_navigation_from_runtime(self) -> None:
        """Refresh whichever dock navigation composition is installed."""

        self._refresh_wizard_shell_from_runtime()
        self._refresh_local_first_dock_from_runtime()

    def _has_configured_strava_connection(self) -> bool:
        return all(
            self._widget_text(name).strip()
            for name in (
                "clientIdLineEdit",
                "clientSecretLineEdit",
                "refreshTokenLineEdit",
            )
        )

    def _mark_atlas_export_stale(self) -> None:
        self._atlas_export_completed = False
        self._atlas_export_output_path = None
        if self.runtime_state.atlas_export_task is None:
            self._atlas_export_task_output_path = None

    def _runtime_store(self) -> DockRuntimeStore:
        store = getattr(self, "_runtime_state_store", None)
        if store is None:
            store = DockRuntimeStore()
            self._runtime_state_store = store
        return store

    @property
    def runtime_state(self):
        return self._runtime_store().state

    @property
    def activities(self):
        return list(self.runtime_state.activities)

    @activities.setter
    def activities(self, value):
        self._runtime_store().set_activities(value)

    @property
    def output_path(self):
        return self.runtime_state.output_path

    @output_path.setter
    def output_path(self, value):
        self._runtime_store().set_output_path(value)

    @property
    def activities_layer(self):
        return self.runtime_state.layers.activities

    @activities_layer.setter
    def activities_layer(self, value):
        self._runtime_store().set_dataset_layers(
            activities_layer=value,
            starts_layer=self.starts_layer,
            points_layer=self.points_layer,
            atlas_layer=self.atlas_layer,
        )

    @property
    def starts_layer(self):
        return self.runtime_state.layers.starts

    @starts_layer.setter
    def starts_layer(self, value):
        self._runtime_store().set_dataset_layers(
            activities_layer=self.activities_layer,
            starts_layer=value,
            points_layer=self.points_layer,
            atlas_layer=self.atlas_layer,
        )

    @property
    def points_layer(self):
        return self.runtime_state.layers.points

    @points_layer.setter
    def points_layer(self, value):
        self._runtime_store().set_dataset_layers(
            activities_layer=self.activities_layer,
            starts_layer=self.starts_layer,
            points_layer=value,
            atlas_layer=self.atlas_layer,
        )

    @property
    def atlas_layer(self):
        return self.runtime_state.layers.atlas

    @atlas_layer.setter
    def atlas_layer(self, value):
        self._runtime_store().set_dataset_layers(
            activities_layer=self.activities_layer,
            starts_layer=self.starts_layer,
            points_layer=self.points_layer,
            atlas_layer=value,
        )

    @property
    def background_layer(self):
        return self.runtime_state.layers.background

    @background_layer.setter
    def background_layer(self, value):
        self._runtime_store().set_background_layer(value)

    @property
    def analysis_layer(self):
        return self.runtime_state.layers.analysis

    @analysis_layer.setter
    def analysis_layer(self, value):
        self._runtime_store().set_analysis_layer(value)

    @property
    def last_fetch_context(self):
        return dict(self.runtime_state.last_fetch_context)

    @last_fetch_context.setter
    def last_fetch_context(self, value):
        self._runtime_store().set_last_fetch_context(value)

    @property
    def _fetch_task(self):
        return self.runtime_state.tasks.fetch

    @_fetch_task.setter
    def _fetch_task(self, value):
        self._runtime_store().set_fetch_task(value)

    @property
    def _store_task(self):
        return self.runtime_state.tasks.store

    @_store_task.setter
    def _store_task(self, value):
        self._runtime_store().set_store_task(value)

    @property
    def _route_sync_task(self):
        return self.runtime_state.tasks.route_sync

    @_route_sync_task.setter
    def _route_sync_task(self, value):
        self._runtime_store().set_route_sync_task(value)

    @property
    def _atlas_export_task(self):
        return self.runtime_state.tasks.atlas_export

    @_atlas_export_task.setter
    def _atlas_export_task(self, value):
        self._runtime_store().set_atlas_export_task(value)

    def _remove_stale_qfit_layers(self):
        """Remove stale qfit project layers before startup signals begin firing."""
        self.project_hygiene_service.remove_stale_qfit_layers()

    def _apply_contextual_help(self):
        for name in [
            "backgroundHelpLabel",
            "analysisHelpLabel",
            "publishHelpLabel",
            "temporalHelpLabel",
        ]:
            label = getattr(self, name, None)
            if label is not None:
                label.hide()

        ContextualHelpBinder(self).apply(build_dock_help_entries())

    def _wire_events(self):
        self.openAuthorizeButton.clicked.connect(self.on_open_authorize_clicked)
        self.exchangeCodeButton.clicked.connect(self.on_exchange_code_clicked)
        self.browseButton.clicked.connect(self.on_browse_clicked)
        self.refreshButton.clicked.connect(self.on_refresh_clicked)
        self.backfillMissingDetailedRoutesButton.clicked.connect(self.on_backfill_missing_detailed_routes_clicked)
        self.loadButton.clicked.connect(self.on_load_clicked)
        if getattr(self, "syncRoutesButton", None) is not None:
            self.syncRoutesButton.clicked.connect(self.on_sync_routes_clicked)
        self.loadLayersButton.clicked.connect(self.on_load_layers_clicked)
        self.clearDatabaseButton.clicked.connect(self.on_clear_database_clicked)
        self.applyFiltersButton.clicked.connect(self.on_apply_filters_clicked)
        self.runAnalysisButton.clicked.connect(self.on_run_analysis_clicked)
        self.loadBackgroundButton.clicked.connect(self.on_load_background_clicked)
        self.backgroundPresetComboBox.currentTextChanged.connect(self.on_background_preset_changed)
        self.detailedStreamsCheckBox.toggled.connect(self._workflow_section_coordinator.update_detailed_fetch_visibility)
        self.writeActivityPointsCheckBox.toggled.connect(self._workflow_section_coordinator.update_point_sampling_visibility)
        self.advancedFetchGroupBox.toggled.connect(self._workflow_section_coordinator.update_advanced_fetch_visibility)
        self.atlasPdfBrowseButton.clicked.connect(self.on_atlas_pdf_browse_clicked)
        self.generateAtlasPdfButton.clicked.connect(self.on_generate_atlas_pdf_clicked)
        self.clientIdLineEdit.textChanged.connect(self._update_connection_status)
        self.clientSecretLineEdit.textChanged.connect(self._update_connection_status)
        self.refreshTokenLineEdit.textChanged.connect(self._update_connection_status)
        self.outputPathLineEdit.textChanged.connect(self._on_output_path_changed)

        preview_inputs = [
            self.activityTypeComboBox.currentTextChanged,
            self.activitySearchLineEdit.textChanged,
            self.dateFromEdit.dateChanged,
            self.dateToEdit.dateChanged,
            self.minDistanceSpinBox.valueChanged,
            self.maxDistanceSpinBox.valueChanged,
            self.detailedRouteStatusComboBox.currentIndexChanged,
            self.previewSortComboBox.currentTextChanged,
        ]
        for signal in preview_inputs:
            signal.connect(self._refresh_activity_preview)

    def _configure_background_preset_options(self):
        self.backgroundPresetComboBox.clear()
        for preset_name in background_preset_names():
            self.backgroundPresetComboBox.addItem(preset_name)

    def _configure_detailed_route_filter_options(self):
        legacy_checkbox = getattr(self, "detailedOnlyCheckBox", None)
        combo = getattr(self, "detailedRouteStatusComboBox", None)
        if combo is None:
            combo = QComboBox(legacy_checkbox.parentWidget())
            combo.setObjectName("detailedRouteStatusComboBox")
            layout = legacy_checkbox.parentWidget().layout()
            if layout is not None and hasattr(layout, "replaceWidget"):
                layout.replaceWidget(legacy_checkbox, combo)
            legacy_checkbox.hide()
            self.detailedRouteStatusComboBox = combo
        combo.clear()
        combo.addItem("Any routes", DETAILED_ROUTE_FILTER_ANY)
        combo.addItem("Detailed routes only", DETAILED_ROUTE_FILTER_PRESENT)
        combo.addItem("Missing detailed routes", DETAILED_ROUTE_FILTER_MISSING)
        combo.setToolTip("Filter activities by detailed-route availability")
        self.tileModeComboBox.clear()
        for mode in TILE_MODES:
            self.tileModeComboBox.addItem(mode)

    def _configure_detailed_route_strategy_options(self):
        combo = getattr(self, "detailedRouteStrategyComboBox", None)
        if combo is None:
            return
        combo.clear()
        for label in detailed_route_strategy_labels():
            combo.addItem(label)

    def _configure_preview_sort_options(self):
        self.previewSortComboBox.clear()
        for label in SORT_OPTIONS:
            self.previewSortComboBox.addItem(label)

    def _configure_temporal_mode_options(self):
        outer_layout = self.temporalModeLabel.parentWidget().layout()
        if hasattr(outer_layout, "setSpacing"):
            outer_layout.setSpacing(6)
        if isinstance(outer_layout, QGridLayout):
            outer_layout.setSpacing(6)
        self.temporalModeComboBox.setSizeAdjustPolicy(
            QComboBox.AdjustToMinimumContentsLengthWithIcon
        )
        self.temporalModeComboBox.setMinimumContentsLength(10)
        self.temporalHelpLabel.setMargin(2)
        self.temporalModeComboBox.clear()
        for label in temporal_mode_labels():
            self.temporalModeComboBox.addItem(label)
        self.temporalModeComboBox.setCurrentText(DEFAULT_TEMPORAL_MODE_LABEL)
        self.temporalModeComboBox.setMinimumContentsLength(10)
        self.temporalModeComboBox.hide()
        self.temporalModeLabel.hide()
        self.temporalHelpLabel.hide()
        temporal_row = getattr(self, "analysisTemporalModeRow", None)
        if temporal_row is not None:
            temporal_row.hide()

    def _configure_analysis_mode_options(self):
        content_widget = getattr(self, "analysisSectionContentWidget", self.analysisWorkflowGroupBox)
        content_layout = content_widget.layout() if content_widget is not None else None

        row = QWidget(content_widget or self.analysisWorkflowGroupBox)
        row.setObjectName("analysisModeRow")
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        label = QLabel("Analysis", row)
        label.setObjectName("analysisModeLabel")
        layout.addWidget(label)

        combo = QComboBox(row)
        combo.setObjectName("analysisModeComboBox")
        combo.addItem("None")
        combo.addItem("Most frequent starting points")
        combo.addItem("Heatmap")
        layout.addWidget(combo)

        button = QPushButton("Run analysis", row)
        button.setObjectName("runAnalysisButton")
        layout.addWidget(button)
        layout.addStretch(1)

        if content_layout is not None:
            content_layout.insertWidget(0, row)
        else:
            self.analysisWorkflowLayout.insertWidget(0, row)
        self.analysisModeLabel = label
        self.analysisModeComboBox = combo
        self.runAnalysisButton = button

    def _bind_dependencies(self, dependencies: DockWidgetDependencies) -> None:
        self.settings = dependencies.settings
        self.sync_controller = dependencies.sync_controller
        self.analysis_workflow = dependencies.analysis_workflow
        self.atlas_export_controller = dependencies.atlas_export_controller
        self.atlas_export_use_case = dependencies.atlas_export_use_case
        self.layer_gateway = dependencies.layer_gateway
        self.background_controller = dependencies.background_controller
        self.project_hygiene_service = dependencies.project_hygiene_service
        self.store_workflow = getattr(dependencies, "store_workflow", dependencies.load_workflow)
        self.dataset_load_workflow = getattr(
            dependencies,
            "dataset_load_workflow",
            dependencies.load_workflow,
        )
        self.clear_database_workflow = getattr(
            dependencies,
            "clear_database_workflow",
            dependencies.load_workflow,
        )
        self.load_workflow = dependencies.load_workflow
        self.visual_apply = dependencies.visual_apply
        self.atlas_export_service = dependencies.atlas_export_service
        self.activity_workflow = dependencies.activity_workflow
        self.atlas_workflow = getattr(dependencies, "atlas_workflow", None)
        self.cache = dependencies.cache

    def _store_activities_workflow(self):
        return getattr(self, "store_workflow", None) or self.load_workflow

    def _dataset_load_workflow_service(self):
        return getattr(self, "dataset_load_workflow", None) or self.load_workflow

    def _clear_database_workflow_service(self):
        return getattr(self, "clear_database_workflow", None) or self.load_workflow

    def _atlas_workflow_service(self):
        atlas_workflow = getattr(self, "atlas_workflow", None)
        if atlas_workflow is None:
            atlas_workflow = DockAtlasWorkflowCoordinator(
                atlas_export_use_case=self.atlas_export_use_case,
            )
            self.atlas_workflow = atlas_workflow
        return atlas_workflow

    @staticmethod
    def _set_combo_value(combo_box, value, default_text) -> None:
        selected = default_text if value in (None, "") else str(value)
        index = combo_box.findText(selected)
        if index < 0:
            index = combo_box.findText(default_text)
        combo_box.setCurrentIndex(max(index, 0))

    @staticmethod
    def _set_bool_value(check_box, value, default: bool) -> None:
        if isinstance(value, str):
            check_box.setChecked(value.lower() in ("1", "true", "yes", "on"))
            return
        if value is None:
            check_box.setChecked(default)
            return
        check_box.setChecked(bool(value))

    @staticmethod
    def _set_int_value(spin_box, value, default: int) -> None:
        try:
            spin_box.setValue(int(value))
        except (TypeError, ValueError):
            spin_box.setValue(int(default))

    @staticmethod
    def _set_combo_data_value(combo_box, value, default: str) -> None:
        target = value if value not in (None, "") else default
        index = combo_box.findData(target)
        if index < 0:
            index = combo_box.findData(default)
        if index < 0:
            index = 0
        combo_box.setCurrentIndex(index)

    @staticmethod
    def _set_float_value(spin_box, value, default: float) -> None:
        try:
            spin_box.setValue(float(value))
        except (TypeError, ValueError):
            spin_box.setValue(float(default))

    def _default_output_path(self) -> str:
        return os.path.join(os.path.expanduser("~"), "qfit_activities.gpkg")

    def _default_atlas_pdf_path(self) -> str:
        return os.path.join(os.path.expanduser("~"), "qfit_atlas.pdf")

    def _load_settings(self):
        load_bindings(build_dock_settings_bindings(self), self.settings)
        self.authCodeLineEdit.setText("")
        self._sync_background_style_fields(self.backgroundPresetComboBox.currentText(), force=False)

        self._update_last_sync_summary()

    def _save_settings(self):
        save_bindings(build_dock_settings_bindings(self), self.settings)


    def _set_default_dates(self):
        today = QDate.currentDate()
        self.dateFromEdit.setDate(today.addYears(-1))
        self.dateToEdit.setDate(today)

    def on_background_preset_changed(self, preset_name):
        self._sync_background_style_fields(preset_name, force=True)
        self._workflow_section_coordinator.update_mapbox_advanced_visibility(preset_name)

    def on_load_background_clicked(self):
        self._save_settings()
        try:
            request = self.background_controller.build_load_request(
                enabled=self.backgroundMapCheckBox.isChecked(),
                preset_name=self.backgroundPresetComboBox.currentText(),
                access_token=self._mapbox_access_token(),
                style_owner=self.mapboxStyleOwnerLineEdit.text().strip(),
                style_id=self.mapboxStyleIdLineEdit.text().strip(),
                tile_mode=self.tileModeComboBox.currentText(),
            )
            result = self.background_controller.load_background_request(request)
            self._runtime_store().set_background_layer(result.layer)
        except (MapboxConfigError, RuntimeError) as exc:
            self._show_error(build_background_map_failure_title(), str(exc))
            self._set_status(build_background_map_failure_status())
            return

        self._set_status(result.status)

    def _sync_background_style_fields(self, preset_name, force=False):
        result = self.background_controller.resolve_style_defaults(
            preset_name,
            current_owner=self.mapboxStyleOwnerLineEdit.text().strip(),
            current_style_id=self.mapboxStyleIdLineEdit.text().strip(),
            force=force,
        )
        if result is not None:
            style_owner, style_id = result
            self.mapboxStyleOwnerLineEdit.setText(style_owner)
            self.mapboxStyleIdLineEdit.setText(style_id)

    def on_open_authorize_clicked(self):
        self._save_settings()
        try:
            authorize_request = self.sync_controller.build_authorize_request(
                client_id=self.clientIdLineEdit.text().strip(),
                client_secret=self.clientSecretLineEdit.text().strip(),
                refresh_token=self.refreshTokenLineEdit.text().strip(),
                cache=self.cache,
                redirect_uri=self._redirect_uri(),
            )
            url = self.sync_controller.build_authorize_url(authorize_request)
            if not QDesktopServices.openUrl(QUrl(url)):
                clipboard = QApplication.clipboard()
                if clipboard is not None:
                    clipboard.setText(url)
                self._show_info(
                    "Open Strava authorize page manually",
                    "qfit could not open the browser automatically. The authorization URL was copied to your clipboard.\n\nOpen this URL in a browser and continue the flow there:\n\n{url}".format(
                        url=url
                    ),
                )
                self._set_status(
                    "Could not open browser automatically. Authorization URL copied to clipboard."
                )
                return
            self._set_status(
                "Strava authorization opened in your browser. Approve access, copy the returned code, then paste it here and click Exchange code."
            )
        except ProviderError as exc:
            self._show_error("Strava authorization failed", str(exc))
            self._set_status("Could not start the Strava authorization flow")

    def on_exchange_code_clicked(self):
        self._save_settings()
        authorization_code = self.authCodeLineEdit.text().strip()
        if not authorization_code:
            self._show_error("Missing authorization code", "Paste the code returned by Strava first.")
            return

        try:
            exchange_request = self.sync_controller.build_exchange_code_request(
                client_id=self.clientIdLineEdit.text().strip(),
                client_secret=self.clientSecretLineEdit.text().strip(),
                refresh_token=self.refreshTokenLineEdit.text().strip(),
                cache=self.cache,
                authorization_code=authorization_code,
                redirect_uri=self._redirect_uri(),
            )
            payload = self.sync_controller.exchange_code_for_tokens(exchange_request)
            refresh_token = payload["refresh_token"]
            self.refreshTokenLineEdit.setText(refresh_token)
            self.authCodeLineEdit.clear()
            self._save_settings()
            self._update_connection_status()
            athlete = payload.get("athlete") or {}
            athlete_name = " ".join(
                part for part in [athlete.get("firstname"), athlete.get("lastname")] if part
            ).strip()
            if athlete_name:
                self._set_status(
                    "Strava connected for {name}. Refresh token saved locally in QGIS settings.".format(
                        name=athlete_name
                    )
                )
            else:
                self._set_status("Strava refresh token saved locally in QGIS settings.")
        except ProviderError as exc:
            self._show_error("Token exchange failed", str(exc))
            self._set_status("Could not exchange the Strava authorization code")

    def on_browse_clicked(self):
        path, _selected = QFileDialog.getSaveFileName(
            self,
            "Choose GeoPackage output",
            self.outputPathLineEdit.text(),
            "GeoPackage (*.gpkg)",
        )
        if path:
            if not path.lower().endswith(".gpkg"):
                path = "{path}.gpkg".format(path=path)
            self.outputPathLineEdit.setText(path)

    def on_refresh_clicked(self):
        # If a fetch is already running, cancel it.
        if self._fetch_task is not None:
            self._fetch_task.cancel()
            self._runtime_store().clear_fetch()
            self._set_fetch_running(False)
            self._set_status("Fetch cancelled.")
            return

        self._start_fetch(
            detailed_route_strategy=self.detailedRouteStrategyComboBox.currentText(),
            status_text="Fetching activities from Strava…",
        )

    def on_backfill_missing_detailed_routes_clicked(self):
        if self._fetch_task is not None:
            return

        self._start_fetch(
            use_detailed_streams=True,
            detailed_route_strategy=DETAILED_ROUTE_STRATEGY_MISSING,
            status_text="Backfilling missing detailed routes from Strava…",
            use_activity_sync_plan=False,
        )

    def _start_fetch(
        self,
        detailed_route_strategy,
        status_text,
        use_detailed_streams=None,
        use_activity_sync_plan=True,
    ):
        self._save_settings()
        sync_plan = (
            self._current_activity_sync_plan()
            if use_activity_sync_plan
            else plan_activity_sync(None)
        )
        try:
            fetch_task = self.activity_workflow.build_fetch_task(
                DockFetchRequest(
                    client_id=self.clientIdLineEdit.text().strip(),
                    client_secret=self.clientSecretLineEdit.text().strip(),
                    refresh_token=self.refreshTokenLineEdit.text().strip(),
                    cache=self.cache,
                    detailed_route_strategy=detailed_route_strategy,
                    on_finished=self._on_fetch_finished,
                    advanced_fetch_enabled=self.advancedFetchGroupBox.isChecked(),
                    detailed_streams_checked=self.detailedStreamsCheckBox.isChecked(),
                    per_page_value=self.perPageSpinBox.value(),
                    max_pages_value=self.maxPagesSpinBox.value(),
                    max_detailed_activities_value=self.maxDetailedActivitiesSpinBox.value(),
                    use_detailed_streams_override=use_detailed_streams,
                    before_epoch=sync_plan.before_epoch,
                    after_epoch=sync_plan.after_epoch,
                )
            )
        except ProviderError as exc:
            self._show_error("Strava import failed", str(exc))
            self._set_status("Strava fetch failed")
            return

        self._runtime_store().begin_fetch(fetch_task)
        self._set_fetch_running(True)
        self._set_status(_fetch_status_for_sync_plan(status_text, sync_plan))
        QgsApplication.taskManager().addTask(fetch_task)

    def _current_activity_sync_plan(self):
        output_path = self.outputPathLineEdit.text().strip()
        sync_state = None
        if output_path:
            try:
                sync_state = SyncRepository(output_path).load_activity_sync_state(provider="strava")
            except (OSError, RuntimeError, sqlite3.Error):
                logger.warning(
                    "Could not read GeoPackage activity sync state; using unbounded fetch plan",
                    exc_info=True,
                )
        return plan_activity_sync(sync_state)

    def _set_fetch_running(self, running):
        """Toggle UI state while a background fetch is in progress."""
        self.refreshButton.setText("Cancel" if running else "Fetch activities")
        self.backfillMissingDetailedRoutesButton.setEnabled(not running)
        self.exchangeCodeButton.setEnabled(not running)
        self.openAuthorizeButton.setEnabled(not running)

    def _on_fetch_finished(self, activities, error, cancelled, provider):
        """Called on the main thread when the background fetch completes."""
        self._runtime_store().clear_fetch()
        self._set_fetch_running(False)

        result = self.activity_workflow.build_fetch_completion_result(
            DockFetchCompletionRequest(
                activities=[] if activities is None else list(activities),
                error=error,
                cancelled=cancelled,
                provider=provider,
                current_activity_type=self.activityTypeComboBox.currentText() or "All",
                preview_request=self._current_activity_preview_request(),
            )
        )

        if result.cancelled:
            self._set_status(result.status_text)
            return

        if result.error_message is not None:
            self._show_error(result.error_title or "Strava import failed", result.error_message)
            self._set_status(result.status_text)
            return

        self._runtime_store().finish_fetch(
            activities=result.activities,
            metadata=result.metadata,
        )
        self.settings.set("last_sync_date", result.today_str)

        if result.activity_type_options is not None:
            self._apply_activity_type_options(result.activity_type_options)
        self.countLabel.setText(result.count_label_text)
        if result.preview_result is not None:
            self.querySummaryLabel.setText(result.preview_result.query_summary_text)
            self.activityPreviewPlainTextEdit.setPlainText(result.preview_result.preview_text)
        if result.activities:
            store_started = self._start_store_activities(
                status_text="Storing fetched activities…"
            )
            if store_started:
                return
            if store_started is None:
                return
        self._set_status(result.status_text)

    def on_load_clicked(self):
        self._start_store_activities(status_text="Store started...")

    def _start_store_activities(self, *, status_text):
        if self._store_task is not None:
            self._set_status("Store already in progress...")
            return None

        self._save_settings()
        workflow = self._store_activities_workflow()
        try:
            request = workflow.build_write_request(
                activities=self.runtime_state.activities,
                output_path=self.outputPathLineEdit.text().strip(),
                write_activity_points=self.writeActivityPointsCheckBox.isChecked(),
                point_stride=self.pointSamplingStrideSpinBox.value(),
                sync_metadata=self.last_fetch_context,
                last_sync_date=self.settings.get("last_sync_date", None),
            )
        except LoadWorkflowError as exc:
            self._show_error("Missing input", str(exc))
            return False
        except (RuntimeError, OSError, ValueError) as exc:
            _msg = "GeoPackage export failed"
            logger.exception(_msg)
            self._show_error(_msg, str(exc))
            self._set_status(_msg)
            return None

        store_task = build_store_task(
            workflow,
            request,
            on_finished=self._handle_store_task_finished,
        )
        self._runtime_store().begin_store(store_task)
        self.loadButton.setEnabled(False)
        self.loadButton.setText("Store in progress...")
        self._set_status(status_text)
        QgsApplication.taskManager().addTask(store_task)
        return True

    def _handle_store_task_finished(self, result, error_message, cancelled):
        self._runtime_store().clear_store()
        self.loadButton.setEnabled(True)
        self.loadButton.setText("Store activities")

        if cancelled:
            self._set_status("Store cancelled")
            return
        if error_message:
            _msg = "GeoPackage export failed"
            self._show_error(_msg, error_message)
            self._set_status(_msg)
            return
        if result is None:
            self._set_status("GeoPackage export failed")
            return

        self._runtime_store().finish_store(
            output_path=result.output_path,
            stored_activity_count=result.total_stored,
        )
        self._mark_atlas_export_stale()
        self._update_stored_activities_summary(result.total_stored)
        self._set_status(result.status)

    def on_sync_routes_clicked(self):
        """Fetch saved Strava routes, persist them, and load route layers."""

        if self._route_sync_task is not None:
            self._route_sync_task.cancel()
            self._set_route_sync_cancelling()
            self._set_status("Route sync cancellation requested…")
            return

        self._save_settings()
        output_path = self.outputPathLineEdit.text().strip()
        if not output_path:
            self._show_error(*build_missing_output_path_error())
            return

        try:
            route_sync_request = self.sync_controller.build_route_sync_task_request(
                client_id=self.clientIdLineEdit.text().strip(),
                client_secret=self.clientSecretLineEdit.text().strip(),
                refresh_token=self.refreshTokenLineEdit.text().strip(),
                cache=self.cache,
                output_path=output_path,
                per_page=self.perPageSpinBox.value(),
                max_pages=self.maxPagesSpinBox.value(),
                use_gpx_geometry=True,
                on_finished=self._handle_route_sync_task_finished,
            )
            route_sync_task = self.sync_controller.build_route_sync_task(route_sync_request)
        except ProviderError as exc:
            self._show_error("Route sync failed", str(exc))
            self._set_status("Route sync failed")
            return

        self._runtime_store().begin_route_sync(route_sync_task)
        self._set_route_sync_running(True)
        self._set_status("Syncing saved Strava routes…")
        QgsApplication.taskManager().addTask(route_sync_task)

    def _set_route_sync_running(self, running):
        button = getattr(self, "syncRoutesButton", None)
        if button is None:
            return
        button.setText(
            "Cancel route sync" if running else "Sync saved routes"
        )
        button.setEnabled(True)
        self.exchangeCodeButton.setEnabled(not running)
        self.openAuthorizeButton.setEnabled(not running)

    def _set_route_sync_cancelling(self):
        button = getattr(self, "syncRoutesButton", None)
        if button is None:
            return
        button.setText("Cancelling route sync…")
        button.setEnabled(False)
        self.exchangeCodeButton.setEnabled(False)
        self.openAuthorizeButton.setEnabled(False)

    def _handle_route_sync_task_finished(self, result, error_message, cancelled, provider):
        self._runtime_store().clear_route_sync()
        self._set_route_sync_running(False)

        if cancelled and result is None:
            self._set_status("Route sync cancelled")
            return
        if error_message:
            self._show_error("Route sync failed", error_message)
            self._set_status("Route sync failed")
            return
        if result is None:
            self._set_status("Route sync failed")
            return

        try:
            output_path = result.get("path")
            if not output_path:
                raise RuntimeError("Route sync did not return a GeoPackage path.")
            route_tracks_layer, route_points_layer, route_profile_samples_layer = (
                self.layer_gateway.load_route_layers(output_path)
            )
        except (RuntimeError, OSError) as exc:
            _msg = "Load route layers failed"
            logger.exception(_msg)
            self._show_error(_msg, str(exc))
            self._set_status(_msg)
            return

        self._runtime_store().set_route_layers(
            route_tracks_layer=route_tracks_layer,
            route_points_layer=route_points_layer,
            route_profile_samples_layer=route_profile_samples_layer,
        )
        self._mark_atlas_export_stale()

        sync = result.get("sync")
        rate_limit_note = self.sync_controller._rate_limit_note(
            getattr(provider, "last_rate_limit", None)
        )
        fetch_notice = result.get("fetch_notice") or getattr(provider, "last_fetch_notice", None)
        fetch_notice_note = " {notice}".format(notice=fetch_notice) if fetch_notice else ""
        status = (
            "Synced {fetched} saved routes into GeoPackage: inserted {inserted}, "
            "updated {updated}, unchanged {unchanged}, stored total {total}. "
            "Loaded {tracks} route tracks, {points} route points, and {samples} profile samples."
        ).format(
            fetched=result.get("fetched_count", 0),
            inserted=sync.inserted if sync else 0,
            updated=sync.updated if sync else 0,
            unchanged=sync.unchanged if sync else 0,
            total=sync.total_count if sync else 0,
            tracks=result.get("route_track_count", 0),
            points=result.get("route_point_count", 0),
            samples=result.get("route_profile_sample_count", 0),
        )
        if cancelled:
            status = "Route sync completed after cancellation was requested. " + status
        self._set_status(status + rate_limit_note + fetch_notice_note)

    def on_load_layers_clicked(self):
        """Load an existing GeoPackage into QGIS without fetching from Strava."""
        self._save_settings()
        workflow = self._dataset_load_workflow_service()
        try:
            request = workflow.build_load_existing_request(
                self.outputPathLineEdit.text().strip(),
            )
            result = workflow.load_existing_request(request)
        except LoadWorkflowError as exc:
            self._show_error("GeoPackage not found", str(exc))
            return
        except (RuntimeError, OSError) as exc:
            _msg = "Load stored map layers failed"
            logger.exception(_msg)
            self._show_error(_msg, str(exc))
            self._set_status(_msg)
            return

        self._runtime_store().load_dataset(
            output_path=result.output_path,
            stored_activity_count=result.total_stored,
            activities_layer=result.activities_layer,
            starts_layer=result.starts_layer,
            points_layer=result.points_layer,
            atlas_layer=result.atlas_layer,
        )
        self._runtime_store().set_route_layers(
            route_tracks_layer=getattr(result, "route_tracks_layer", None),
            route_points_layer=getattr(result, "route_points_layer", None),
            route_profile_samples_layer=getattr(result, "route_profile_samples_layer", None),
        )
        self._mark_atlas_export_stale()

        self._populate_activity_types_from_layer()
        visual_status = self._apply_visual_configuration(apply_subset_filters=False)

        self._update_loaded_activities_summary(result.total_stored)
        status = result.status
        if visual_status:
            status = "{status} {visual_status}".format(status=status, visual_status=visual_status)
        self._set_status(status)

    def on_clear_database_clicked(self):
        """Delete the GeoPackage, clear loaded layers, and reset status."""
        output_path = self.outputPathLineEdit.text().strip()
        if not output_path:
            self._show_error(*build_missing_output_path_error())
            return

        reply = QMessageBox.question(
            self,
            build_clear_database_confirmation_title(),
            build_clear_database_confirmation_body(output_path),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        workflow = self._clear_database_workflow_service()
        try:
            request = workflow.build_clear_database_request(
                output_path=output_path,
                layers=[
                    self.activities_layer,
                    self.starts_layer,
                    self.points_layer,
                    self.atlas_layer,
                    self.runtime_state.route_tracks_layer,
                    self.runtime_state.route_points_layer,
                    self.runtime_state.route_profile_samples_layer,
                ],
            )
            result = workflow.clear_database_request(request)
        except LoadWorkflowError as exc:
            self._show_error(build_clear_database_load_workflow_error_title(), str(exc))
            return
        except (RuntimeError, OSError) as exc:
            self._show_error(build_clear_database_delete_failure_error_title(), str(exc))
            self._set_status(build_clear_database_delete_failure_status())
            return

        self._runtime_store().reset_loaded_dataset()
        self._clear_analysis_layer()
        self._mark_atlas_export_stale()

        self._update_cleared_activities_summary()
        self._set_status(result.status)

    def on_apply_filters_clicked(self):
        self._dispatch_dock_action(ApplyVisualizationAction)

    def on_run_analysis_clicked(self):
        self._dispatch_dock_action(RunAnalysisAction)

    def on_clear_analysis_clicked(self):
        self._clear_analysis_layer()
        self._set_status("No analysis displayed")
        self._refresh_live_dock_navigation_from_runtime()

    def _dispatch_dock_action(self, action_type):
        result = self._dock_visual_workflow.dispatch_action(
            action_type,
            self._current_visual_workflow_request(),
            require_layers=True,
        )
        if result is None:
            return

        if result.unsupported_reason:
            self._set_status(result.unsupported_reason)
            return
        if result.background_error:
            self._show_error(build_background_map_failure_title(), result.background_error)
        if result.background_layer is not None:
            self._runtime_store().set_background_layer(result.background_layer)
        if result.status:
            self._set_status(result.status)

    def _build_visual_workflow_action(self, action_type):
        """Compatibility wrapper while older smoke tests migrate to coordinator entry points."""

        return self._dock_visual_workflow.build_action(
            action_type,
            self._current_visual_workflow_request(),
        )

    def _current_visual_workflow_request(self, *, apply_subset_filters=True):
        return DockVisualWorkflowRequest(
            layers=build_visual_layer_refs(
                activities_layer=self.activities_layer,
                starts_layer=self.starts_layer,
                points_layer=self.points_layer,
                atlas_layer=self.atlas_layer,
            ),
            selection_state=build_visual_workflow_selection_state_handoff(
                build_activity_preview_selection_state(
                    self._current_activity_preview_request()
                )
            ),
            settings=build_visual_workflow_settings_snapshot(
                style_preset=self.stylePresetComboBox.currentText(),
                temporal_mode=DEFAULT_TEMPORAL_MODE_LABEL,
                analysis_mode=self.analysisModeComboBox.currentText(),
            ),
            background=build_visual_workflow_background_inputs(
                enabled=self.backgroundMapCheckBox.isChecked(),
                preset_name=self.backgroundPresetComboBox.currentText(),
                access_token=self._mapbox_access_token(),
                style_owner=self.mapboxStyleOwnerLineEdit.text().strip(),
                style_id=self.mapboxStyleIdLineEdit.text().strip(),
                tile_mode=self.tileModeComboBox.currentText(),
            ),
            apply_subset_filters=apply_subset_filters,
        )

    def _run_selected_analysis(self, analysis_mode, starts_layer, selection_state=None):
        request = self.analysis_workflow.build_request(
            analysis_mode=analysis_mode,
            starts_layer=starts_layer,
            selection_state=selection_state,
            activities_layer=getattr(self, "activities_layer", None),
            points_layer=getattr(self, "points_layer", None),
        )
        result = self.analysis_workflow.run_request(request)
        if result.layer is None:
            return result.status

        QgsProject.instance().addMapLayer(result.layer, False)
        QgsProject.instance().layerTreeRoot().insertLayer(0, result.layer)
        self._runtime_store().set_analysis_layer(result.layer)
        return result.status

    def _apply_visual_configuration(self, apply_subset_filters):
        result = self._dock_visual_workflow.dispatch_action(
            ApplyVisualizationAction,
            self._current_visual_workflow_request(
                apply_subset_filters=apply_subset_filters,
            ),
            require_layers=False,
        )
        if result.background_error:
            self._show_error(build_background_map_failure_title(), result.background_error)
        if result.background_layer is not None:
            self._runtime_store().set_background_layer(result.background_layer)
        return result.status

    def _apply_analysis_configuration(
        self,
        analysis_mode=None,
        starts_layer=None,
        selection_state=None,
    ):
        self._clear_analysis_layer()

        inputs = build_apply_analysis_configuration_inputs(
            current_mode=self.analysisModeComboBox.currentText(),
            current_starts_layer=getattr(self, "starts_layer", None),
            current_selection_state=build_activity_preview_selection_state(
                self._current_activity_preview_request()
            ),
            analysis_mode=analysis_mode,
            starts_layer=starts_layer,
            selection_state=selection_state,
        )
        return self._run_selected_analysis(
            inputs.analysis_mode,
            inputs.starts_layer,
            inputs.selection_state,
        )

    def _clear_analysis_layer(self):
        project = QgsProject.instance()
        analysis_removed = False
        if self.analysis_layer is not None:
            analysis_removed = True
            try:
                project.removeMapLayer(self.analysis_layer.id())
            except RuntimeError:
                logger.debug("Failed to remove analysis layer", exc_info=True)
            self._runtime_store().clear_analysis_layer()

        analysis_layer_names = {
            FREQUENT_STARTING_POINTS_LAYER_NAME,
            ACTIVITY_HEATMAP_LAYER_NAME,
        }
        for layer in tuple(project.mapLayers().values()):
            if layer.name() not in analysis_layer_names:
                continue
            analysis_removed = True
            try:
                project.removeMapLayer(layer.id())
            except RuntimeError:
                logger.debug("Failed to remove stale analysis layer", exc_info=True)
        if analysis_removed:
            self._mark_atlas_export_stale()
        return analysis_removed

    def _current_activity_preview_request(self):
        return build_activity_preview_request(
            activities=self.runtime_state.activities,
            activity_type=self.activityTypeComboBox.currentText() or "All",
            date_from=self.dateFromEdit.date().toString("yyyy-MM-dd") if self.dateFromEdit.date().isValid() else None,
            date_to=self.dateToEdit.date().toString("yyyy-MM-dd") if self.dateToEdit.date().isValid() else None,
            min_distance_km=self.minDistanceSpinBox.value(),
            max_distance_km=self.maxDistanceSpinBox.value(),
            search_text=self.activitySearchLineEdit.text().strip(),
            detailed_route_filter=self.detailedRouteStatusComboBox.currentData(),
            sort_label=self.previewSortComboBox.currentText() or DEFAULT_SORT_LABEL,
        )

    def _refresh_activity_preview(self):
        preview = self.activity_workflow.build_preview_result(
            self._current_activity_preview_request()
        )
        self.querySummaryLabel.setText(preview.query_summary_text)
        self.activityPreviewPlainTextEdit.setPlainText(preview.preview_text)
        self._refresh_summary_status()
        return preview.fetched_activities

    def _update_cleared_activities_summary(self):
        self.countLabel.setText(build_cleared_activities_summary())
        self._refresh_summary_status()

    def _update_last_sync_summary(self):
        summary = build_last_sync_summary(
            last_sync_date=self.settings.get("last_sync_date", None),
        )
        if summary:
            self.countLabel.setText(summary)
            self._refresh_summary_status()

    def _update_loaded_activities_summary(self, total_activities):
        self.countLabel.setText(
            build_loaded_activities_summary(
                total_activities=total_activities,
                last_sync_date=self.settings.get("last_sync_date", "unknown"),
            )
        )
        self._refresh_summary_status()

    def _update_stored_activities_summary(self, total_activities):
        self.countLabel.setText(
            build_stored_activities_summary(
                total_activities=total_activities,
                last_sync_date=self.settings.get("last_sync_date", date.today().isoformat()),
            )
        )
        self._refresh_summary_status()

    def _redirect_uri(self):
        return self.redirectUriLineEdit.text().strip() or StravaProvider.DEFAULT_REDIRECT_URI

    def _mapbox_access_token(self):
        return (self.settings.get("mapbox_access_token", "") or "").strip()

    def _qdate_to_date(self, value):
        return date(value.year(), value.month(), value.day())

    def _apply_activity_type_options(self, result: ActivityTypeOptionsResult) -> None:
        self.activityTypeComboBox.clear()
        for value in result.options:
            self.activityTypeComboBox.addItem(value)
        index = self.activityTypeComboBox.findText(result.selected_value)
        self.activityTypeComboBox.setCurrentIndex(max(index, 0))

    def _populate_activity_types(self):
        self._apply_activity_type_options(
            build_activity_type_options_from_activities(
                self.runtime_state.activities,
                current_value=self.activityTypeComboBox.currentText() or "All",
            )
        )

    def _populate_activity_types_from_layer(self):
        """Populate the activity type filter from the loaded activities layer.

        Used when layers are loaded directly (without fetching), so the combo
        box shows the correct activity types from the existing GeoPackage.
        """
        if self.activities_layer is None or not self.activities_layer.isValid():
            return
        current_value = self.activityTypeComboBox.currentText() or "All"
        try:
            field_names = [self.activities_layer.fields().at(i).name() for i in range(self.activities_layer.fields().count())]
            result = build_activity_type_options_from_records(
                self.activities_layer.getFeatures(),
                field_names,
                current_value=current_value,
            )
        except (RuntimeError, KeyError):
            logger.debug("Failed to populate activity types from layer", exc_info=True)
            return
        if result is None:
            return
        self._apply_activity_type_options(result)


    def _update_connection_status(self):
        self.connectionStatusLabel.setText(
            build_strava_connection_status(
                client_id=self.clientIdLineEdit.text(),
                client_secret=self.clientSecretLineEdit.text(),
                refresh_token=self.refreshTokenLineEdit.text(),
            )
        )
        self._refresh_summary_status()

    def on_atlas_pdf_browse_clicked(self):
        path, _selected = QFileDialog.getSaveFileName(
            self,
            "Save Atlas PDF",
            self.atlasPdfPathLineEdit.text(),
            "PDF files (*.pdf)",
        )
        if path:
            if not path.lower().endswith(".pdf"):
                path = f"{path}.pdf"
            self.atlasPdfPathLineEdit.setText(path)
            self._mark_atlas_export_stale()
            self._refresh_summary_status()

    def on_generate_atlas_pdf_clicked(self):
        # Cancel any running export
        if self._atlas_export_task is not None:
            self._atlas_export_task.cancel()
            self._set_atlas_export_cancelling()
            self._set_atlas_pdf_status("Atlas PDF export cancellation requested…")
            self._set_status("Atlas PDF export cancellation requested…")
            return

        export_command = self._atlas_workflow_service().build_export_command(
            self._current_atlas_export_request(),
        )
        prepared_export = self.atlas_export_use_case.prepare_export(export_command)
        if prepared_export.path_changed:
            self.atlasPdfPathLineEdit.setText(prepared_export.output_path)
        if not prepared_export.is_ready:
            if prepared_export.pdf_status is not None:
                self._set_atlas_pdf_status(prepared_export.pdf_status)
            if prepared_export.main_status is not None:
                self._set_status(prepared_export.main_status)
            self._show_error(prepared_export.error_title, prepared_export.error_message)
            return

        self._save_settings()
        atlas_export_task = self.atlas_export_use_case.start_export(
            prepared_export,
            export_command,
        )
        self._runtime_store().begin_atlas_export(atlas_export_task)
        self._atlas_export_task_output_path = prepared_export.output_path

        self._set_atlas_export_running(True)
        self._set_atlas_pdf_status(
            f"Exporting atlas ({self.atlas_layer.featureCount()} pages)…"
        )
        self._set_status("Generating atlas PDF…")

        QgsApplication.taskManager().addTask(atlas_export_task)

    def _current_atlas_export_request(self):
        return DockAtlasExportRequest(
            atlas_layer=self.atlas_layer,
            selection_state=build_activity_preview_selection_state(
                self._current_activity_preview_request()
            ),
            output_path=self.atlasPdfPathLineEdit.text().strip(),
            atlas_title=self.atlasTitleLineEdit.text().strip(),
            atlas_subtitle=self.atlasSubtitleLineEdit.text().strip(),
            on_finished=self._on_atlas_export_finished,
            pre_export_tile_mode=self.tileModeComboBox.currentText(),
            preset_name=self.backgroundPresetComboBox.currentText(),
            access_token=self._mapbox_access_token(),
            style_owner=self.mapboxStyleOwnerLineEdit.text().strip(),
            style_id=self.mapboxStyleIdLineEdit.text().strip(),
            background_enabled=self.backgroundMapCheckBox.isChecked(),
            profile_plot_style=build_native_profile_plot_style_from_settings(self.settings),
        )

    def _set_atlas_export_running(self, running: bool) -> None:
        self.generateAtlasPdfButton.setText(
            "Cancel export" if running else "Generate atlas PDF"
        )
        self.generateAtlasPdfButton.setEnabled(True)
        self.loadButton.setEnabled(not running)
        self.loadLayersButton.setEnabled(not running)
        self.refreshButton.setEnabled(not running)

    def _set_atlas_export_cancelling(self) -> None:
        self.generateAtlasPdfButton.setText("Cancelling…")
        self.generateAtlasPdfButton.setEnabled(False)

    def _on_atlas_export_finished(
        self,
        output_path,
        error,
        cancelled,
        page_count,
    ) -> None:
        """Called on the main thread when the atlas export task completes."""
        self._runtime_store().clear_atlas_export()
        self._set_atlas_export_running(False)

        result = self.atlas_export_use_case.finish_export(output_path, error, cancelled, page_count)
        if not result.cancelled and result.error is None and result.output_path:
            self._atlas_export_completed = True
            self._atlas_export_output_path = result.output_path
        self._atlas_export_task_output_path = None
        self._set_atlas_pdf_status(result.pdf_status)
        self._set_status(result.main_status)
        if result.error is not None and not result.cancelled:
            self._show_error("Atlas PDF export failed", result.error)

    def _set_atlas_pdf_status(self, text: str) -> None:
        label = getattr(self, "atlasPdfStatusLabel", None)
        if label is not None:
            label.setText(text)

    def _set_status(self, text):
        self.statusLabel.setText(text)
        self._refresh_summary_status()

    def _refresh_summary_status(self) -> None:
        label = getattr(self, "summaryStatusLabel", None)
        if label is not None:
            label.setText(
                build_dock_summary_status(
                    connection_status=self._label_text("connectionStatusLabel"),
                    activity_summary=self._label_text("countLabel"),
                    query_summary=self._label_text("querySummaryLabel"),
                    workflow_status=self._label_text("statusLabel"),
                )
            )
        self._refresh_live_dock_navigation_from_runtime()

    def _label_text(self, name: str) -> str:
        return self._widget_text(name)

    def _widget_text(self, name: str) -> str:
        widget = getattr(self, name, None)
        if widget is None:
            return ""
        text = getattr(widget, "text", "")
        if callable(text):
            return text()
        return text or ""

    def _show_info(self, title, message):
        QMessageBox.information(self, title, message)

    def _show_error(self, title, message):
        QMessageBox.critical(self, title, message)
