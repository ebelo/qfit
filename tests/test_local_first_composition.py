import importlib
import sys
import unittest
from unittest.mock import patch

from tests import _path  # noqa: F401
from tests.test_wizard_shell import _fake_qt_modules

from qfit.ui.application.wizard_progress import WizardProgressFacts


def _load_local_first_composition_module():
    for name in (
        "qfit.ui.dockwidget.local_first_composition",
        "qfit.ui.dockwidget.local_first_shell",
        "qfit.ui.dockwidget.wizard_composition",
        "qfit.ui.dockwidget.analysis_page",
        "qfit.ui.dockwidget.atlas_page",
        "qfit.ui.dockwidget.connection_page",
        "qfit.ui.dockwidget.map_page",
        "qfit.ui.dockwidget.sync_page",
        "qfit.ui.dockwidget.action_row",
        "qfit.ui.dockwidget.footer_status_bar",
        "qfit.ui.dockwidget",
    ):
        sys.modules.pop(name, None)
    with patch.dict(sys.modules, _fake_qt_modules()):
        return importlib.import_module("qfit.ui.dockwidget.local_first_composition")


class LocalFirstDockCompositionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = _load_local_first_composition_module()

    def test_builds_shell_with_local_first_pages_and_reused_content(self):
        composition = self.module.build_local_first_dock_composition(
            progress_facts=WizardProgressFacts(activities_stored=True),
        )

        self.assertEqual(composition.shell.objectName(), "qfitLocalFirstDockShell")
        self.assertEqual(composition.shell.page_count(), 5)
        self.assertEqual(
            tuple(composition.pages),
            ("data", "map", "analysis", "atlas", "settings"),
        )
        self.assertEqual(
            composition.pages["data"].objectName(),
            "qfitLocalFirstDockPage_data",
        )
        self.assertEqual(
            composition.page_content.data_content.objectName(),
            "qfitWizardSyncPageContent",
        )
        self.assertEqual(
            composition.page_content.settings_content.objectName(),
            "qfitWizardConnectionPageContent",
        )
        self.assertIs(composition.sync_content, composition.page_content.data_content)
        self.assertIs(
            composition.connection_content,
            composition.page_content.settings_content,
        )

    def test_data_page_is_local_first_and_navigation_is_not_step_locked(self):
        composition = self.module.build_local_first_dock_composition(
            progress_facts=WizardProgressFacts(
                activities_stored=True,
                preferred_current_key="settings",
            ),
        )

        self.assertEqual(composition.shell.current_key(), "settings")
        self.assertTrue(composition.shell.button_for_key("data").isEnabled())
        self.assertTrue(composition.shell.button_for_key("atlas").isEnabled())
        self.assertEqual(
            composition.sync_content.detail_label.text(),
            "Stored activities are ready to load from the existing GeoPackage.",
        )

    def test_connects_existing_page_action_callbacks(self):
        composition = self.module.build_local_first_dock_composition()
        calls = []
        callbacks = self.module.WizardActionCallbacks(
            configure_connection=lambda: calls.append("settings"),
            sync_activities=lambda: calls.append("sync"),
            sync_saved_routes=lambda: calls.append("routes"),
            load_activity_layers=lambda: calls.append("layers"),
            edit_map_filters=lambda visible: calls.append(f"filters:{visible}"),
            apply_map_filters=lambda: calls.append("apply"),
            run_analysis=lambda: calls.append("analysis"),
            set_analysis_mode=lambda mode: calls.append(f"mode:{mode}"),
            export_atlas=lambda: calls.append("atlas"),
        )

        self.module.connect_local_first_action_callbacks(composition, callbacks)
        composition.connection_content.configureRequested.emit()
        composition.sync_content.syncRequested.emit()
        composition.sync_content.syncRoutesRequested.emit()
        composition.sync_content.loadActivitiesRequested.emit()
        composition.map_content.loadLayersRequested.emit()
        composition.map_content.editFiltersRequested.emit(True)
        composition.map_content.applyFiltersRequested.emit()
        composition.analysis_content.runAnalysisRequested.emit()
        composition.analysis_content.analysisModeChanged.emit("Heatmap")
        composition.atlas_content.exportAtlasRequested.emit()

        self.assertEqual(
            calls,
            [
                "settings",
                "sync",
                "routes",
                "layers",
                "layers",
                "filters:True",
                "apply",
                "analysis",
                "mode:Heatmap",
                "atlas",
            ],
        )

    def test_refresh_updates_navigation_and_page_content_state(self):
        composition = self.module.build_local_first_dock_composition()

        self.module.refresh_local_first_dock_composition(
            composition,
            progress_facts=WizardProgressFacts(
                connection_configured=True,
                activities_stored=True,
                activity_layers_loaded=True,
                preferred_current_key="map",
                output_name="activities.gpkg",
            ),
        )

        self.assertEqual(composition.shell.current_key(), "map")
        self.assertTrue(composition.shell.button_for_key("map").property("current"))
        self.assertEqual(composition.sync_content.status_label.text(), "Activities stored")
        self.assertEqual(composition.map_content.status_label.text(), "Activity layers loaded")
        self.assertEqual(composition.connection_content.status_label.text(), "Strava connected")

    def test_refresh_preserves_current_page_without_explicit_preference(self):
        composition = self.module.build_local_first_dock_composition(
            progress_facts=WizardProgressFacts(preferred_current_key="atlas"),
        )

        self.module.refresh_local_first_dock_composition(
            composition,
            progress_facts=WizardProgressFacts(activities_stored=True),
        )

        self.assertEqual(composition.shell.current_key(), "atlas")
        self.assertTrue(composition.shell.button_for_key("atlas").property("current"))

    def test_public_exports_include_action_callbacks(self):
        self.assertIn("WizardActionCallbacks", self.module.__all__)


if __name__ == "__main__":
    unittest.main()
