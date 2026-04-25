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
        assembled = self.composition.build_placeholder_wizard_shell()
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


if __name__ == "__main__":
    unittest.main()
