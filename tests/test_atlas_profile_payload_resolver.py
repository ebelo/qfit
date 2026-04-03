import json
import os
import sqlite3
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from tests import _path  # noqa: F401

from qfit.atlas import profile_payload_resolver


class TestPageProfilePayloadResolver(unittest.TestCase):
    def test_build_page_profile_payload_collects_native_inputs(self):
        feat = MagicMock(name="feature")
        feat.geometry.return_value = "feature-geometry"

        payload = profile_payload_resolver.build_page_profile_payload(feat, [])

        self.assertEqual(payload.feature_geometry, "feature-geometry")
        self.assertIs(payload.feature, feat)

        with patch.object(
            profile_payload_resolver,
            "build_native_profile_curve_from_feature",
            return_value="curve",
        ) as build_native_curve:
            native_curve, native_request = payload.native_inputs()

        self.assertEqual(native_curve, "curve")
        self.assertIsNone(native_request)
        build_native_curve.assert_called_once_with(
            "feature-geometry",
            feature=feat,
            altitudes=[],
        )

    def test_prefers_filtered_activity_line_geometry(self):
        atlas_feature = MagicMock(name="atlas_feature")
        atlas_feature.geometry.return_value = "atlas-polygon"

        point_feature = MagicMock(name="point_feature")
        point_feature.geometry.return_value = "point-geometry"
        point_layer = MagicMock(name="point_layer")
        point_layer.getFeatures.side_effect = lambda: iter([point_feature])

        line_feature = MagicMock(name="line_feature")
        line_feature.geometry.return_value = "line-geometry"
        line_layer = MagicMock(name="line_layer")
        line_layer.getFeatures.side_effect = lambda: iter([line_feature])

        with patch.object(
            profile_payload_resolver,
            "build_native_profile_curve",
            side_effect=lambda geometry: "curve" if geometry == "line-geometry" else None,
        ):
            payload = profile_payload_resolver.build_page_profile_payload(
                atlas_feature,
                [(point_layer, ""), (line_layer, "")],
            )

        self.assertEqual(payload.feature_geometry, "line-geometry")

    def test_uses_profile_sample_lookup_for_source_activity(self):
        feat = MagicMock(name="feature")
        feat.geometry.return_value = "feature-geometry"
        feat.attribute.side_effect = lambda name: "activity-42" if name == "source_activity_id" else None

        lookup = MagicMock(return_value=[(0.0, 450.0), (1000.0, 530.0)])

        payload = profile_payload_resolver.build_page_profile_payload(
            feat,
            [],
            profile_altitude_lookup=lookup,
        )

        self.assertEqual(payload.page_points, [(0.0, 450.0), (1000.0, 530.0)])
        lookup.assert_called_once_with("activity-42")

    def test_falls_back_to_details_json_from_filtered_layer(self):
        atlas_feature = MagicMock(name="atlas_feature")
        atlas_feature.geometry.return_value = "atlas-z-line"
        atlas_feature.attribute.side_effect = lambda name: {
            "source_activity_id": "activity-42",
            "details_json": None,
        }.get(name)

        filtered_feature = MagicMock(name="filtered_feature")
        filtered_feature.geometry.return_value = "line-geometry"
        filtered_feature.attribute.side_effect = lambda name: {
            "source_activity_id": "activity-42",
            "details_json": json.dumps(
                {
                    "stream_metrics": {
                        "distance": [0, 1000],
                        "altitude": [450, 530],
                    }
                }
            ),
        }.get(name)
        filtered_layer = MagicMock(name="filtered_layer")
        filtered_layer.getFeatures.side_effect = lambda: iter([filtered_feature])

        with patch.object(
            profile_payload_resolver,
            "build_native_profile_curve",
            side_effect=lambda geometry: "curve" if geometry == "atlas-z-line" else None,
        ):
            payload = profile_payload_resolver.build_page_profile_payload(
                atlas_feature,
                [(filtered_layer, "")],
            )

        self.assertEqual(payload.page_points, [(0.0, 450.0), (1000.0, 530.0)])
        self.assertEqual(payload.feature_geometry, "atlas-z-line")
        self.assertIs(payload.feature, atlas_feature)


class TestAtlasProfileSampleLookup(unittest.TestCase):
    def test_reads_ordered_altitudes_from_gpkg(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            gpkg_path = os.path.join(tmp_dir, "profile-samples.gpkg")
            with sqlite3.connect(gpkg_path) as conn:
                conn.execute(
                    """
                    CREATE TABLE atlas_profile_samples (
                        source_activity_id TEXT,
                        profile_point_index INTEGER,
                        distance_m REAL,
                        altitude_m REAL
                    )
                    """
                )
                conn.executemany(
                    "INSERT INTO atlas_profile_samples VALUES (?, ?, ?, ?)",
                    [
                        ("activity-1", 2, 2000.0, 530.0),
                        ("activity-1", 0, 0.0, 450.0),
                        ("activity-1", 1, 1000.0, 490.0),
                    ],
                )

            atlas_layer = MagicMock(name="atlas_layer")
            atlas_layer.source.return_value = f"{gpkg_path}|layername=activity_atlas_pages"

            lookup = profile_payload_resolver.AtlasProfileSampleLookup(atlas_layer)

            self.assertEqual(
                lookup.lookup("activity-1"),
                [(0.0, 450.0), (1000.0, 490.0), (2000.0, 530.0)],
            )
            self.assertIsNone(lookup.lookup("missing"))


if __name__ == "__main__":
    unittest.main()
