import unittest

from tests import _path  # noqa: F401
from qfit.analysis.application.frequent_start_points import (
    StartPointSample,
    analyze_frequent_start_points,
)


class FrequentStartPointsTests(unittest.TestCase):
    def test_returns_top_clusters_ranked_by_activity_count(self):
        samples = [
            StartPointSample(0, 0, "a1"),
            StartPointSample(12, 6, "a2"),
            StartPointSample(18, 8, "a3"),
            StartPointSample(1000, 1000, "b1"),
            StartPointSample(1015, 1010, "b2"),
            StartPointSample(5000, 5000, "c1"),
        ]

        clusters, radius_m = analyze_frequent_start_points(samples)

        self.assertGreater(radius_m, 0)
        self.assertEqual([cluster.activity_count for cluster in clusters[:3]], [3, 2, 1])
        self.assertEqual([cluster.rank for cluster in clusters[:3]], [1, 2, 3])
        self.assertGreater(clusters[0].marker_size, clusters[1].marker_size)
        self.assertGreater(clusters[1].marker_size, clusters[2].marker_size)

    def test_limits_results_to_top_ten_clusters(self):
        samples = [StartPointSample(i * 1000.0, 0.0, str(i)) for i in range(15)]

        clusters, _radius_m = analyze_frequent_start_points(samples)

        self.assertEqual(len(clusters), 10)
        self.assertEqual(clusters[-1].rank, 10)

    def test_single_sample_uses_default_radius_and_marker_size(self):
        clusters, radius_m = analyze_frequent_start_points([StartPointSample(50.0, 75.0, "solo")])

        self.assertEqual(radius_m, 75.0)
        self.assertEqual(len(clusters), 1)
        self.assertEqual(clusters[0].activity_count, 1)
        self.assertEqual(clusters[0].marker_size, 7.0)

    def test_same_size_clusters_share_default_marker_size(self):
        samples = [
            StartPointSample(0.0, 0.0, "a1"),
            StartPointSample(8.0, 5.0, "a2"),
            StartPointSample(1000.0, 1000.0, "b1"),
            StartPointSample(1010.0, 1005.0, "b2"),
        ]

        clusters, _radius_m = analyze_frequent_start_points(samples)

        self.assertEqual([cluster.activity_count for cluster in clusters], [2, 2])
        self.assertEqual([cluster.marker_size for cluster in clusters], [7.0, 7.0])

    def test_empty_input_returns_no_clusters(self):
        clusters, radius_m = analyze_frequent_start_points([])

        self.assertEqual(clusters, [])
        self.assertEqual(radius_m, 0.0)


if __name__ == "__main__":
    unittest.main()
