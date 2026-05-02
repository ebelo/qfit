import unittest

from qfit.ui.application.local_first_navigation import (
    build_local_first_dock_navigation_state,
    local_first_dock_page_keys,
)
from qfit.ui.application.wizard_progress import WizardProgressFacts


class LocalFirstDockNavigationTests(unittest.TestCase):
    def test_builds_unlocked_local_first_pages_with_full_labels(self):
        navigation = build_local_first_dock_navigation_state()

        self.assertEqual(
            local_first_dock_page_keys(),
            ("data", "map", "analysis", "atlas", "settings"),
        )
        self.assertEqual(navigation.current_key, "data")
        self.assertEqual(
            [page.title for page in navigation.pages],
            ["Data", "Map", "Analysis", "Atlas", "Settings"],
        )
        self.assertTrue(all(page.enabled for page in navigation.pages))
        self.assertFalse(any("..." in page.title for page in navigation.pages))
        self.assertFalse(any("…" in page.title for page in navigation.pages))

    def test_preferred_current_page_is_resolved_without_locking(self):
        navigation = build_local_first_dock_navigation_state(
            WizardProgressFacts(preferred_current_key="atlas"),
        )

        self.assertEqual(navigation.current_key, "atlas")
        self.assertEqual(
            [page.key for page in navigation.pages if page.current],
            ["atlas"],
        )
        self.assertTrue(all(page.enabled for page in navigation.pages))

    def test_explicit_preferred_current_page_overrides_fact_preference(self):
        navigation = build_local_first_dock_navigation_state(
            WizardProgressFacts(preferred_current_key="settings"),
            preferred_current_key="map",
        )

        self.assertEqual(navigation.current_key, "map")
        self.assertEqual(
            [page.key for page in navigation.pages if page.current],
            ["map"],
        )

    def test_unknown_preferred_current_page_falls_back_to_data(self):
        navigation = build_local_first_dock_navigation_state(
            preferred_current_key="synchronization",
        )

        self.assertEqual(navigation.current_key, "data")
        self.assertEqual(
            [page.key for page in navigation.pages if page.current],
            ["data"],
        )

    def test_page_readiness_describes_state_without_gating_navigation(self):
        navigation = build_local_first_dock_navigation_state(
            WizardProgressFacts(
                connection_configured=True,
                activities_stored=True,
                activity_layers_loaded=True,
                analysis_generated=False,
                atlas_exported=False,
            ),
            preferred_current_key="analysis",
        )
        by_key = {page.key: page for page in navigation.pages}

        self.assertTrue(by_key["data"].ready)
        self.assertTrue(by_key["map"].ready)
        self.assertFalse(by_key["analysis"].ready)
        self.assertFalse(by_key["atlas"].ready)
        self.assertTrue(by_key["settings"].ready)
        self.assertTrue(by_key["analysis"].current)
        self.assertTrue(all(page.enabled for page in navigation.pages))

    def test_data_page_status_is_local_first_before_strava_configuration(self):
        navigation = build_local_first_dock_navigation_state(WizardProgressFacts())
        data_page = navigation.pages[0]

        self.assertEqual(data_page.key, "data")
        self.assertEqual(
            data_page.status_text,
            "Choose a local GeoPackage or sync from Strava",
        )


if __name__ == "__main__":
    unittest.main()
