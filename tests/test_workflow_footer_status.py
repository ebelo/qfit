import unittest

from tests import _path  # noqa: F401

from qfit.ui.application.workflow_footer_status import (
    WorkflowFooterFacts,
    build_workflow_footer_facts_from_progress_facts,
    build_workflow_footer_status,
)
from qfit.ui.application.workflow_progress_facts import WorkflowProgressFacts


class WorkflowFooterStatusTests(unittest.TestCase):
    def test_builds_compact_status_from_workflow_page_facts(self):
        self.assertEqual(
            build_workflow_footer_status(
                connection_status="Strava connected",
                activity_summary="12 activities stored",
                map_summary="3 layers loaded",
                analysis_status="Analysis ready",
                atlas_status="Atlas PDF not exported yet",
            ),
            "Strava connected · 12 activities stored · 3 layers loaded · "
            "Analysis ready · Atlas PDF not exported yet",
        )

    def test_omits_empty_and_duplicate_parts(self):
        self.assertEqual(
            build_workflow_footer_status(
                connection_status="Ready",
                activity_summary="",
                map_summary=None,
                analysis_status="Ready",
                atlas_status=" ",
            ),
            "Ready",
        )

    def test_falls_back_to_ready_when_no_status_parts_are_available(self):
        self.assertEqual(
            build_workflow_footer_status(
                connection_status="",
                activity_summary=None,
                map_summary=" ",
                analysis_status="",
                atlas_status=None,
            ),
            "Ready",
        )

    def test_builds_explicit_footer_facts_from_progress_facts(self):
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
            build_workflow_footer_facts_from_progress_facts(facts),
            WorkflowFooterFacts(
                strava_connected=True,
                activity_count=12,
                layer_count=4,
                gpkg_path="qfit.gpkg",
                last_sync_date="2026-04-16",
            ),
        )

    def test_footer_facts_do_not_report_unstored_or_unloaded_counts(self):
        facts = WorkflowProgressFacts(
            connection_configured=True,
            activities_fetched=True,
            fetched_activity_count=5,
            activity_count=99,
            loaded_layer_count=4,
        )

        self.assertEqual(
            build_workflow_footer_facts_from_progress_facts(facts),
            WorkflowFooterFacts(
                strava_connected=True,
                activity_count=None,
                layer_count=0,
                gpkg_path=None,
            ),
        )

    def test_footer_facts_fall_back_to_single_loaded_layer_when_count_unknown(self):
        facts = WorkflowProgressFacts(activity_layers_loaded=True)

        self.assertEqual(
            build_workflow_footer_facts_from_progress_facts(facts).layer_count,
            1,
        )

    def test_footer_facts_ignore_blank_last_sync_date(self):
        facts = WorkflowProgressFacts(last_sync_date="   ")

        self.assertIsNone(
            build_workflow_footer_facts_from_progress_facts(facts).last_sync_date
        )


if __name__ == "__main__":
    unittest.main()
