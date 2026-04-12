import unittest

from tests import _path  # noqa: F401

from qfit.visualization.application.visual_apply_messages import (
    append_visual_apply_temporal_note,
    build_filtered_visual_apply_status,
    build_visual_apply_status,
)


class VisualApplyMessagesTests(unittest.TestCase):
    def test_build_filtered_visual_apply_status(self):
        self.assertEqual(
            build_filtered_visual_apply_status(42),
            "Applied filters and styling (42 matching activities)",
        )

    def test_append_visual_apply_temporal_note(self):
        self.assertEqual(
            append_visual_apply_temporal_note(
                "Applied styling to the loaded qfit layers",
                "Temporal mode: Monthly",
            ),
            "Applied styling to the loaded qfit layers. Temporal mode: Monthly.",
        )

    def test_append_visual_apply_temporal_note_returns_status_when_empty(self):
        self.assertEqual(
            append_visual_apply_temporal_note(
                "Applied styling to the loaded qfit layers",
                "",
            ),
            "Applied styling to the loaded qfit layers",
        )

    def test_build_visual_apply_status_for_filtered_apply(self):
        self.assertEqual(
            build_visual_apply_status(True, True, 42, False, False),
            "Applied filters and styling (42 matching activities)",
        )

    def test_build_visual_apply_status_for_styled_background_loaded(self):
        self.assertEqual(
            build_visual_apply_status(True, False, 0, True, True),
            "Applied styling and loaded the background map below the qfit activity layers",
        )

    def test_build_visual_apply_status_for_styled_only(self):
        self.assertEqual(
            build_visual_apply_status(True, False, 0, False, False),
            "Applied styling to the loaded qfit layers",
        )

    def test_build_visual_apply_status_for_background_only(self):
        self.assertEqual(
            build_visual_apply_status(False, False, 0, True, True),
            "Background map loaded below the qfit activity layers",
        )

    def test_build_visual_apply_status_for_background_cleared(self):
        self.assertEqual(
            build_visual_apply_status(False, False, 0, False, False),
            "Background map cleared",
        )


if __name__ == "__main__":
    unittest.main()
