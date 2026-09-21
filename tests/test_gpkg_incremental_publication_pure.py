import importlib.util
import os
import sqlite3
import sys
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock, call, patch


@dataclass(frozen=True)
class _Plan:
    source: str = "strava"
    source_activity_id: str = "2"
    page_number: int = 1
    page_sort_key: str = "2026-02|ride|strava|2"
    start_date: str = "2026-02-01T08:00:00Z"
    page_date: str = "2026-02-01"
    distance_m: float = 10.0
    moving_time_s: int = 20
    total_elevation_gain_m: float = 30.0
    activity_type: str = "Ride"
    document_activity_count: int = 1
    document_date_range_label: str | None = None
    document_total_distance_label: str | None = None
    document_total_duration_label: str | None = None
    document_total_elevation_gain_label: str | None = None
    document_activity_types_label: str | None = None
    document_cover_summary: str | None = None


def _summary(plans):
    plans = list(plans)
    return SimpleNamespace(
        activity_count=len(plans),
        date_range_label="dates" if plans else None,
        total_distance_label="distance" if plans else None,
        total_duration_label="duration" if plans else None,
        total_elevation_gain_label="elevation" if plans else None,
        activity_types_label=", ".join(dict.fromkeys(plan.activity_type for plan in plans)) or None,
        cover_summary="cover" if plans else None,
    )


class _Layer:
    def __init__(self, count=1):
        self._count = count

    def featureCount(self):
        return self._count


class _FieldDefinition:
    def __init__(self, name):
        self._name = name

    def GetName(self):
        return self._name


class _LayerDefinition:
    def __init__(self, fields):
        self.fields = tuple(fields)

    def GetFieldCount(self):
        return len(self.fields)

    def GetFieldDefn(self, index):
        return _FieldDefinition(self.fields[index])

    def GetFieldIndex(self, name):
        return self.fields.index(name)


class _Geometry:
    def Clone(self):
        return _Geometry()


class _Feature:
    def __init__(self, definition, fid=-1, values=None, geometry=None):
        self.definition = definition
        self.fid = fid
        self.values = dict(values or {})
        self.geometry = geometry

    def GetFID(self):
        return self.fid

    def GetDefnRef(self):
        return self.definition

    def IsFieldSet(self, index):
        return self.definition.fields[index] in self.values

    def GetField(self, index):
        return self.values.get(self.definition.fields[index])

    def SetField(self, field, value):
        name = self.definition.fields[field] if isinstance(field, int) else field
        self.values[name] = value

    def GetGeometryRef(self):
        return self.geometry

    def SetGeometry(self, geometry):
        self.geometry = geometry


class _OgrLayer:
    def __init__(self, name, fields, features=None):
        self.name = name
        self.definition = _LayerDefinition(fields)
        self.features = list(features or [])
        self.attribute_filter = None
        self.synced = False

    def GetName(self):
        return self.name

    def GetLayerDefn(self):
        return self.definition

    def SetAttributeFilter(self, expression):
        self.attribute_filter = expression

    def __iter__(self):
        return iter(list(self.features))

    def ResetReading(self):
        return None

    def DeleteFeature(self, fid):
        self.features = [feature for feature in self.features if feature.fid != fid]
        return 0

    def CreateFeature(self, feature):
        feature.fid = max((item.fid for item in self.features), default=0) + 1
        self.features.append(feature)
        return 0

    def SetFeature(self, feature):
        return 0

    def SyncToDisk(self):
        self.synced = True


class _DataSource:
    def __init__(self, layers=None, commit_result=0):
        self.layers = {layer.name: layer for layer in (layers or [])}
        self.commit_result = commit_result
        self.started = False
        self.committed = False
        self.rolled_back = False

    def GetLayerByName(self, name):
        return self.layers.get(name)

    def StartTransaction(self, _force):
        self.started = True
        return 0

    def CommitTransaction(self):
        self.committed = True
        return self.commit_result

    def RollbackTransaction(self):
        self.rolled_back = True
        return 0


class IncrementalPublicationPureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.builders = {
            name: MagicMock(return_value=_Layer())
            for name in (
                "build_atlas_layer",
                "build_cover_highlight_layer",
                "build_document_summary_layer",
                "build_page_detail_item_layer",
                "build_profile_sample_layer",
                "build_toc_layer",
                "build_start_layer",
                "build_track_layer",
                "build_point_layer",
            )
        }

        def module(name, **attributes):
            result = ModuleType(name)
            for key, value in attributes.items():
                setattr(result, key, value)
            return result

        stubs = {
            "qfit.activities.infrastructure.geopackage.gpkg_atlas_page_builder": module(
                "qfit.activities.infrastructure.geopackage.gpkg_atlas_page_builder",
                build_atlas_layer=cls.builders["build_atlas_layer"],
            ),
            "qfit.activities.infrastructure.geopackage.gpkg_atlas_table_builders": module(
                "qfit.activities.infrastructure.geopackage.gpkg_atlas_table_builders",
                build_cover_highlight_layer=cls.builders["build_cover_highlight_layer"],
                build_document_summary_layer=cls.builders["build_document_summary_layer"],
                build_page_detail_item_layer=cls.builders["build_page_detail_item_layer"],
                build_profile_sample_layer=cls.builders["build_profile_sample_layer"],
                build_toc_layer=cls.builders["build_toc_layer"],
            ),
            "qfit.activities.infrastructure.geopackage.gpkg_io": module(
                "qfit.activities.infrastructure.geopackage.gpkg_io",
                write_layer_to_gpkg=MagicMock(),
            ),
            "qfit.activities.infrastructure.geopackage.gpkg_layer_builders": module(
                "qfit.activities.infrastructure.geopackage.gpkg_layer_builders",
                build_start_layer=cls.builders["build_start_layer"],
                build_track_layer=cls.builders["build_track_layer"],
            ),
            "qfit.activities.infrastructure.geopackage.gpkg_point_layer_builder": module(
                "qfit.activities.infrastructure.geopackage.gpkg_point_layer_builder",
                build_point_layer=cls.builders["build_point_layer"],
            ),
            "qfit.atlas.publish_atlas": module(
                "qfit.atlas.publish_atlas",
                build_atlas_document_summary_from_plans=MagicMock(side_effect=_summary),
                build_atlas_page_plans=MagicMock(),
            ),
        }
        module_path = (
            Path(__file__).resolve().parents[1]
            / "activities"
            / "infrastructure"
            / "geopackage"
            / "gpkg_incremental_publication.py"
        )
        module_name = (
            "qfit.activities.infrastructure.geopackage."
            "gpkg_incremental_publication_testmod"
        )
        spec = importlib.util.spec_from_file_location(module_name, module_path)
        loaded = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, stubs):
            assert spec.loader is not None
            spec.loader.exec_module(loaded)
        cls.module = loaded

    def setUp(self):
        for builder in self.builders.values():
            builder.reset_mock(return_value=False, side_effect=False)
            builder.return_value = _Layer()
        self.module.build_atlas_page_plans.reset_mock()
        self.module.build_atlas_document_summary_from_plans.reset_mock()
        self.module.build_atlas_document_summary_from_plans.side_effect = _summary

    @staticmethod
    def _stats(**overrides):
        payload = {
            "changed_keys": (("strava", "2"),),
            "removed_keys": (),
            "requires_full_rebuild": False,
            "total_count": 2,
        }
        payload.update(overrides)
        return SimpleNamespace(**payload)

    def _atlas_database(self):
        descriptor, path = tempfile.mkstemp(suffix=".gpkg")
        os.close(descriptor)
        with sqlite3.connect(path) as connection:
            connection.execute(
                """
                CREATE TABLE activity_atlas_pages (
                    source TEXT,
                    source_activity_id TEXT,
                    page_number INTEGER,
                    page_sort_key TEXT,
                    start_date TEXT,
                    page_date TEXT,
                    distance_m REAL,
                    moving_time_s INTEGER,
                    total_elevation_gain_m REAL,
                    activity_type TEXT
                )
                """
            )
            connection.execute(
                "INSERT INTO activity_atlas_pages VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    "strava",
                    "1",
                    1,
                    "2026-01|ride|strava|1",
                    "2026-01-01T08:00:00Z",
                    "2026-01-01",
                    1.0,
                    2,
                    3.0,
                    "Ride",
                ),
            )
        return path

    def test_incremental_publication_plans_stages_merges_and_reports(self):
        path = self._atlas_database()
        changed_plan = _Plan()
        self.module.build_atlas_page_plans.return_value = [changed_plan]
        progress = MagicMock()
        try:
            with patch.object(
                self.module,
                "_write_staging_gpkg",
                return_value=path + ".stage",
            ) as write_stage, patch.object(
                self.module,
                "_merge_staged_layers",
            ) as merge, patch.object(
                self.module,
                "_remove_staging_gpkg",
            ) as remove:
                result = self.module.publish_incremental_activity_layers(
                    [{"source": "strava", "source_activity_id": "2"}],
                    path,
                    "settings",
                    self._stats(),
                    progress=progress,
                )

            self.assertEqual(set(result), set(self.module.KEYED_TABLES + self.module.PAGE_KEYED_TABLES + self.module.GLOBAL_TABLES))
            write_stage.assert_called_once()
            merge.assert_called_once()
            remove.assert_called_once_with(path + ".stage")
            self.assertEqual(progress.call_args_list[0], call("plan", 0, 4))
            self.assertEqual(progress.call_args_list[-1], call("complete", 4, 4))
        finally:
            os.remove(path)

    def test_mutation_size_and_removed_activity_guards(self):
        empty_stats = self._stats(total_count=2)
        with self.assertRaisesRegex(self.module.IncrementalPublicationNotEligible, "empty"):
            self.module._validate_mutation_size(empty_stats, ())
        ceiling_stats = self._stats(total_count=1000)
        ceiling_keys = tuple(("strava", str(index)) for index in range(101))
        with self.assertRaisesRegex(self.module.IncrementalPublicationNotEligible, "ceiling"):
            self.module._validate_mutation_size(
                ceiling_stats,
                ceiling_keys,
            )
        initial_stats = self._stats(total_count=1)
        with self.assertRaisesRegex(self.module.IncrementalPublicationNotEligible, "initial"):
            self.module._validate_mutation_size(initial_stats, (("strava", "1"),))
        large_stats = self._stats(total_count=20)
        large_keys = tuple(("strava", str(index)) for index in range(6))
        with self.assertRaisesRegex(self.module.IncrementalPublicationNotEligible, "too large"):
            self.module._validate_mutation_size(
                large_stats,
                large_keys,
            )

    def test_plan_changed_pages_reuses_pages_and_appends_in_sort_order(self):
        existing = {
            ("strava", "1"): SimpleNamespace(
                source="strava",
                source_activity_id="1",
                page_number=1,
                page_sort_key="2026-01|ride|strava|1",
                start_date="2026-01-01",
                page_date="2026-01-01",
                distance_m=1.0,
                moving_time_s=2,
                total_elevation_gain_m=3.0,
                activity_type="Ride",
            )
        }
        self.module.build_atlas_page_plans.return_value = [
            _Plan(source_activity_id="3", page_sort_key="2026-03|ride|strava|3"),
            _Plan(source_activity_id="2", page_sort_key="2026-02|ride|strava|2"),
        ]

        plans, sort_keys, page_summary, table_summary = self.module._plan_changed_pages(
            [{}, {}],
            (("strava", "3"), ("strava", "2")),
            existing,
            "settings",
        )

        self.assertEqual(
            [(plan.source_activity_id, plan.page_number) for plan in plans],
            [("2", 2), ("3", 3)],
        )
        self.assertEqual(sort_keys, ("2026-02|ride|strava|2", "2026-03|ride|strava|3"))
        self.assertEqual(page_summary.activity_count, 3)
        self.assertEqual(table_summary.activity_count, 3)

    def test_plan_changed_pages_rejects_disappearance_reorder_and_backfill(self):
        previous = SimpleNamespace(
            source="strava",
            source_activity_id="2",
            page_number=2,
            page_sort_key="2026-02|ride|strava|2",
            start_date="2026-02-01",
            page_date="2026-02-01",
            distance_m=1.0,
            moving_time_s=2,
            total_elevation_gain_m=3.0,
            activity_type="Ride",
        )
        existing = {("strava", "2"): previous}
        self.module.build_atlas_page_plans.return_value = []
        with self.assertRaisesRegex(self.module.IncrementalPublicationNotEligible, "disappear"):
            self.module._plan_changed_pages([{}], (("strava", "2"),), existing, None)

        self.module.build_atlas_page_plans.return_value = [
            _Plan(page_sort_key="2026-02|renamed|strava|2")
        ]
        with self.assertRaisesRegex(self.module.IncrementalPublicationNotEligible, "sort key"):
            self.module._plan_changed_pages([{}], (("strava", "2"),), existing, None)

        self.module.build_atlas_page_plans.return_value = [
            _Plan(source_activity_id="1", page_sort_key="2026-01|ride|strava|1")
        ]
        with self.assertRaisesRegex(self.module.IncrementalPublicationNotEligible, "append-only"):
            self.module._plan_changed_pages([{}], (("strava", "1"),), existing, None)

    def test_staging_file_is_written_in_order_and_removed_on_failure(self):
        layers = {"first": _Layer(), "second": _Layer()}
        writer = MagicMock()
        with tempfile.TemporaryDirectory() as temp_dir, patch.object(
            self.module,
            "write_layer_to_gpkg",
            writer,
        ):
            output = str(Path(temp_dir) / "target.gpkg")
            staging = self.module._write_staging_gpkg(layers, output)
            self.assertEqual(
                writer.call_args_list,
                [
                    call(layers["first"], staging, "first", overwrite_file=True),
                    call(layers["second"], staging, "second", overwrite_file=False),
                ],
            )
            self.assertTrue(os.path.exists(staging))
            self.module._remove_staging_gpkg(staging)
            self.assertFalse(os.path.exists(staging))

        with tempfile.TemporaryDirectory() as temp_dir, patch.object(
            self.module,
            "write_layer_to_gpkg",
            side_effect=RuntimeError("stage failed"),
        ):
            with self.assertRaisesRegex(RuntimeError, "stage failed"):
                self.module._write_staging_gpkg(
                    layers,
                    str(Path(temp_dir) / "target.gpkg"),
                )
            self.assertEqual(list(Path(temp_dir).glob(".qfit-incremental-*")), [])

    def test_filters_escape_values_and_cancellation_is_cooperative(self):
        expression = self.module._activity_key_filter((("str'ava", "1"),))
        self.assertIn("str''ava", expression)
        self.assertEqual(self.module._activity_key_filter(()), "0 = 1")
        self.assertEqual(self.module._value_filter("page_sort_key", ()), "0 = 1")
        self.assertIn("IN ('a', 'b')", self.module._value_filter("page_sort_key", ("a", "b")))
        with self.assertRaises(self.module.IncrementalPublicationCancelled):
            self.module._check_cancelled(lambda: True)

    def test_replace_filtered_features_validates_schema_and_copies_geometry(self):
        fields = ("source", "source_activity_id", "name")
        target_layer = _OgrLayer(
            "activity_tracks",
            fields,
            [_Feature(_LayerDefinition(fields), fid=1, values={"source": "old"})],
        )
        staged_layer = _OgrLayer(
            "activity_tracks",
            fields,
            [
                _Feature(
                    _LayerDefinition(fields),
                    fid=9,
                    values={
                        "source": "strava",
                        "source_activity_id": "2",
                        "name": "Ride",
                    },
                    geometry=_Geometry(),
                )
            ],
        )
        target = _DataSource([target_layer])
        staged = _DataSource([staged_layer])
        ogr = SimpleNamespace(Feature=lambda definition: _Feature(definition))

        self.module._replace_filtered_features(
            ogr,
            target,
            staged,
            "activity_tracks",
            "source = 'strava'",
        )

        self.assertEqual(len(target_layer.features), 1)
        self.assertEqual(target_layer.features[0].values["name"], "Ride")
        self.assertIsInstance(target_layer.features[0].geometry, _Geometry)
        self.assertTrue(target_layer.synced)

        staged.layers["activity_tracks"] = _OgrLayer(
            "activity_tracks",
            ("different",),
        )
        with self.assertRaisesRegex(
            self.module.IncrementalPublicationNotEligible,
            "schema mismatch",
        ):
            self.module._replace_filtered_features(
                ogr,
                target,
                staged,
                "activity_tracks",
                None,
            )

    def test_update_document_fields_and_missing_layer_guard(self):
        fields = (
            "document_activity_count",
            "document_date_range_label",
            "document_total_distance_label",
            "document_total_duration_label",
            "document_total_elevation_gain_label",
            "document_activity_types_label",
            "document_cover_summary",
        )
        feature = _Feature(_LayerDefinition(fields), fid=1)
        layer = _OgrLayer("activity_atlas_pages", fields, [feature])
        self.module._update_document_fields(_DataSource([layer]), _summary([_Plan()]))
        self.assertEqual(feature.values["document_activity_count"], 1)
        self.assertEqual(feature.values["document_cover_summary"], "cover")
        self.assertTrue(layer.synced)

        ogr = SimpleNamespace()
        target = _DataSource()
        staged = _DataSource()
        with self.assertRaisesRegex(
            self.module.IncrementalPublicationNotEligible,
            "unavailable",
        ):
            self.module._replace_filtered_features(
                ogr,
                target,
                staged,
                "missing",
                None,
            )

    def test_merge_uses_one_transaction_and_rolls_back_commit_failure(self):
        target = _DataSource()
        staged = _DataSource()
        ogr = SimpleNamespace(
            OGRERR_NONE=0,
            Open=MagicMock(side_effect=[target, staged]),
        )
        summary = _summary([_Plan()])
        with patch.object(self.module, "_import_ogr", return_value=ogr), patch.object(
            self.module,
            "_replace_filtered_features",
        ) as replace_features, patch.object(
            self.module,
            "_update_document_fields",
        ) as update_document:
            self.module._merge_staged_layers(
                "target.gpkg",
                "stage.gpkg",
                (("strava", "2"),),
                ("sort",),
                summary,
            )

        self.assertTrue(target.started)
        self.assertTrue(target.committed)
        self.assertFalse(target.rolled_back)
        self.assertEqual(
            replace_features.call_count,
            len(
                self.module.KEYED_TABLES
                + self.module.PAGE_KEYED_TABLES
                + self.module.GLOBAL_TABLES
            ),
        )
        update_document.assert_called_once_with(
            target,
            summary,
            cancelled=None,
        )

        failing_target = _DataSource(commit_result=1)
        failing_ogr = SimpleNamespace(
            OGRERR_NONE=0,
            Open=MagicMock(side_effect=[failing_target, staged]),
        )
        with patch.object(
            self.module,
            "_import_ogr",
            return_value=failing_ogr,
        ), patch.object(
            self.module,
            "_replace_filtered_features",
        ), patch.object(
            self.module,
            "_update_document_fields",
        ):
            with self.assertRaisesRegex(RuntimeError, "commit"):
                self.module._merge_staged_layers(
                    "target.gpkg",
                    "stage.gpkg",
                    (("strava", "2"),),
                    ("sort",),
                    summary,
                )
        self.assertTrue(failing_target.rolled_back)

    def test_import_ogr_enables_exceptions(self):
        ogr = SimpleNamespace(UseExceptions=MagicMock())
        osgeo = ModuleType("osgeo")
        osgeo.ogr = ogr
        with patch.dict(sys.modules, {"osgeo": osgeo}):
            self.assertIs(self.module._import_ogr(), ogr)
        ogr.UseExceptions.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
