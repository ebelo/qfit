import unittest

from tests import _path  # noqa: F401

from qfit.visualization.application.background_map_messages import (
    build_background_map_failure_title,
)


class BackgroundMapMessagesTests(unittest.TestCase):
    def test_build_background_map_failure_title(self):
        self.assertEqual(build_background_map_failure_title(), "Background map failed")


if __name__ == "__main__":
    unittest.main()
