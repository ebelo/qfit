import unittest

from tests import _path  # noqa: F401

from qfit.visualization.application.background_map_messages import (
    build_background_map_cleared_status,
    build_background_map_failure_status,
    build_background_map_failure_title,
    build_background_map_loaded_status,
    build_styled_background_map_loaded_status,
)


class BackgroundMapMessagesTests(unittest.TestCase):
    def test_build_background_map_cleared_status(self):
        self.assertEqual(
            build_background_map_cleared_status(),
            "Background map cleared",
        )

    def test_build_background_map_failure_status(self):
        self.assertEqual(
            build_background_map_failure_status(),
            "Background map could not be updated",
        )

    def test_build_background_map_failure_title(self):
        self.assertEqual(build_background_map_failure_title(), "Background map failed")

    def test_build_background_map_loaded_status(self):
        self.assertEqual(
            build_background_map_loaded_status(),
            "Background map loaded below the qfit activity layers",
        )

    def test_build_styled_background_map_loaded_status(self):
        self.assertEqual(
            build_styled_background_map_loaded_status(),
            "Applied styling and loaded the background map below the qfit activity layers",
        )


if __name__ == "__main__":
    unittest.main()
