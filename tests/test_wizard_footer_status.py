import unittest

from tests import _path  # noqa: F401

from qfit.ui.application.wizard_footer_status import build_wizard_footer_status


class WizardFooterStatusTests(unittest.TestCase):
    def test_builds_compact_status_from_wizard_page_facts(self):
        self.assertEqual(
            build_wizard_footer_status(
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
            build_wizard_footer_status(
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
            build_wizard_footer_status(
                connection_status="",
                activity_summary=None,
                map_summary=" ",
                analysis_status="",
                atlas_status=None,
            ),
            "Ready",
        )


if __name__ == "__main__":
    unittest.main()
