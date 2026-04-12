import unittest

from tests import _path  # noqa: F401

from qfit.visualization.application.visual_apply_messages import (
    build_filtered_visual_apply_status,
)


class VisualApplyMessagesTests(unittest.TestCase):
    def test_build_filtered_visual_apply_status(self):
        self.assertEqual(
            build_filtered_visual_apply_status(42),
            "Applied filters and styling (42 matching activities)",
        )


if __name__ == "__main__":
    unittest.main()
