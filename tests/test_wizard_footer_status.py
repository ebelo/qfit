import unittest

from tests import _path  # noqa: F401

from qfit.ui.application import wizard_footer_status as wizard_footer
from qfit.ui.application import workflow_footer_status as workflow_footer
from qfit.ui.application.workflow_progress_facts import WorkflowProgressFacts


class WizardFooterStatusCompatibilityTests(unittest.TestCase):
    def test_wizard_footer_facts_aliases_workflow_footer_facts(self):
        self.assertIs(
            wizard_footer.WizardFooterFacts,
            workflow_footer.WorkflowFooterFacts,
        )

    def test_wizard_footer_status_delegates_to_workflow_footer_status(self):
        kwargs = {
            "connection_status": "Strava connected",
            "activity_summary": "12 activities stored",
            "map_summary": "3 layers loaded",
            "analysis_status": "Analysis ready",
            "atlas_status": "Atlas PDF not exported yet",
        }

        self.assertEqual(
            wizard_footer.build_wizard_footer_status(**kwargs),
            workflow_footer.build_workflow_footer_status(**kwargs),
        )

    def test_wizard_footer_facts_builder_delegates_to_workflow_footer_builder(self):
        facts = WorkflowProgressFacts(
            connection_configured=True,
            activities_stored=True,
            activity_layers_loaded=True,
            activity_count=12,
            output_name="qfit.gpkg",
            loaded_layer_count=4,
            last_sync_date="2026-04-16",
        )

        self.assertEqual(
            wizard_footer.build_wizard_footer_facts_from_progress_facts(facts),
            workflow_footer.build_workflow_footer_facts_from_progress_facts(facts),
        )

    def test_wizard_footer_module_keeps_compat_exports(self):
        self.assertEqual(
            set(wizard_footer.__all__),
            {
                "WizardFooterFacts",
                "build_wizard_footer_facts_from_progress_facts",
                "build_wizard_footer_status",
            },
        )


if __name__ == "__main__":
    unittest.main()
