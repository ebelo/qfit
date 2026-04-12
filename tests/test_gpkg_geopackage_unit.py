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

    def test_gpkg_writer_defaults_to_writing_activity_points(self):
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

            moved = importlib.import_module(
                "qfit.activities.infrastructure.geopackage.gpkg_writer"
            )

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
                "atlas_cover_highlight_count": layer,
                "atlas_page_detail_items": layer,
                "atlas_profile_samples": layer,
                "atlas_toc_entries": layer,
                "atlas_cover_highlights": layer,
            }

            writer = moved.GeoPackageWriter(
                output_path="/tmp/qfit-unit.gpkg",
                activity_store_factory=lambda _path: activity_store,
            )

            with patch("os.path.exists", return_value=False), patch("os.path.getsize", return_value=0):
                writer.write_activities(
                    [{"name": "Morning Ride"}],
                    sync_metadata={"provider": "strava"},
                )

            build_and_write_all_layers.assert_called_once_with(
                [{"name": "Morning Ride"}],
                "/tmp/qfit-unit.gpkg",
                {"margin_percent": 12},
                write_activity_points=True,
                point_stride=5,
            )

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
            self.assertIs(legacy.ensure_attribute_indexes, moved.ensure_attribute_indexes)
            self.assertIs(legacy.ensure_spatial_indexes, moved.ensure_spatial_indexes)

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
            executed_sql = []

            class _Cursor:
                def execute(self, statement):
                    executed_sql.append(statement)

            class _Connection:
                def cursor(self):
                    return _Cursor()

                def commit(self):
                    executed_sql.append("COMMIT")

                def __enter__(self):
                    return self

                def __exit__(self, exc_type, exc, tb):
                    return False

            spatial_index_calls = []

            class _FeatureSource:
                SpatialIndexNotPresent = 1
                SpatialIndexPresent = 2

            class _VectorDataProvider:
                CreateSpatialIndex = 1

            class _Provider:
                def __init__(self, layer_name):
                    self.layer_name = layer_name

                def capabilities(self):
                    return _VectorDataProvider.CreateSpatialIndex

                def hasSpatialIndex(self):
                    return _FeatureSource.SpatialIndexPresent

                def createSpatialIndex(self):
                    spatial_index_calls.append(self.layer_name)
                    return True

            class _Layer:
                def __init__(self, uri, layer_name, provider_key):
                    self.uri = uri
                    self.layer_name = layer_name
                    self.provider_key = provider_key

                def isValid(self):
                    return True

                def dataProvider(self):
                    return _Provider(self.layer_name)

            with patch.object(moved.sqlite3, "connect", return_value=_Connection()) as sqlite_connect, \
                    patch.object(
                        moved,
                        "_import_qgis_spatial_index_api",
                        return_value=(_FeatureSource, _VectorDataProvider, lambda uri, layer_name, provider_key: _Layer(uri, layer_name, provider_key)),
                    ):
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
                self.assertEqual(sqlite_connect.call_args, call("/tmp/full.gpkg"))
                self.assertIn(
                    "CREATE INDEX IF NOT EXISTS idx_activity_tracks_source_activity_id ON activity_tracks(source, source_activity_id)",
                    executed_sql,
                )
                self.assertIn(
                    "CREATE INDEX IF NOT EXISTS idx_activity_points_point_timestamp_local ON activity_points(point_timestamp_local)",
                    executed_sql,
                )
                self.assertIn(
                    "CREATE INDEX IF NOT EXISTS idx_activity_atlas_pages_page_sort_key ON activity_atlas_pages(page_sort_key)",
                    executed_sql,
                )
                self.assertEqual(executed_sql[-1], "COMMIT")
                self.assertEqual(spatial_index_calls, [])

            present = _FeatureSource.SpatialIndexPresent
            missing = _FeatureSource.SpatialIndexNotPresent
            loaded_layers = []

            class _SpatialProvider:
                def __init__(self, state):
                    self.state = state
                    self.create_calls = 0

                def capabilities(self):
                    return _VectorDataProvider.CreateSpatialIndex

                def hasSpatialIndex(self):
                    return self.state

                def createSpatialIndex(self):
                    self.create_calls += 1
                    self.state = present
                    return True

            providers = {
                "activity_tracks": _SpatialProvider(missing),
                "activity_starts": _SpatialProvider(present),
                "activity_points": _SpatialProvider(missing),
                "activity_atlas_pages": _SpatialProvider(present),
            }

            class _SpatialLayer:
                def __init__(self, uri, layer_name, provider_key):
                    loaded_layers.append((uri, layer_name, provider_key))
                    self.layer_name = layer_name

                def isValid(self):
                    return True

                def dataProvider(self):
                    return providers[self.layer_name]

            with patch.object(
                moved,
                "_import_qgis_spatial_index_api",
                return_value=(_FeatureSource, _VectorDataProvider, lambda uri, layer_name, provider_key: _SpatialLayer(uri, layer_name, provider_key)),
            ):
                moved.ensure_spatial_indexes("/tmp/full.gpkg")

            self.assertEqual(
                loaded_layers,
                [
                    ("/tmp/full.gpkg|layername=activity_tracks", "activity_tracks", "ogr"),
                    ("/tmp/full.gpkg|layername=activity_starts", "activity_starts", "ogr"),
                    ("/tmp/full.gpkg|layername=activity_points", "activity_points", "ogr"),
                    ("/tmp/full.gpkg|layername=activity_atlas_pages", "activity_atlas_pages", "ogr"),
                ],
            )
            self.assertEqual(providers["activity_tracks"].create_calls, 1)
            self.assertEqual(providers["activity_starts"].create_calls, 0)
            self.assertEqual(providers["activity_points"].create_calls, 1)
            self.assertEqual(providers["activity_atlas_pages"].create_calls, 0)

            class _InvalidLayer:
                def isValid(self):
                    return False

            with patch.object(
                moved,
                "_import_qgis_spatial_index_api",
                return_value=(_FeatureSource, _VectorDataProvider, lambda uri, layer_name, provider_key: _InvalidLayer()),
            ):
                with self.assertRaisesRegex(RuntimeError, "Failed to load GeoPackage layer 'activity_tracks'"):
                    moved.ensure_spatial_indexes("/tmp/full.gpkg")

            class _NoCapabilityProvider:
                def capabilities(self):
                    return 0

                def hasSpatialIndex(self):
                    return missing

            class _NoCapabilityLayer:
                def isValid(self):
                    return True

                def dataProvider(self):
                    return _NoCapabilityProvider()

            with patch.object(
                moved,
                "_import_qgis_spatial_index_api",
                return_value=(_FeatureSource, _VectorDataProvider, lambda uri, layer_name, provider_key: _NoCapabilityLayer()),
            ):
                with self.assertRaisesRegex(RuntimeError, "does not support spatial index creation"):
                    moved.ensure_spatial_indexes("/tmp/full.gpkg")

            class _CreateFailureProvider:
                def capabilities(self):
                    return _VectorDataProvider.CreateSpatialIndex

                def hasSpatialIndex(self):
                    return missing

                def createSpatialIndex(self):
                    return False

            class _CreateFailureLayer:
                def isValid(self):
                    return True

                def dataProvider(self):
                    return _CreateFailureProvider()

            with patch.object(
                moved,
                "_import_qgis_spatial_index_api",
                return_value=(_FeatureSource, _VectorDataProvider, lambda uri, layer_name, provider_key: _CreateFailureLayer()),
            ):
                with self.assertRaisesRegex(RuntimeError, "Failed to create spatial index for layer 'activity_tracks'"):
                    moved.ensure_spatial_indexes("/tmp/full.gpkg")


if __name__ == "__main__":
    unittest.main()
