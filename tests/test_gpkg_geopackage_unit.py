import importlib
import os
import sys
import unittest
from types import ModuleType
from unittest.mock import MagicMock, call, patch

from tests import _path  # noqa: F401

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


class GeoPackagePackageUnitTests(unittest.TestCase):
    def _module(self, name, **attrs):
        module = ModuleType(name)
        for key, value in attrs.items():
            setattr(module, key, value)
        return module

    def test_moved_gpkg_writer_and_root_shim_share_same_class(self):
        normalize_settings = MagicMock(return_value={"margin_percent": 12})
        bootstrap_empty_gpkg = MagicMock()
        build_and_write_all_layers = MagicMock()

        module_overrides = {
            "qfit.activities.infrastructure.geopackage.gpkg_schema": self._module(
                "qfit.activities.infrastructure.geopackage.gpkg_schema",
                GPKG_LAYER_SCHEMA={"activity_tracks": [("name", "String")]},
            ),
            "qfit.activities.infrastructure.geopackage.gpkg_write_orchestration": self._module(
                "qfit.activities.infrastructure.geopackage.gpkg_write_orchestration",
                bootstrap_empty_gpkg=bootstrap_empty_gpkg,
                build_and_write_all_layers=build_and_write_all_layers,
            ),
            "qfit.atlas.publish_atlas": self._module(
                "qfit.atlas.publish_atlas",
                normalize_atlas_page_settings=normalize_settings,
            ),
        }

        with patch.dict(sys.modules, module_overrides):
            sys.modules.pop("qfit.activities.infrastructure.geopackage.gpkg_writer", None)
            sys.modules.pop("qfit.gpkg_writer", None)

            moved = importlib.import_module(
                "qfit.activities.infrastructure.geopackage.gpkg_writer"
            )
            legacy = importlib.import_module("qfit.gpkg_writer")

            self.assertIs(legacy.GeoPackageWriter, moved.GeoPackageWriter)

            activity_store = MagicMock()
            activity_store.upsert_activities.return_value = {"added": 1}
            activity_store.load_all_activity_records.return_value = [{"name": "Morning Ride"}]
            layer = MagicMock()
            layer.featureCount.return_value = 1
            build_and_write_all_layers.return_value = {
                "activity_tracks": layer,
                "activity_starts": layer,
                "activity_points": layer,
                "activity_atlas_pages": layer,
                "atlas_document_summary": layer,
                "atlas_cover_highlights": layer,
                "atlas_page_detail_items": layer,
                "atlas_profile_samples": layer,
                "atlas_toc_entries": layer,
            }

            writer = moved.GeoPackageWriter(
                output_path="/tmp/qfit-unit.gpkg",
                write_activity_points=True,
                point_stride=5,
                atlas_margin_percent=12,
                activity_store_factory=lambda _path: activity_store,
            )

            self.assertEqual(writer.schema(), {"activity_tracks": [("name", "String")]})

            with patch("os.path.exists", return_value=False), patch("os.path.getsize", return_value=0):
                result = writer.write_activities(
                    [{"name": "Morning Ride"}],
                    sync_metadata={"provider": "strava"},
                )

            normalize_settings.assert_called_once_with(
                margin_percent=12,
                min_extent_degrees=None,
                target_aspect_ratio=None,
            )
            bootstrap_empty_gpkg.assert_called_once_with(
                "/tmp/qfit-unit.gpkg", {"margin_percent": 12}
            )
            build_and_write_all_layers.assert_called_once_with(
                [{"name": "Morning Ride"}],
                "/tmp/qfit-unit.gpkg",
                {"margin_percent": 12},
                write_activity_points=True,
                point_stride=5,
            )
            self.assertEqual(result["path"], "/tmp/qfit-unit.gpkg")
            self.assertEqual(result["sync"], {"added": 1})

    def test_moved_gpkg_write_orchestration_and_root_shim_share_same_functions(self):
        write_layer_to_gpkg = MagicMock()
        build_track_layer = MagicMock(side_effect=lambda records: ("tracks", tuple(records)))
        build_start_layer = MagicMock(side_effect=lambda records: ("starts", tuple(records)))
        build_point_layer = MagicMock(
            side_effect=lambda records, enabled=False, stride=1: (
                "points",
                tuple(records),
                enabled,
                stride,
            )
        )
        build_atlas_layer = MagicMock(
            side_effect=lambda records, settings, plans=None: (
                "atlas",
                tuple(records),
                settings,
                plans,
            )
        )
        build_document_summary_layer = MagicMock(side_effect=lambda plans=None: ("summary", plans))
        build_cover_highlight_layer = MagicMock(side_effect=lambda plans=None: ("highlights", plans))
        build_page_detail_item_layer = MagicMock(
            side_effect=lambda records, settings=None, plans=None: (
                "details",
                tuple(records),
                settings,
                plans,
            )
        )
        build_profile_sample_layer = MagicMock(
            side_effect=lambda records, settings=None, plans=None: (
                "profile",
                tuple(records),
                settings,
                plans,
            )
        )
        build_toc_layer = MagicMock(
            side_effect=lambda records=None, settings=None, plans=None: (
                "toc",
                tuple(records or []),
                settings,
                plans,
            )
        )
        build_atlas_page_plans = MagicMock(return_value=[{"page": 1}])

        module_overrides = {
            "qfit.activities.infrastructure.geopackage.gpkg_io": self._module(
                "qfit.activities.infrastructure.geopackage.gpkg_io",
                write_layer_to_gpkg=write_layer_to_gpkg,
            ),
            "qfit.activities.infrastructure.geopackage.gpkg_layer_builders": self._module(
                "qfit.activities.infrastructure.geopackage.gpkg_layer_builders",
                build_track_layer=build_track_layer,
                build_start_layer=build_start_layer,
            ),
            "qfit.gpkg_layer_builders": self._module(
                "qfit.gpkg_layer_builders",
                build_track_layer=build_track_layer,
                build_start_layer=build_start_layer,
            ),
            "qfit.activities.infrastructure.geopackage.gpkg_point_layer_builder": self._module(
                "qfit.activities.infrastructure.geopackage.gpkg_point_layer_builder",
                build_point_layer=build_point_layer,
            ),
            "qfit.gpkg_point_layer_builder": self._module(
                "qfit.gpkg_point_layer_builder",
                build_point_layer=build_point_layer,
            ),
            "qfit.activities.infrastructure.geopackage.gpkg_atlas_page_builder": self._module(
                "qfit.activities.infrastructure.geopackage.gpkg_atlas_page_builder",
                build_atlas_layer=build_atlas_layer,
            ),
            "qfit.gpkg_atlas_page_builder": self._module(
                "qfit.gpkg_atlas_page_builder",
                build_atlas_layer=build_atlas_layer,
            ),
            "qfit.activities.infrastructure.geopackage.gpkg_atlas_table_builders": self._module(
                "qfit.activities.infrastructure.geopackage.gpkg_atlas_table_builders",
                build_cover_highlight_layer=build_cover_highlight_layer,
                build_document_summary_layer=build_document_summary_layer,
                build_page_detail_item_layer=build_page_detail_item_layer,
                build_profile_sample_layer=build_profile_sample_layer,
                build_toc_layer=build_toc_layer,
            ),
            "qfit.gpkg_atlas_table_builders": self._module(
                "qfit.gpkg_atlas_table_builders",
                build_cover_highlight_layer=build_cover_highlight_layer,
                build_document_summary_layer=build_document_summary_layer,
                build_page_detail_item_layer=build_page_detail_item_layer,
                build_profile_sample_layer=build_profile_sample_layer,
                build_toc_layer=build_toc_layer,
            ),
            "qfit.atlas.publish_atlas": self._module(
                "qfit.atlas.publish_atlas",
                build_atlas_page_plans=build_atlas_page_plans,
            ),
        }

        with patch.dict(sys.modules, module_overrides):
            sys.modules.pop(
                "qfit.activities.infrastructure.geopackage.gpkg_write_orchestration",
                None,
            )
            sys.modules.pop("qfit.gpkg_write_orchestration", None)

            moved = importlib.import_module(
                "qfit.activities.infrastructure.geopackage.gpkg_write_orchestration"
            )
            legacy = importlib.import_module("qfit.gpkg_write_orchestration")

            self.assertIs(legacy.bootstrap_empty_gpkg, moved.bootstrap_empty_gpkg)
            self.assertIs(
                legacy.build_and_write_all_layers,
                moved.build_and_write_all_layers,
            )

            moved.bootstrap_empty_gpkg("/tmp/bootstrap.gpkg", {"margin_percent": 8})
            self.assertEqual(write_layer_to_gpkg.call_count, 9)
            self.assertEqual(
                write_layer_to_gpkg.mock_calls[0],
                call(("tracks", ()), "/tmp/bootstrap.gpkg", "activity_tracks", overwrite_file=True),
            )
            self.assertEqual(
                write_layer_to_gpkg.mock_calls[-1],
                call(("toc", (), None, None), "/tmp/bootstrap.gpkg", "atlas_toc_entries", overwrite_file=False),
            )

            write_layer_to_gpkg.reset_mock()
            layers = moved.build_and_write_all_layers(
                [{"name": "Evening Run"}],
                "/tmp/full.gpkg",
                {"margin_percent": 10},
                write_activity_points=True,
                point_stride=3,
            )

            build_atlas_page_plans.assert_called_once_with(
                [{"name": "Evening Run"}], settings={"margin_percent": 10}
            )
            self.assertEqual(write_layer_to_gpkg.call_count, 9)
            self.assertEqual(
                layers["activity_points"],
                ("points", ({"name": "Evening Run"},), True, 3),
            )
            self.assertEqual(layers["atlas_toc_entries"], ("toc", ({"name": "Evening Run"},), {"margin_percent": 10}, [{"page": 1}]))


if __name__ == "__main__":
    unittest.main()
