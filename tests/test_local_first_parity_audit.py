import unittest
from types import SimpleNamespace
from unittest.mock import patch

from tests import _path  # noqa: F401

from qfit.ui.application.local_first_control_moves import (
    local_first_control_move_for_key,
    local_first_widget_move_for_key,
)
from qfit.ui.application import local_first_parity_audit as audit
from qfit.ui.application.local_first_parity_audit import (
    ISSUE_805_REQUIRED_AREAS,
    build_issue805_local_first_parity_surfaces,
    issue805_local_first_coverage_by_area,
    missing_issue805_local_first_areas,
)


class LocalFirstParityAuditTests(unittest.TestCase):
    def test_issue_805_acceptance_areas_all_have_audited_surfaces(self):
        self.assertEqual(missing_issue805_local_first_areas(), ())
        self.assertEqual(
            tuple(issue805_local_first_coverage_by_area()),
            ISSUE_805_REQUIRED_AREAS,
        )

    def test_audit_documents_current_local_first_surfaces_by_area(self):
        coverage = issue805_local_first_coverage_by_area()

        self.assertEqual(
            coverage,
            {
                "mapbox_background_map": ("basemap",),
                "activity_visualization_options": (
                    "activity_style",
                    "activity_preview",
                ),
                "map_filters": ("map_filters", "map_actions"),
                "data_storage_settings": (
                    "backfill_routes",
                    "storage",
                    "data_actions",
                ),
                "analysis_controls": (
                    "analysis_temporal",
                    "analysis_actions",
                ),
                "atlas_export_controls": ("atlas_pdf", "atlas_actions"),
                "connection_settings_controls": (
                    "settings_configuration_action",
                ),
            },
        )

    def test_audit_uses_control_move_inventory_for_legacy_backed_widgets(self):
        surfaces = {
            surface.key: surface
            for surface in build_issue805_local_first_parity_surfaces()
        }

        basemap = local_first_control_move_for_key("basemap")
        self.assertEqual(surfaces["basemap"].local_first_page, "settings")
        self.assertEqual(
            surfaces["basemap"].required_widget_attrs,
            basemap.required_widget_attrs,
        )
        self.assertIn("loadBackgroundButton", surfaces["basemap"].required_widget_attrs)

        storage = local_first_control_move_for_key("storage")
        self.assertEqual(surfaces["storage"].local_first_page, "settings")
        self.assertEqual(
            surfaces["storage"].required_widget_attrs,
            storage.required_widget_attrs,
        )
        self.assertIn("browseButton", surfaces["storage"].required_widget_attrs)

    def test_audit_includes_loose_widget_and_local_first_action_surfaces(self):
        surfaces = {
            surface.key: surface
            for surface in build_issue805_local_first_parity_surfaces()
        }

        activity_style = local_first_widget_move_for_key("activity_style")
        self.assertEqual(surfaces["activity_style"].local_first_page, "map")
        self.assertEqual(
            surfaces["activity_style"].required_widget_attrs,
            activity_style.required_widget_attrs,
        )
        self.assertEqual(
            surfaces["activity_style"].optional_widget_attrs,
            ("previewSortLabel", "previewSortComboBox"),
        )
        self.assertEqual(
            surfaces["analysis_actions"].action_names,
            (
                "runAnalysisRequested",
                "clearAnalysisRequested",
                "analysisModeChanged",
            ),
        )
        self.assertEqual(
            surfaces["settings_configuration_action"].action_names,
            ("configureRequested",),
        )

    def test_coverage_by_area_keeps_empty_required_areas_visible(self):
        with patch.object(
            audit,
            "build_issue805_local_first_parity_surfaces",
            return_value=(),
        ):
            coverage = issue805_local_first_coverage_by_area()

        self.assertEqual(tuple(coverage), ISSUE_805_REQUIRED_AREAS)
        self.assertTrue(all(keys == () for keys in coverage.values()))

    def test_audit_rejects_unmapped_move_keys_with_context(self):
        move = SimpleNamespace(
            key="new_control",
            content_attr="sync_content",
            required_widget_attrs=(),
        )

        with patch.object(audit, "LOCAL_FIRST_WIDGET_MOVES", ()), patch.object(
            audit,
            "LOCAL_FIRST_CONTROL_MOVES",
            (move,),
        ):
            with self.assertRaisesRegex(
                ValueError,
                "LOCAL_FIRST_CONTROL_MOVES key 'new_control'",
            ):
                build_issue805_local_first_parity_surfaces()

    def test_audit_rejects_unknown_content_attrs_with_context(self):
        move = SimpleNamespace(
            key="backfill_routes",
            content_attr="onboarding_content",
            required_widget_attrs=(),
        )

        with patch.object(audit, "LOCAL_FIRST_WIDGET_MOVES", ()), patch.object(
            audit,
            "LOCAL_FIRST_CONTROL_MOVES",
            (move,),
        ):
            with self.assertRaisesRegex(
                ValueError,
                "content_attr 'onboarding_content'",
            ):
                build_issue805_local_first_parity_surfaces()

    def test_application_package_reexports_parity_audit_helpers(self):
        from qfit import ui
        from qfit.ui import application

        self.assertIn("LocalFirstParitySurface", application.__all__)
        self.assertIs(
            application.build_issue805_local_first_parity_surfaces,
            build_issue805_local_first_parity_surfaces,
        )
        self.assertTrue(hasattr(ui.application, "missing_issue805_local_first_areas"))


if __name__ == "__main__":
    unittest.main()
