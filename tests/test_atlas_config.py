import unittest

from tests import _path  # noqa: F401
from qfit.atlas.application.atlas_config import estimate_size_mb, estimate_time_min


class AtlasConfigTests(unittest.TestCase):
    def test_estimates_single_page_with_minimum_display_values(self):
        self.assertEqual(estimate_time_min(1), 1)
        self.assertEqual(estimate_size_mb(1), 0.1)

    def test_estimates_larger_exports_from_spec_baselines(self):
        self.assertEqual(estimate_time_min(300), 2)
        self.assertEqual(estimate_size_mb(300), 8.2)

    def test_rounds_half_minute_estimates_up(self):
        self.assertEqual(estimate_time_min(375), 3)

    def test_treats_negative_page_counts_as_empty_exports(self):
        self.assertEqual(estimate_time_min(-10), 1)
        self.assertEqual(estimate_size_mb(-10), 0.0)


if __name__ == "__main__":
    unittest.main()
