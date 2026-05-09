import unittest

from tests import _path  # noqa: F401

from qfit.ui.application.local_first_control_moves import (
    LOCAL_FIRST_CONTROL_MOVES,
    local_first_control_move_for_key,
    local_first_control_move_keys,
)


class LocalFirstControlMoveTests(unittest.TestCase):
    def test_control_move_inventory_covers_current_legacy_backed_surfaces(self):
        self.assertEqual(
            local_first_control_move_keys(),
            (
                "advanced_fetch",
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
                "advancedFetchGroupBox",
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
                "advanced_fetch": "sync_content",
                "activity_preview": "sync_content",
                "backfill_routes": "sync_content",
                "map_filters": "map_content",
                "atlas_pdf": "atlas_content",
                "basemap": "connection_content",
                "storage": "connection_content",
            },
        )

    def test_lookup_returns_full_install_metadata(self):
        move = local_first_control_move_for_key("atlas_pdf")

        self.assertEqual(move.content_attr, "atlas_content")
        self.assertEqual(move.group_attr, "atlasPdfGroupBox")
        self.assertEqual(move.title, "PDF output")
        self.assertTrue(move.show_after_move)

        backfill = local_first_control_move_for_key("backfill_routes")
        self.assertFalse(backfill.show_after_move)

        filters = local_first_control_move_for_key("map_filters")
        self.assertEqual(filters.layout_getter_attr, "filter_controls_layout")
        self.assertEqual(filters.parent_panel_attr, "filter_controls_panel")

    def test_lookup_rejects_unknown_control_area(self):
        with self.assertRaises(KeyError):
            local_first_control_move_for_key("credentials")


if __name__ == "__main__":
    unittest.main()
