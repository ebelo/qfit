import unittest
from unittest.mock import patch

from tests import _path  # noqa: F401
from QFIT.strava_client import StravaClient


class StravaClientTests(unittest.TestCase):
    def test_build_authorize_url_uses_defaults(self):
        client = StravaClient(client_id="123")
        url = client.build_authorize_url()

        self.assertIn("client_id=123", url)
        self.assertIn("response_type=code", url)
        self.assertIn("approval_prompt=force", url)
        self.assertIn("scope=read%2Cactivity%3Aread_all", url)

    def test_normalize_activity_maps_core_fields(self):
        client = StravaClient()
        activity = client.normalize_activity(
            {
                "id": 42,
                "name": "Morning Ride",
                "type": "Ride",
                "sport_type": "GravelRide",
                "start_date": "2026-03-20T06:00:00Z",
                "start_date_local": "2026-03-20T07:00:00Z",
                "timezone": "(GMT+01:00) Europe/Zurich",
                "distance": 12345.6,
                "moving_time": 3600,
                "elapsed_time": 3900,
                "total_elevation_gain": 321.0,
                "average_speed": 3.4,
                "max_speed": 9.9,
                "start_latlng": [46.5, 6.6],
                "end_latlng": [46.6, 6.7],
                "map": {"summary_polyline": "abc"},
                "private_note": "keep me in details",
            }
        )

        self.assertEqual(activity.source, "strava")
        self.assertEqual(activity.source_activity_id, "42")
        self.assertEqual(activity.activity_type, "Ride")
        self.assertEqual(activity.sport_type, "GravelRide")
        self.assertEqual(activity.start_lat, 46.5)
        self.assertEqual(activity.end_lon, 6.7)
        self.assertEqual(activity.summary_polyline, "abc")
        self.assertEqual(activity.geometry_source, "summary_polyline")
        self.assertEqual(activity.details_json["private_note"], "keep me in details")
        self.assertIn("normalized_at", activity.details_json)

    def test_extract_stream_bundle_supports_dict_and_list_payloads(self):
        client = StravaClient()

        self.assertEqual(
            client._extract_stream_bundle(
                {
                    "latlng": {"data": [[46.5, 6.6], [46.6, 6.7]]},
                    "time": {"data": [0, 10]},
                }
            ),
            {"latlng": [[46.5, 6.6], [46.6, 6.7]], "time": [0, 10]},
        )
        self.assertEqual(
            client._extract_stream_bundle(
                [
                    {"type": "latlng", "data": [[46.5, 6.6], [46.6, 6.7]]},
                    {"type": "time", "data": [0, 10]},
                ]
            ),
            {"latlng": [[46.5, 6.6], [46.6, 6.7]], "time": [0, 10]},
        )

    def test_apply_stream_bundle_updates_activity(self):
        client = StravaClient()
        activity = client.normalize_activity({"id": 42, "name": "Run"})

        result = client._apply_stream_bundle_to_activity(
            activity,
            {"latlng": [[46.5, 6.6], [46.6, 6.7]], "time": [0, 10]},
        )

        self.assertTrue(result)
        self.assertEqual(activity.geometry_source, "stream")
        self.assertEqual(activity.geometry_points, [(46.5, 6.6), (46.6, 6.7)])
        self.assertEqual(activity.details_json["stream_point_count"], 2)
        self.assertEqual(activity.details_json["stream_metrics"], {"time": [0, 10]})
        self.assertEqual(activity.details_json["stream_metric_keys"], ["time"])

    def test_enrich_activities_uses_cache_before_network(self):
        client = StravaClient()
        activity = client.normalize_activity({"id": 42, "name": "Run"})

        with patch.object(client, "_load_cached_stream_bundle", return_value={"latlng": [[46.5, 6.6]]}), patch.object(
            client, "fetch_activity_stream_bundle"
        ) as fetch_mock:
            client.enrich_activities_with_streams([activity])

        fetch_mock.assert_not_called()
        self.assertEqual(client.last_stream_enrichment_stats["cached"], 1)
        self.assertEqual(activity.details_json["stream_cache"], "hit")

    def test_parse_rate_limit_pair_and_remaining(self):
        client = StravaClient()
        self.assertEqual(client._parse_rate_limit_pair("200, 2000"), (200, 2000))
        self.assertEqual(client._parse_rate_limit_pair("bad"), (None, None))
        self.assertEqual(client._remaining(200, 50), 150)
        self.assertIsNone(client._remaining(None, 50))


if __name__ == "__main__":
    unittest.main()
