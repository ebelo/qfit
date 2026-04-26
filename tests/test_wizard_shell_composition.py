import importlib
import sys
import unittest
from unittest.mock import patch

from tests import _path  # noqa: F401
from tests.test_wizard_shell import _fake_qt_modules

from qfit.ui.application.dock_workflow_sections import DockWizardProgress


def _load_wizard_composition_module():
    for name in (
        "qfit.ui.dockwidget.wizard_composition",
        "qfit.ui.dockwidget.analysis_page",
        "qfit.ui.dockwidget.atlas_page",
        "qfit.ui.dockwidget.connection_page",
        "qfit.ui.dockwidget.sync_page",
        "qfit.ui.dockwidget.map_page",
        "qfit.ui.dockwidget.wizard_shell_presenter",
        "qfit.ui.dockwidget.wizard_page",
        "qfit.ui.dockwidget.wizard_shell",
        "qfit.ui.dockwidget.stepper_bar",
        "qfit.ui.dockwidget",
    ):
        sys.modules.pop(name, None)
    with patch.dict(sys.modules, _fake_qt_modules()):
        return importlib.import_module("qfit.ui.dockwidget.wizard_composition")


class WizardShellCompositionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.composition = _load_wizard_composition_module()

    def test_builds_placeholder_shell_with_pages_before_presenter_renders(self):
        assembled = self.composition.build_placeholder_wizard_shell(footer_text="Ready")

        self.assertEqual(assembled.shell.objectName(), "qfitWizardShell")
        self.assertEqual(assembled.shell.footer_bar.text(), "Ready")
        self.assertEqual(assembled.shell.page_count(), 5)
        self.assertEqual(
            [page.spec.key for page in assembled.pages],
            ["connection", "sync", "map", "analysis", "atlas"],
        )
        self.assertEqual(assembled.shell.pages_stack.widgets, list(assembled.pages))
        self.assertEqual(assembled.presenter.progress.current_key, "connection")
        self.assertEqual(assembled.shell.pages_stack.currentIndex(), 0)
        self.assertIsNotNone(assembled.connection_content)
        self.assertIs(
            assembled.pages[0].body_layout().widgets[-1],
            assembled.connection_content,
        )
        self.assertEqual(
            assembled.connection_content.status_label.text(),
            "Strava not connected",
        )
        self.assertEqual(assembled.pages[0].primary_hint_label.text(), "")
        self.assertFalse(assembled.pages[0].primary_hint_label.isVisible())
        self.assertIsNotNone(assembled.sync_content)
        self.assertIs(
            assembled.pages[1].body_layout().widgets[-1],
            assembled.sync_content,
        )
        self.assertEqual(
            assembled.sync_content.status_label.text(),
            "Activities not synced yet",
        )
        self.assertIsNotNone(assembled.map_content)
        self.assertIs(
            assembled.pages[2].body_layout().widgets[-1],
            assembled.map_content,
        )
        self.assertEqual(
            assembled.map_content.status_label.text(),
            "Activity layers not loaded",
        )
        self.assertIsNotNone(assembled.analysis_content)
        self.assertIs(
            assembled.pages[3].body_layout().widgets[-1],
            assembled.analysis_content,
        )
        self.assertEqual(
            assembled.analysis_content.status_label.text(),
            "Analysis not run yet",
        )
        self.assertIsNotNone(assembled.atlas_content)
        self.assertIs(
            assembled.pages[4].body_layout().widgets[-1],
            assembled.atlas_content,
        )
        self.assertEqual(
            assembled.atlas_content.status_label.text(),
            "Atlas PDF not exported yet",
        )
        self.assertTrue(
            all(
                page.primary_hint_label.property("wizardPlaceholderHint") == "retired"
                for page in assembled.pages
            )
        )
        self.assertEqual(
            assembled.shell.stepper_bar.states(),
            ("current", "locked", "locked", "locked", "locked"),
        )

    def test_action_callbacks_are_wired_to_installed_page_ctas(self):
        calls = []
        callbacks = self.composition.WizardActionCallbacks(
            configure_connection=lambda: calls.append("configure"),
            sync_activities=lambda: calls.append("sync"),
            load_activity_layers=lambda: calls.append("load"),
            apply_map_filters=lambda: calls.append("filter"),
            run_analysis=lambda: calls.append("analysis"),
            export_atlas=lambda: calls.append("atlas"),
        )

        assembled = self.composition.build_placeholder_wizard_shell(
            map_state=self.composition.MapPageState(loaded=True),
            analysis_state=self.composition.AnalysisPageState(ready=True),
            atlas_state=self.composition.AtlasPageState(ready=True),
        )

        returned = self.composition.connect_wizard_action_callbacks(assembled, callbacks)

        assembled.connection_content.configure_button.clicked.emit()
        assembled.sync_content.sync_button.clicked.emit()
        assembled.map_content.load_layers_button.clicked.emit()
        assembled.map_content.apply_filters_button.clicked.emit()
        assembled.analysis_content.run_analysis_button.clicked.emit()
        assembled.atlas_content.export_atlas_button.clicked.emit()

        self.assertIs(returned, assembled)
        self.assertIs(assembled.action_callbacks, callbacks)
        self.assertEqual(
            calls,
            ["configure", "sync", "load", "filter", "analysis", "atlas"],
        )

    def test_action_callbacks_are_only_wired_once_per_composition(self):
        calls = []
        assembled = self.composition.build_placeholder_wizard_shell()
        first_callbacks = self.composition.WizardActionCallbacks(
            configure_connection=lambda: calls.append("first"),
        )
        second_callbacks = self.composition.WizardActionCallbacks(
            configure_connection=lambda: calls.append("second"),
        )

        self.composition.connect_wizard_action_callbacks(assembled, first_callbacks)
        returned = self.composition.connect_wizard_action_callbacks(
            assembled,
            second_callbacks,
        )
        assembled.connection_content.configure_button.clicked.emit()

        self.assertIs(returned, assembled)
        self.assertIs(assembled.action_callbacks, first_callbacks)
        self.assertEqual(calls, ["first"])

    def test_action_callbacks_ignore_pages_missing_from_partial_specs(self):
        calls = []
        specs = (
            self.composition.DockWizardPageSpec(
                key="connection",
                title="Connection",
                summary="Connect qfit to Strava.",
                primary_action_hint="Primary action: configure connection",
            ),
        )

        assembled = self.composition.build_placeholder_wizard_shell(specs=specs)
        self.composition.connect_wizard_action_callbacks(
            assembled,
            self.composition.WizardActionCallbacks(
                configure_connection=lambda: calls.append("configure"),
                sync_activities=lambda: calls.append("sync"),
            ),
        )

        assembled.connection_content.configure_button.clicked.emit()

        self.assertEqual(calls, ["configure"])
        self.assertIsNone(assembled.sync_content)

    def test_initial_progress_selects_matching_installed_page(self):
        progress = DockWizardProgress(
            current_key="map",
            completed_keys=frozenset({"connection", "sync"}),
            visited_keys=frozenset({"map"}),
        )

        assembled = self.composition.build_placeholder_wizard_shell(progress=progress)

        self.assertEqual(assembled.shell.pages_stack.currentIndex(), 2)
        self.assertEqual(
            assembled.shell.stepper_bar.states(),
            ("done", "done", "current", "locked", "locked"),
        )

    def test_initial_progress_can_be_derived_from_workflow_facts(self):
        facts = self.composition.WizardProgressFacts(
            connection_configured=True,
            activities_stored=True,
            preferred_current_key="map",
        )

        assembled = self.composition.build_placeholder_wizard_shell(progress_facts=facts)

        self.assertEqual(assembled.presenter.progress.current_key, "map")
        self.assertEqual(
            assembled.presenter.progress.completed_keys,
            frozenset({"connection", "sync"}),
        )
        self.assertEqual(assembled.shell.pages_stack.currentIndex(), 2)
        self.assertEqual(
            assembled.shell.stepper_bar.states(),
            ("done", "done", "current", "locked", "locked"),
        )
        self.assertEqual(assembled.connection_content.status_label.text(), "Strava connected")
        self.assertEqual(assembled.connection_content.configure_button.text(), "Review connection")
        self.assertEqual(assembled.sync_content.status_label.text(), "Activities stored")
        self.assertTrue(assembled.sync_content.sync_button.isEnabled())
        self.assertEqual(
            assembled.map_content.status_label.text(),
            "Stored activities ready to load",
        )
        self.assertTrue(assembled.map_content.load_layers_button.isEnabled())
        self.assertEqual(
            assembled.map_content.load_layers_button.property("wizardActionAvailability"),
            "available",
        )
        self.assertFalse(assembled.map_content.apply_filters_button.isEnabled())

    def test_existing_wizard_settings_restore_reachable_initial_step(self):
        settings = self.composition.WizardSettingsSnapshot(
            wizard_version=1,
            last_step_index=3,
            first_launch=False,
        )

        assembled = self.composition.build_placeholder_wizard_shell(
            progress_facts=self.composition.WizardProgressFacts(
                connection_configured=True,
                activities_stored=True,
                activity_layers_loaded=True,
            ),
            wizard_settings=settings,
        )

        self.assertEqual(assembled.presenter.progress.current_key, "analysis")
        self.assertEqual(assembled.shell.pages_stack.currentIndex(), 3)
        self.assertEqual(
            assembled.shell.stepper_bar.states(),
            ("done", "done", "done", "current", "locked"),
        )

    def test_first_launch_wizard_settings_do_not_restore_saved_step(self):
        settings = self.composition.WizardSettingsSnapshot(
            wizard_version=1,
            last_step_index=4,
            first_launch=True,
        )

        assembled = self.composition.build_placeholder_wizard_shell(
            progress_facts=self.composition.WizardProgressFacts(),
            wizard_settings=settings,
        )

        self.assertEqual(assembled.presenter.progress.current_key, "connection")
        self.assertEqual(assembled.shell.pages_stack.currentIndex(), 0)

    def test_connection_page_summary_reports_configured_credentials(self):
        facts = self.composition.WizardProgressFacts(connection_configured=True)

        assembled = self.composition.build_placeholder_wizard_shell(progress_facts=facts)

        self.assertEqual(
            assembled.connection_content.credential_summary_label.text(),
            "Strava OAuth credentials are stored in qfit settings",
        )
        self.assertEqual(
            assembled.connection_content.credential_summary_label.property("connectionState"),
            "connected",
        )

    def test_sync_page_summary_uses_runtime_activity_count_and_output_name(self):
        facts = self.composition.WizardProgressFacts(
            connection_configured=True,
            activities_stored=True,
            activity_count=12,
            output_name="qfit.gpkg",
        )

        assembled = self.composition.build_placeholder_wizard_shell(progress_facts=facts)

        self.assertEqual(
            assembled.sync_content.activity_summary_label.text(),
            "12 activities stored in qfit.gpkg",
        )
        self.assertIn("12 activities stored in qfit.gpkg", assembled.shell.footer_bar.text())

    def test_sync_page_summary_uses_singular_activity_count(self):
        facts = self.composition.WizardProgressFacts(
            connection_configured=True,
            activities_stored=True,
            activity_count=1,
            output_name="qfit.gpkg",
        )

        assembled = self.composition.build_placeholder_wizard_shell(progress_facts=facts)

        self.assertEqual(
            assembled.sync_content.activity_summary_label.text(),
            "1 activity stored in qfit.gpkg",
        )

    def test_sync_page_summary_omits_unknown_activity_count(self):
        facts = self.composition.WizardProgressFacts(
            connection_configured=True,
            activities_stored=True,
            output_name="qfit.gpkg",
        )

        assembled = self.composition.build_placeholder_wizard_shell(progress_facts=facts)

        self.assertEqual(
            assembled.sync_content.activity_summary_label.text(),
            "Activities stored in qfit.gpkg",
        )

    def test_sync_page_shows_fetched_activities_ready_to_store(self):
        facts = self.composition.WizardProgressFacts(
            connection_configured=True,
            activities_fetched=True,
            fetched_activity_count=3,
        )

        assembled = self.composition.build_placeholder_wizard_shell(progress_facts=facts)

        self.assertEqual(assembled.presenter.progress.current_key, "sync")
        self.assertEqual(assembled.sync_content.status_label.text(), "Activities fetched")
        self.assertEqual(
            assembled.sync_content.detail_label.text(),
            "Store fetched activities in the GeoPackage to complete synchronization.",
        )
        self.assertEqual(
            assembled.sync_content.activity_summary_label.text(),
            "3 fetched activities ready to store",
        )
        self.assertEqual(
            assembled.sync_content.sync_button.text(),
            "Store fetched activities",
        )
        self.assertTrue(assembled.sync_content.sync_button.isEnabled())
        self.assertIn(
            "3 fetched activities ready to store",
            assembled.shell.footer_bar.text(),
        )

    def test_map_page_summary_names_stored_output_before_layers_load(self):
        facts = self.composition.WizardProgressFacts(
            connection_configured=True,
            activities_stored=True,
            output_name="qfit.gpkg",
        )

        assembled = self.composition.build_placeholder_wizard_shell(progress_facts=facts)

        self.assertEqual(
            assembled.map_content.status_label.text(),
            "Stored activities ready to load",
        )
        self.assertEqual(
            assembled.map_content.layer_summary_label.text(),
            "Stored activities in qfit.gpkg are ready to load",
        )
        self.assertIn(
            "Stored activities in qfit.gpkg are ready to load",
            assembled.shell.footer_bar.text(),
        )

    def test_loaded_map_page_summary_names_source_output(self):
        facts = self.composition.WizardProgressFacts(
            connection_configured=True,
            activities_stored=True,
            activity_layers_loaded=True,
            output_name="qfit.gpkg",
        )

        assembled = self.composition.build_placeholder_wizard_shell(progress_facts=facts)

        self.assertEqual(
            assembled.map_content.layer_summary_label.text(),
            "Activity layers from qfit.gpkg are loaded on the map",
        )
        self.assertIn(
            "Activity layers from qfit.gpkg are loaded on the map",
            assembled.shell.footer_bar.text(),
        )

    def test_map_page_summary_reports_enabled_basemap_before_load(self):
        facts = self.composition.WizardProgressFacts(
            connection_configured=True,
            activities_stored=True,
            background_enabled=True,
            background_name="Outdoors",
        )

        assembled = self.composition.build_placeholder_wizard_shell(progress_facts=facts)

        self.assertEqual(
            assembled.map_content.background_summary_label.text(),
            "Basemap ready to load: Outdoors",
        )

    def test_map_page_summary_reports_loaded_basemap(self):
        facts = self.composition.WizardProgressFacts(
            connection_configured=True,
            activities_stored=True,
            activity_layers_loaded=True,
            background_enabled=True,
            background_layer_loaded=True,
            background_name="Satellite",
        )

        assembled = self.composition.build_placeholder_wizard_shell(progress_facts=facts)

        self.assertEqual(
            assembled.map_content.background_summary_label.text(),
            "Basemap loaded: Satellite",
        )

    def test_map_page_summary_reports_loaded_basemap_without_stale_name(self):
        facts = self.composition.WizardProgressFacts(
            connection_configured=True,
            activities_stored=True,
            activity_layers_loaded=True,
            background_enabled=True,
            background_layer_loaded=True,
        )

        assembled = self.composition.build_placeholder_wizard_shell(progress_facts=facts)

        self.assertEqual(
            assembled.map_content.background_summary_label.text(),
            "Basemap loaded",
        )

    def test_map_page_summary_reports_selected_activity_style_before_load(self):
        facts = self.composition.WizardProgressFacts(
            connection_configured=True,
            activities_stored=True,
            activity_style_preset="By activity type",
        )

        assembled = self.composition.build_placeholder_wizard_shell(progress_facts=facts)

        self.assertEqual(
            assembled.map_content.style_summary_label.text(),
            "Selected activity style: By activity type",
        )

    def test_map_page_summary_does_not_claim_loaded_style_is_applied(self):
        facts = self.composition.WizardProgressFacts(
            connection_configured=True,
            activities_stored=True,
            activity_layers_loaded=True,
            activity_style_preset="Simple lines",
        )

        assembled = self.composition.build_placeholder_wizard_shell(progress_facts=facts)

        self.assertEqual(
            assembled.map_content.style_summary_label.text(),
            "Selected activity style: Simple lines",
        )

    def test_loaded_map_page_summary_reports_visible_filter_count(self):
        facts = self.composition.WizardProgressFacts(
            connection_configured=True,
            activities_stored=True,
            activity_layers_loaded=True,
            filters_active=True,
            filtered_activity_count=3,
        )

        assembled = self.composition.build_placeholder_wizard_shell(progress_facts=facts)

        self.assertEqual(
            assembled.map_content.filter_summary_label.text(),
            "Filters match 3 loaded activities",
        )

    def test_loaded_map_page_summary_reports_all_visible_when_unfiltered(self):
        facts = self.composition.WizardProgressFacts(
            connection_configured=True,
            activities_stored=True,
            activity_layers_loaded=True,
        )

        assembled = self.composition.build_placeholder_wizard_shell(progress_facts=facts)

        self.assertEqual(
            assembled.map_content.filter_summary_label.text(),
            "All loaded activities are visible",
        )

    def test_analysis_page_input_summary_reports_filtered_count(self):
        facts = self.composition.WizardProgressFacts(
            connection_configured=True,
            activities_stored=True,
            activity_layers_loaded=True,
            filters_active=True,
            filtered_activity_count=2,
        )

        assembled = self.composition.build_placeholder_wizard_shell(progress_facts=facts)

        self.assertEqual(
            assembled.analysis_content.input_summary_label.text(),
            "2 filtered activities ready for analysis",
        )

    def test_analysis_page_input_summary_reports_singular_filtered_count(self):
        facts = self.composition.WizardProgressFacts(
            connection_configured=True,
            activities_stored=True,
            activity_layers_loaded=True,
            filters_active=True,
            filtered_activity_count=1,
        )

        assembled = self.composition.build_placeholder_wizard_shell(progress_facts=facts)

        self.assertEqual(
            assembled.analysis_content.input_summary_label.text(),
            "1 filtered activity ready for analysis",
        )

    def test_analysis_page_input_summary_reports_zero_filtered_count(self):
        facts = self.composition.WizardProgressFacts(
            connection_configured=True,
            activities_stored=True,
            activity_layers_loaded=True,
            filters_active=True,
            filtered_activity_count=0,
        )

        assembled = self.composition.build_placeholder_wizard_shell(progress_facts=facts)

        self.assertEqual(
            assembled.analysis_content.input_summary_label.text(),
            "0 filtered activities ready for analysis",
        )

    def test_analysis_page_input_summary_reports_filtered_subset_without_count(self):
        facts = self.composition.WizardProgressFacts(
            connection_configured=True,
            activities_stored=True,
            activity_layers_loaded=True,
            filters_active=True,
        )

        assembled = self.composition.build_placeholder_wizard_shell(progress_facts=facts)

        self.assertEqual(
            assembled.analysis_content.input_summary_label.text(),
            "Filtered activity subset ready for analysis",
        )

    def test_progress_facts_drive_page_cta_prerequisites_without_marking_done(self):
        facts = self.composition.WizardProgressFacts(connection_configured=True)

        assembled = self.composition.build_placeholder_wizard_shell(progress_facts=facts)

        self.assertEqual(assembled.presenter.progress.current_key, "sync")
        self.assertEqual(assembled.presenter.progress.completed_keys, frozenset({"connection"}))
        self.assertEqual(
            assembled.shell.stepper_bar.states(),
            ("done", "current", "locked", "locked", "locked"),
        )
        self.assertEqual(assembled.sync_content.status_label.text(), "Activities not synced yet")
        self.assertFalse(assembled.sync_state.ready)
        self.assertTrue(assembled.sync_content.sync_button.isEnabled())
        self.assertEqual(
            assembled.sync_content.sync_button.property("wizardActionAvailability"),
            "available",
        )
        self.assertFalse(assembled.map_content.load_layers_button.isEnabled())
        self.assertEqual(
            assembled.map_content.load_layers_button.toolTip(),
            "Sync activities before loading map layers.",
        )
        self.assertFalse(assembled.analysis_content.run_analysis_button.isEnabled())
        self.assertFalse(assembled.atlas_content.export_atlas_button.isEnabled())
        self.assertEqual(
            assembled.atlas_content.export_atlas_button.toolTip(),
            "Run analysis before exporting atlas PDF.",
        )

    def test_progress_facts_explain_locked_page_prerequisites(self):
        assembled = self.composition.build_placeholder_wizard_shell(
            progress_facts=self.composition.WizardProgressFacts()
        )

        self.assertEqual(
            assembled.sync_content.status_label.text(),
            "Connection required before sync",
        )
        self.assertEqual(
            assembled.sync_content.detail_label.text(),
            "Configure Strava credentials before syncing activities.",
        )
        self.assertEqual(
            assembled.sync_content.activity_summary_label.text(),
            "Connect to Strava to enable synchronization",
        )
        self.assertEqual(
            assembled.map_content.status_label.text(),
            "Sync required before map loading",
        )
        self.assertEqual(
            assembled.map_content.layer_summary_label.text(),
            "Sync activities before loading map layers",
        )
        self.assertEqual(
            assembled.analysis_content.status_label.text(),
            "Map layers required before analysis",
        )
        self.assertEqual(
            assembled.analysis_content.input_summary_label.text(),
            "Load activity layers before running analysis",
        )
        self.assertEqual(
            assembled.atlas_content.status_label.text(),
            "Analysis required before atlas export",
        )
        self.assertEqual(
            assembled.atlas_content.input_summary_label.text(),
            "Run analysis before exporting atlas PDF",
        )
        self.assertIn(
            "Connect to Strava to enable synchronization",
            assembled.shell.footer_bar.text(),
        )

    def test_progress_facts_disable_busy_sync_and_atlas_ctas(self):
        assembled = self.composition.build_placeholder_wizard_shell(
            progress_facts=self.composition.WizardProgressFacts(
                connection_configured=True,
                activities_stored=True,
                activity_layers_loaded=True,
                analysis_generated=True,
                sync_in_progress=True,
                atlas_export_in_progress=True,
            )
        )

        self.assertEqual(
            assembled.sync_content.status_label.text(),
            "Synchronization in progress",
        )
        self.assertEqual(
            assembled.sync_content.activity_summary_label.text(),
            "Updating stored activities",
        )
        self.assertIn("Updating stored activities", assembled.shell.footer_bar.text())
        self.assertFalse(assembled.sync_content.sync_button.isEnabled())
        self.assertEqual(assembled.sync_content.sync_button.text(), "Sync in progress…")
        self.assertEqual(
            assembled.sync_content.sync_button.toolTip(),
            "Wait for the current synchronization to finish.",
        )
        self.assertEqual(
            assembled.atlas_content.status_label.text(),
            "Atlas export in progress",
        )
        self.assertFalse(assembled.atlas_content.export_atlas_button.isEnabled())
        self.assertEqual(
            assembled.atlas_content.export_atlas_button.text(), "Export in progress…"
        )
        self.assertEqual(
            assembled.atlas_content.export_atlas_button.toolTip(),
            "Wait for the current atlas export to finish.",
        )

    def test_busy_sync_summary_uses_output_name_when_available(self):
        assembled = self.composition.build_placeholder_wizard_shell(
            progress_facts=self.composition.WizardProgressFacts(
                connection_configured=True,
                activities_stored=True,
                sync_in_progress=True,
                output_name="qfit.gpkg",
            )
        )

        self.assertEqual(
            assembled.sync_content.activity_summary_label.text(),
            "Updating activities in qfit.gpkg",
        )
        self.assertIn("Updating activities in qfit.gpkg", assembled.shell.footer_bar.text())

    def test_busy_sync_without_stored_activities_replaces_empty_summary(self):
        assembled = self.composition.build_placeholder_wizard_shell(
            progress_facts=self.composition.WizardProgressFacts(
                connection_configured=True,
                sync_in_progress=True,
            )
        )

        self.assertEqual(
            assembled.sync_content.activity_summary_label.text(),
            "Synchronization in progress",
        )
        self.assertIn("Synchronization in progress", assembled.shell.footer_bar.text())

    def test_atlas_page_summary_uses_configured_output_name_before_export(self):
        assembled = self.composition.build_placeholder_wizard_shell(
            progress_facts=self.composition.WizardProgressFacts(
                connection_configured=True,
                activities_stored=True,
                activity_layers_loaded=True,
                analysis_generated=True,
                atlas_output_name="qfit-atlas.pdf",
            )
        )

        self.assertEqual(
            assembled.atlas_content.output_summary_label.text(),
            "Ready to export qfit-atlas.pdf",
        )

    def test_analysis_page_summary_names_generated_output(self):
        assembled = self.composition.build_placeholder_wizard_shell(
            progress_facts=self.composition.WizardProgressFacts(
                connection_configured=True,
                activities_stored=True,
                activity_layers_loaded=True,
                analysis_generated=True,
                analysis_output_name="qfit activity heatmap",
            )
        )

        self.assertEqual(
            assembled.analysis_content.result_summary_label.text(),
            "Analysis output qfit activity heatmap is available",
        )

    def test_atlas_page_input_summary_names_analysis_output(self):
        assembled = self.composition.build_placeholder_wizard_shell(
            progress_facts=self.composition.WizardProgressFacts(
                connection_configured=True,
                activities_stored=True,
                activity_layers_loaded=True,
                analysis_generated=True,
                analysis_output_name="qfit activity heatmap",
            )
        )

        self.assertEqual(
            assembled.atlas_content.input_summary_label.text(),
            "Analysis output qfit activity heatmap ready for atlas export",
        )

    def test_atlas_page_input_summary_keeps_generic_copy_without_named_output(self):
        assembled = self.composition.build_placeholder_wizard_shell(
            progress_facts=self.composition.WizardProgressFacts(
                connection_configured=True,
                activities_stored=True,
                activity_layers_loaded=True,
                analysis_generated=True,
            )
        )

        self.assertEqual(
            assembled.atlas_content.input_summary_label.text(),
            "Analysis outputs ready for atlas export",
        )

    def test_busy_atlas_page_summary_uses_configured_output_name(self):
        assembled = self.composition.build_placeholder_wizard_shell(
            progress_facts=self.composition.WizardProgressFacts(
                connection_configured=True,
                activities_stored=True,
                activity_layers_loaded=True,
                analysis_generated=True,
                atlas_export_in_progress=True,
                atlas_output_name="qfit-atlas.pdf",
            )
        )

        self.assertEqual(
            assembled.atlas_content.output_summary_label.text(),
            "Exporting qfit-atlas.pdf",
        )

    def test_exported_atlas_page_summary_uses_configured_output_name(self):
        assembled = self.composition.build_placeholder_wizard_shell(
            progress_facts=self.composition.WizardProgressFacts(
                connection_configured=True,
                activities_stored=True,
                activity_layers_loaded=True,
                analysis_generated=True,
                atlas_exported=True,
                atlas_output_name="qfit-atlas.pdf",
            )
        )

        self.assertEqual(
            assembled.atlas_content.output_summary_label.text(),
            "Latest atlas PDF exported to qfit-atlas.pdf",
        )

    def test_explicit_page_state_overrides_progress_fact_defaults(self):
        assembled = self.composition.build_placeholder_wizard_shell(
            progress_facts=self.composition.WizardProgressFacts(connection_configured=True),
            sync_state=self.composition.SyncPageState(
                primary_action_enabled=False,
                primary_action_blocked_tooltip="Sync is paused.",
            ),
        )

        self.assertFalse(assembled.sync_content.sync_button.isEnabled())
        self.assertEqual(assembled.sync_content.sync_button.toolTip(), "Sync is paused.")

    def test_progress_fact_page_states_are_gated_by_completed_prefix(self):
        assembled = self.composition.build_placeholder_wizard_shell(
            progress_facts=self.composition.WizardProgressFacts(
                connection_configured=False,
                activities_stored=True,
                activity_layers_loaded=True,
                analysis_generated=True,
                atlas_exported=True,
            )
        )

        self.assertEqual(assembled.presenter.progress.current_key, "connection")
        self.assertEqual(assembled.presenter.progress.completed_keys, frozenset())
        self.assertFalse(assembled.connection_state.connected)
        self.assertFalse(assembled.sync_state.ready)
        self.assertFalse(assembled.sync_content.sync_button.isEnabled())
        self.assertFalse(assembled.map_state.loaded)
        self.assertFalse(assembled.map_content.load_layers_button.isEnabled())
        self.assertFalse(assembled.map_content.apply_filters_button.isEnabled())
        self.assertFalse(assembled.analysis_state.ready)
        self.assertFalse(assembled.analysis_content.run_analysis_button.isEnabled())
        self.assertFalse(assembled.atlas_state.ready)
        self.assertFalse(assembled.atlas_content.export_atlas_button.isEnabled())

    def test_build_rejects_conflicting_progress_inputs(self):
        with self.assertRaisesRegex(ValueError, "progress or progress_facts"):
            self.composition.build_placeholder_wizard_shell(
                progress=DockWizardProgress(current_key="connection"),
                progress_facts=self.composition.WizardProgressFacts(),
            )

    def test_builds_default_footer_from_page_status_facts(self):
        assembled = self.composition.build_placeholder_wizard_shell()

        self.assertEqual(
            assembled.shell.footer_bar.text(),
            "Strava not connected · No activities stored · "
            "No activity layers on the map · Analysis not run yet · "
            "Atlas PDF not exported yet",
        )

    def test_page_state_inputs_drive_default_footer_text(self):
        assembled = self.composition.build_placeholder_wizard_shell(
            connection_state=self.composition.ConnectionPageState(
                connected=True,
                status_text="Strava connected",
            ),
            sync_state=self.composition.SyncPageState(
                ready=True,
                activity_summary_text="12 activities stored",
            ),
            map_state=self.composition.MapPageState(
                loaded=True,
                layer_summary_text="3 activity layers loaded",
            ),
            analysis_state=self.composition.AnalysisPageState(
                ready=True,
                status_text="Analysis ready",
            ),
            atlas_state=self.composition.AtlasPageState(
                ready=True,
                status_text="Atlas ready",
            ),
        )

        self.assertEqual(
            assembled.shell.footer_bar.text(),
            "Strava connected · 12 activities stored · 3 activity layers loaded · "
            "Analysis ready · Atlas ready",
        )

    def test_supports_explicit_empty_specs_without_binding_current_dock_controls(self):
        assembled = self.composition.build_placeholder_wizard_shell(specs=())

        self.assertEqual(assembled.pages, ())
        self.assertIsNone(assembled.connection_content)
        self.assertIsNone(assembled.sync_content)
        self.assertIsNone(assembled.map_content)
        self.assertIsNone(assembled.analysis_content)
        self.assertIsNone(assembled.atlas_content)
        self.assertEqual(assembled.shell.page_count(), 0)
        self.assertEqual(assembled.shell.footer_bar.text(), "Ready")
        self.assertEqual(assembled.shell.pages_stack.currentIndex(), -1)
        self.assertEqual(assembled.presenter.progress.current_key, "connection")

    def test_default_footer_only_summarizes_installed_pages(self):
        specs = (
            self.composition.DockWizardPageSpec(
                key="connection",
                title="Connection",
                summary="Connect qfit to Strava.",
                primary_action_hint="Primary action: configure connection",
            ),
            self.composition.DockWizardPageSpec(
                key="atlas",
                title="Atlas PDF",
                summary="Export a PDF atlas.",
                primary_action_hint="Primary action: export atlas PDF",
            ),
        )

        assembled = self.composition.build_placeholder_wizard_shell(specs=specs)

        self.assertEqual(
            assembled.shell.footer_bar.text(),
            "Strava not connected · Atlas PDF not exported yet",
        )

    def test_refreshes_page_content_and_footer_without_rebuilding_shell(self):
        assembled = self.composition.build_placeholder_wizard_shell()

        refreshed = self.composition.refresh_wizard_shell_composition(
            assembled,
            connection_state=self.composition.ConnectionPageState(
                connected=True,
                status_text="Strava connected",
                detail_text="Credentials are ready.",
                primary_action_label="Review connection",
            ),
            sync_state=self.composition.SyncPageState(
                ready=True,
                status_text="Ready to sync",
                activity_summary_text="12 activities stored",
                primary_action_label="Fetch latest activities",
            ),
            map_state=self.composition.MapPageState(
                loaded=True,
                status_text="Map ready",
                layer_summary_text="3 activity layers loaded",
            ),
            analysis_state=self.composition.AnalysisPageState(
                ready=True,
                status_text="Analysis ready",
            ),
            atlas_state=self.composition.AtlasPageState(
                ready=True,
                status_text="Atlas ready",
            ),
        )

        self.assertIs(refreshed, assembled)
        self.assertIs(refreshed.shell, assembled.shell)
        self.assertIs(refreshed.pages, assembled.pages)
        self.assertIs(refreshed.connection_content, assembled.connection_content)
        self.assertEqual(
            assembled.connection_content.status_label.text(),
            "Strava connected",
        )
        self.assertEqual(
            assembled.connection_content.configure_button.text(),
            "Review connection",
        )
        self.assertEqual(assembled.sync_content.status_label.text(), "Ready to sync")
        self.assertEqual(
            assembled.sync_content.sync_button.text(),
            "Fetch latest activities",
        )
        self.assertEqual(assembled.map_content.status_label.text(), "Map ready")
        self.assertEqual(
            assembled.analysis_content.status_label.text(),
            "Analysis ready",
        )
        self.assertEqual(assembled.atlas_content.status_label.text(), "Atlas ready")
        self.assertEqual(
            assembled.shell.footer_bar.text(),
            "Strava connected · 12 activities stored · 3 activity layers loaded · "
            "Analysis ready · Atlas ready",
        )
        self.assertEqual(refreshed.connection_state.status_text, "Strava connected")

    def test_partial_refresh_keeps_previous_snapshots_without_reassignment(self):
        assembled = self.composition.build_placeholder_wizard_shell()

        self.composition.refresh_wizard_shell_composition(
            assembled,
            connection_state=self.composition.ConnectionPageState(
                connected=True,
                status_text="Strava connected",
            ),
        )
        self.composition.refresh_wizard_shell_composition(
            assembled,
            sync_state=self.composition.SyncPageState(
                ready=True,
                activity_summary_text="12 activities stored",
            ),
        )

        self.assertEqual(
            assembled.connection_content.status_label.text(),
            "Strava connected",
        )
        self.assertEqual(
            assembled.sync_content.activity_summary_label.text(),
            "12 activities stored",
        )
        self.assertEqual(
            assembled.shell.footer_bar.text(),
            "Strava connected · 12 activities stored · "
            "No activity layers on the map · Analysis not run yet · "
            "Atlas PDF not exported yet",
        )

    def test_refresh_supports_explicit_footer_and_partial_page_specs(self):
        specs = (
            self.composition.DockWizardPageSpec(
                key="connection",
                title="Connection",
                summary="Connect qfit to Strava.",
                primary_action_hint="Primary action: configure connection",
            ),
        )
        assembled = self.composition.build_placeholder_wizard_shell(specs=specs)

        refreshed = self.composition.refresh_wizard_shell_composition(
            assembled,
            connection_state=self.composition.ConnectionPageState(
                connected=True,
                status_text="Strava connected",
            ),
            sync_state=self.composition.SyncPageState(
                ready=True,
                activity_summary_text="Hidden sync page should not affect footer",
            ),
            footer_text="Custom status",
        )

        self.assertEqual(
            assembled.connection_content.status_label.text(),
            "Strava connected",
        )
        self.assertIsNone(assembled.sync_content)
        self.assertEqual(assembled.shell.footer_bar.text(), "Custom status")
        self.assertEqual(
            refreshed.sync_state.activity_summary_text,
            "Hidden sync page should not affect footer",
        )

    def test_refresh_can_update_progress_without_rebuilding_shell(self):
        persisted_step_indexes = []
        assembled = self.composition.build_placeholder_wizard_shell(
            on_current_step_changed=persisted_step_indexes.append,
        )
        progress = DockWizardProgress(
            current_key="map",
            completed_keys=frozenset({"connection", "sync"}),
            visited_keys=frozenset({"map"}),
        )

        refreshed = self.composition.refresh_wizard_shell_composition(
            assembled,
            progress=progress,
        )

        self.assertIs(refreshed, assembled)
        self.assertEqual(assembled.presenter.progress, progress)
        self.assertEqual(assembled.shell.pages_stack.currentIndex(), 2)
        self.assertEqual(
            assembled.shell.stepper_bar.states(),
            ("done", "done", "current", "locked", "locked"),
        )
        self.assertIsNotNone(assembled.on_current_step_changed)
        self.assertEqual(persisted_step_indexes, [2])

    def test_refresh_can_update_progress_from_workflow_facts(self):
        assembled = self.composition.build_placeholder_wizard_shell()

        refreshed = self.composition.refresh_wizard_shell_composition(
            assembled,
            progress_facts=self.composition.WizardProgressFacts(
                connection_configured=True,
                activities_stored=True,
                activity_layers_loaded=True,
                preferred_current_key="analysis",
            ),
        )

        self.assertIs(refreshed, assembled)
        self.assertEqual(assembled.presenter.progress.current_key, "analysis")
        self.assertEqual(
            assembled.presenter.progress.completed_keys,
            frozenset({"connection", "sync", "map"}),
        )
        self.assertEqual(assembled.shell.pages_stack.currentIndex(), 3)
        self.assertEqual(
            assembled.shell.stepper_bar.states(),
            ("done", "done", "done", "current", "locked"),
        )
        self.assertEqual(assembled.connection_content.status_label.text(), "Strava connected")
        self.assertEqual(assembled.sync_content.status_label.text(), "Activities stored")
        self.assertEqual(assembled.map_content.status_label.text(), "Activity layers loaded")
        self.assertTrue(assembled.map_content.load_layers_button.isEnabled())
        self.assertTrue(assembled.map_content.apply_filters_button.isEnabled())
        self.assertFalse(assembled.analysis_state.ready)
        self.assertTrue(assembled.analysis_content.run_analysis_button.isEnabled())
        self.assertFalse(assembled.atlas_content.export_atlas_button.isEnabled())

    def test_refresh_can_update_progress_from_settings_and_workflow_facts(self):
        assembled = self.composition.build_placeholder_wizard_shell()

        self.composition.refresh_wizard_shell_composition(
            assembled,
            progress_facts=self.composition.WizardProgressFacts(
                connection_configured=True,
                activities_stored=True,
            ),
            wizard_settings=self.composition.WizardSettingsSnapshot(
                wizard_version=1,
                last_step_index=2,
                first_launch=False,
            ),
        )

        self.assertEqual(assembled.presenter.progress.current_key, "map")
        self.assertEqual(assembled.shell.pages_stack.currentIndex(), 2)

    def test_refresh_progress_facts_replace_previous_default_state(self):
        assembled = self.composition.build_placeholder_wizard_shell()
        self.composition.refresh_wizard_shell_composition(
            assembled,
            sync_state=self.composition.SyncPageState(
                primary_action_enabled=False,
                primary_action_blocked_tooltip="Sync paused.",
            ),
        )

        self.composition.refresh_wizard_shell_composition(
            assembled,
            progress_facts=self.composition.WizardProgressFacts(connection_configured=True),
        )

        self.assertTrue(assembled.sync_content.sync_button.isEnabled())
        self.assertEqual(assembled.sync_content.sync_button.toolTip(), "")

    def test_refresh_rejects_conflicting_progress_inputs_before_mutation(self):
        assembled = self.composition.build_placeholder_wizard_shell()

        with self.assertRaisesRegex(ValueError, "progress or progress_facts"):
            self.composition.refresh_wizard_shell_composition(
                assembled,
                connection_state=self.composition.ConnectionPageState(
                    connected=True,
                    status_text="Strava connected",
                ),
                progress=DockWizardProgress(current_key="connection"),
                progress_facts=self.composition.WizardProgressFacts(),
            )

        self.assertEqual(
            assembled.connection_content.status_label.text(),
            "Strava not connected",
        )
        self.assertEqual(assembled.presenter.progress.current_key, "connection")

    def test_refresh_validates_progress_before_mutating_page_state(self):
        assembled = self.composition.build_placeholder_wizard_shell()

        with self.assertRaises(KeyError):
            self.composition.refresh_wizard_shell_composition(
                assembled,
                connection_state=self.composition.ConnectionPageState(
                    connected=True,
                    status_text="Strava connected",
                ),
                footer_text="Changed footer",
                progress=DockWizardProgress(current_key="review"),
            )

        self.assertEqual(
            assembled.connection_content.status_label.text(),
            "Strava not connected",
        )
        self.assertEqual(assembled.connection_state.status_text, "Strava not connected")
        self.assertEqual(
            assembled.shell.footer_bar.text(),
            "Strava not connected · No activities stored · "
            "No activity layers on the map · Analysis not run yet · "
            "Atlas PDF not exported yet",
        )
        self.assertEqual(assembled.presenter.progress.current_key, "connection")
        self.assertEqual(assembled.shell.pages_stack.currentIndex(), 0)

    def test_partial_refresh_rejects_progress_for_uninstalled_page(self):
        specs = (
            self.composition.DockWizardPageSpec(
                key="connection",
                title="Connection",
                summary="Connect qfit to Strava.",
                primary_action_hint="Primary action: configure connection",
            ),
        )
        assembled = self.composition.build_placeholder_wizard_shell(specs=specs)

        with self.assertRaises(ValueError):
            self.composition.refresh_wizard_shell_composition(
                assembled,
                connection_state=self.composition.ConnectionPageState(
                    connected=True,
                    status_text="Strava connected",
                ),
                footer_text="Changed footer",
                progress=DockWizardProgress(current_key="sync"),
            )

        self.assertEqual(
            assembled.connection_content.status_label.text(),
            "Strava not connected",
        )
        self.assertEqual(assembled.connection_state.status_text, "Strava not connected")
        self.assertEqual(assembled.shell.footer_bar.text(), "Strava not connected")
        self.assertEqual(assembled.presenter.progress.current_key, "connection")
        self.assertEqual(assembled.shell.pages_stack.currentIndex(), 0)

    def test_partial_progress_uses_installed_page_stack_index(self):
        specs = (
            self.composition.DockWizardPageSpec(
                key="connection",
                title="Connection",
                summary="Connect qfit to Strava.",
                primary_action_hint="Primary action: configure connection",
            ),
            self.composition.DockWizardPageSpec(
                key="atlas",
                title="Atlas PDF",
                summary="Export a PDF atlas.",
                primary_action_hint="Primary action: export atlas PDF",
            ),
        )
        assembled = self.composition.build_placeholder_wizard_shell(specs=specs)
        progress = DockWizardProgress(
            current_key="atlas",
            completed_keys=frozenset({"connection", "sync", "map", "analysis"}),
            visited_keys=frozenset({"atlas"}),
        )

        self.composition.refresh_wizard_shell_composition(
            assembled,
            progress=progress,
        )

        self.assertEqual(assembled.presenter.progress, progress)
        self.assertEqual(assembled.shell.pages_stack.currentIndex(), 1)


if __name__ == "__main__":
    unittest.main()
