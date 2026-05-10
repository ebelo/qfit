import unittest

from tests import _path  # noqa: F401

from qfit.ui.application.local_first_control_moves import (
    HIDE_LEGACY_ATLAS_EXPORT_BUTTON_HOOK,
    LOCAL_FIRST_CONTROL_MOVES,
    LOCAL_FIRST_WIDGET_MOVES,
    REFRESH_CONDITIONAL_VISIBILITY_HOOK,
    local_first_control_move_for_key,
    local_first_control_move_keys,
    local_first_widget_move_for_key,
    local_first_widget_move_keys,
)


class LocalFirstControlMoveTests(unittest.TestCase):
    def test_control_move_inventory_covers_current_legacy_backed_surfaces(self):
        self.assertEqual(
            local_first_control_move_keys(),
            (
                "activity_preview",
                "backfill_routes",
                "map_filters",
                "atlas_pdf",
                "basemap",
                "storage",
            ),
        )
        self.assertEqual(
            [move.group_attr for move in LOCAL_FIRST_CONTROL_MOVES],
            [
                "previewGroupBox",
                "backfillMissingDetailedRoutesButton",
                "filterGroupBox",
                "atlasPdfGroupBox",
                "backgroundGroupBox",
                "outputGroupBox",
            ],
        )

    def test_control_moves_document_local_first_destination_pages(self):
        destinations = {
            move.key: move.content_attr for move in LOCAL_FIRST_CONTROL_MOVES
        }

        self.assertEqual(
            destinations,
            {
                "activity_preview": "sync_content",
                "backfill_routes": "sync_content",
                "map_filters": "map_content",
                "atlas_pdf": "atlas_content",
                "basemap": "settings_content",
                "storage": "settings_content",
            },
        )

    def test_control_moves_document_required_supported_controls(self):
        required_widgets = {
            move.key: move.required_widget_attrs for move in LOCAL_FIRST_CONTROL_MOVES
        }

        self.assertEqual(
            required_widgets,
            {
                "activity_preview": (
                    "querySummaryLabel",
                    "activityPreviewPlainTextEdit",
                ),
                "backfill_routes": (),
                "map_filters": (
                    "activityTypeComboBox",
                    "activitySearchLineEdit",
                    "dateFromEdit",
                    "dateToEdit",
                    "minDistanceSpinBox",
                    "maxDistanceSpinBox",
                    "detailedRouteStatusComboBox",
                ),
                "atlas_pdf": ("atlasPdfPathLineEdit", "atlasPdfBrowseButton"),
                "basemap": (
                    "backgroundMapCheckBox",
                    "backgroundPresetComboBox",
                    "mapboxStyleOwnerLineEdit",
                    "mapboxStyleIdLineEdit",
                    "tileModeComboBox",
                    "loadBackgroundButton",
                ),
                "storage": (
                    "outputPathLineEdit",
                    "browseButton",
                    "writeActivityPointsCheckBox",
                    "pointSamplingStrideSpinBox",
                ),
            },
        )

    def test_lookup_returns_full_install_metadata(self):
        move = local_first_control_move_for_key("atlas_pdf")

        self.assertEqual(move.content_attr, "atlas_content")
        self.assertEqual(move.group_attr, "atlasPdfGroupBox")
        self.assertEqual(
            move.required_widget_attrs,
            ("atlasPdfPathLineEdit", "atlasPdfBrowseButton"),
        )
        self.assertEqual(move.title, "PDF output")
        self.assertTrue(move.show_after_move)
        self.assertEqual(
            move.after_install_hook_key,
            HIDE_LEGACY_ATLAS_EXPORT_BUTTON_HOOK,
        )

        backfill = local_first_control_move_for_key("backfill_routes")
        self.assertTrue(backfill.show_after_move)
        self.assertEqual(
            backfill.after_install_hook_key,
            REFRESH_CONDITIONAL_VISIBILITY_HOOK,
        )

        filters = local_first_control_move_for_key("map_filters")
        self.assertEqual(filters.layout_getter_attr, "filter_controls_layout")
        self.assertEqual(filters.parent_panel_attr, "filter_controls_panel")
        self.assertEqual(filters.post_install_visible_attr, "set_filter_controls_visible")
        self.assertIsNone(filters.after_install_hook_key)

    def test_control_moves_document_post_install_hooks(self):
        hooks = {
            move.key: move.after_install_hook_key for move in LOCAL_FIRST_CONTROL_MOVES
        }

        self.assertEqual(
            hooks,
            {
                "activity_preview": None,
                "backfill_routes": REFRESH_CONDITIONAL_VISIBILITY_HOOK,
                "map_filters": None,
                "atlas_pdf": HIDE_LEGACY_ATLAS_EXPORT_BUTTON_HOOK,
                "basemap": REFRESH_CONDITIONAL_VISIBILITY_HOOK,
                "storage": REFRESH_CONDITIONAL_VISIBILITY_HOOK,
            },
        )

    def test_widget_move_inventory_covers_loose_visualization_controls(self):
        self.assertEqual(
            local_first_widget_move_keys(),
            ("activity_style",),
        )

        activity_style = LOCAL_FIRST_WIDGET_MOVES[0]
        self.assertEqual(activity_style.content_attr, "map_content")
        self.assertEqual(
            activity_style.required_widget_attrs,
            ("stylePresetLabel", "stylePresetComboBox"),
        )
        self.assertEqual(activity_style.optional_widget_groups, ())
        self.assertEqual(activity_style.optional_widget_attrs, ())
        self.assertEqual(activity_style.layout_getter_attr, "style_controls_layout")
        self.assertEqual(activity_style.parent_panel_attr, "style_controls_panel")
        self.assertEqual(
            activity_style.post_install_visible_attr,
            "set_style_controls_visible",
        )

    def test_widget_move_lookup_returns_full_install_metadata(self):
        move = local_first_widget_move_for_key("activity_style")

        self.assertEqual(
            move.installed_attr,
            "_local_first_activity_style_controls_installed",
        )
        self.assertEqual(
            move.installed_target_attr,
            "_local_first_activity_style_controls_installed_target",
        )

    def test_lookup_rejects_unknown_control_area(self):
        with self.assertRaises(KeyError):
            local_first_control_move_for_key("credentials")
        with self.assertRaises(KeyError):
            local_first_widget_move_for_key("credentials")


if __name__ == "__main__":
    unittest.main()
