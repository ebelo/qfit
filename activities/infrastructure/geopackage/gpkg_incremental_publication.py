"""Transactional changed-activity publication for activity GeoPackages.

The canonical registry remains the source of truth.  This module rebuilds only
the derived rows owned by a small mutation set, stages them in a temporary
GeoPackage, and merges every affected table in one SQLite transaction.
"""

import gc
import os
import sqlite3
import tempfile
from dataclasses import replace
from types import SimpleNamespace

from .gpkg_atlas_page_builder import build_atlas_layer
from .gpkg_atlas_table_builders import (
    build_cover_highlight_layer,
    build_document_summary_layer,
    build_page_detail_item_layer,
    build_profile_sample_layer,
    build_toc_layer,
)
from .gpkg_io import write_layer_to_gpkg
from .gpkg_layer_builders import build_start_layer, build_track_layer
from .gpkg_point_layer_builder import build_point_layer
from ....atlas.publish_atlas import (
    build_atlas_document_summary_from_plans,
    build_atlas_page_plans,
)


MAX_INCREMENTAL_ACTIVITIES = 100
MAX_INCREMENTAL_FRACTION = 0.25

KEYED_TABLES = (
    "activity_tracks",
    "activity_starts",
    "activity_points",
    "activity_atlas_pages",
    "atlas_profile_samples",
)
PAGE_KEYED_TABLES = (
    "atlas_page_detail_items",
    "atlas_toc_entries",
)
GLOBAL_TABLES = (
    "atlas_document_summary",
    "atlas_cover_highlights",
)


class IncrementalPublicationNotEligible(RuntimeError):
    """Raised when safe incremental publication invariants are not met."""


class IncrementalPublicationCancelled(InterruptedError):
    """Raised before commit when the owning QGIS task is cancelled."""


def publish_incremental_activity_layers(
    records,
    output_path,
    atlas_page_settings,
    sync_result,
    *,
    write_activity_points=True,
    point_stride=5,
    progress=None,
    cancelled=None,
):
    """Stage and transactionally publish rows for ``sync_result.changed_keys``.

    Existing atlas page numbers are retained.  New pages may only append after
    the current maximum sort key; deletions and reorderings deliberately fall
    back to a complete bounded rebuild.
    """

    records = list(records)
    _check_cancelled(cancelled)
    changed_keys = tuple(sync_result.changed_keys)
    _validate_mutation_size(sync_result, changed_keys)
    if sync_result.requires_full_rebuild:
        raise IncrementalPublicationNotEligible("removed activities require a full rebuild")
    if len(records) != len(changed_keys):
        raise IncrementalPublicationNotEligible("not every changed activity could be hydrated")

    _report(progress, "plan", 0, 4)
    existing_pages = _load_existing_atlas_pages(output_path)
    (
        changed_plans,
        affected_sort_keys,
        page_document_summary,
        table_summary,
    ) = _plan_changed_pages(
        records,
        changed_keys,
        existing_pages,
        atlas_page_settings,
    )
    layers = _build_changed_layers(
        records,
        changed_plans,
        table_summary,
        atlas_page_settings,
        write_activity_points=write_activity_points,
        point_stride=point_stride,
    )

    _check_cancelled(cancelled)
    _report(progress, "stage", 1, 4)
    staging_path = _write_staging_gpkg(layers, output_path)
    try:
        _check_cancelled(cancelled)
        _report(progress, "commit", 2, 4)
        _merge_staged_layers(
            output_path,
            staging_path,
            changed_keys,
            affected_sort_keys,
            page_document_summary,
            cancelled=cancelled,
        )
    finally:
        _remove_staging_gpkg(staging_path)

    _report(progress, "complete", 4, 4)
    return {name: layer.featureCount() for name, layer in layers.items()}


def _validate_mutation_size(sync_result, changed_keys):
    changed_count = len(changed_keys)
    if not changed_count:
        raise IncrementalPublicationNotEligible("empty mutation set")
    if changed_count > MAX_INCREMENTAL_ACTIVITIES:
        raise IncrementalPublicationNotEligible("mutation set exceeds incremental ceiling")
    total_count = max(0, int(sync_result.total_count or 0))
    if total_count <= changed_count:
        raise IncrementalPublicationNotEligible("initial publication requires a full rebuild")
    if total_count >= 20 and changed_count / total_count > MAX_INCREMENTAL_FRACTION:
        raise IncrementalPublicationNotEligible("mutation set is too large for incremental publication")


def _load_existing_atlas_pages(output_path):
    required = {
        "source",
        "source_activity_id",
        "page_number",
        "page_sort_key",
        "start_date",
        "page_date",
        "distance_m",
        "moving_time_s",
        "total_elevation_gain_m",
        "activity_type",
    }
    with sqlite3.connect(output_path) as connection:
        columns = {
            row[1]
            for row in connection.execute("PRAGMA table_info(activity_atlas_pages)")
        }
        if not required.issubset(columns):
            raise IncrementalPublicationNotEligible("atlas schema requires migration")
        rows = connection.execute(
            """
            SELECT source, source_activity_id, page_number, page_sort_key,
                   start_date, page_date, distance_m, moving_time_s,
                   total_elevation_gain_m, activity_type
            FROM activity_atlas_pages
            ORDER BY page_number
            """
        ).fetchall()
    return {
        (str(row[0] or ""), str(row[1] or "")): SimpleNamespace(
            source=row[0],
            source_activity_id=row[1],
            page_number=int(row[2]),
            page_sort_key=row[3],
            start_date=row[4],
            page_date=row[5],
            distance_m=row[6],
            moving_time_s=row[7],
            total_elevation_gain_m=row[8],
            activity_type=row[9],
        )
        for row in rows
    }


def _plan_changed_pages(records, changed_keys, existing_pages, atlas_page_settings):
    raw_plans = build_atlas_page_plans(records, settings=atlas_page_settings)
    raw_plan_by_key = {
        (str(plan.source or ""), str(plan.source_activity_id or "")): plan
        for plan in raw_plans
    }
    changed_key_set = set(changed_keys)
    if set(raw_plan_by_key) - changed_key_set:
        raise IncrementalPublicationNotEligible("atlas planner returned an unknown activity")

    unaffected = [
        plan for key, plan in existing_pages.items() if key not in changed_key_set
    ]
    max_page_number = max((plan.page_number for plan in existing_pages.values()), default=0)
    max_sort_key = max((plan.page_sort_key for plan in existing_pages.values()), default=None)
    final_changed, new_plans = _partition_changed_pages(
        changed_keys,
        existing_pages,
        raw_plan_by_key,
        max_sort_key,
    )
    final_changed.extend(_number_appended_pages(new_plans, max_page_number))

    final_changed.sort(key=lambda plan: plan.page_sort_key)
    all_summary_plans = sorted(
        unaffected + final_changed,
        key=lambda plan: (
            plan.start_date or "",
            str(plan.source_activity_id or ""),
        ),
        reverse=True,
    )
    page_document_summary = build_atlas_document_summary_from_plans(
        all_summary_plans
    )
    table_summary = build_atlas_document_summary_from_plans(
        sorted(unaffected + final_changed, key=lambda plan: plan.page_sort_key)
    )
    final_changed = [
        _with_document_summary(plan, page_document_summary)
        for plan in final_changed
    ]
    affected_sort_keys = {
        plan.page_sort_key
        for key, plan in existing_pages.items()
        if key in changed_key_set
    }
    affected_sort_keys.update(plan.page_sort_key for plan in final_changed)
    return (
        final_changed,
        tuple(sorted(affected_sort_keys)),
        page_document_summary,
        table_summary,
    )


def _partition_changed_pages(
    changed_keys,
    existing_pages,
    raw_plan_by_key,
    max_sort_key,
):
    retained = []
    appended = []
    for key in changed_keys:
        previous = existing_pages.get(key)
        current = raw_plan_by_key.get(key)
        if previous is not None:
            if current is None:
                raise IncrementalPublicationNotEligible(
                    "an existing atlas page would disappear"
                )
            if current.page_sort_key != previous.page_sort_key:
                raise IncrementalPublicationNotEligible("an atlas sort key changed")
            retained.append(replace(current, page_number=previous.page_number))
        elif current is not None:
            if max_sort_key is not None and current.page_sort_key <= max_sort_key:
                raise IncrementalPublicationNotEligible(
                    "a new atlas page is not append-only"
                )
            appended.append(current)
    return retained, appended


def _number_appended_pages(plans, max_page_number):
    return [
        replace(plan, page_number=max_page_number + offset)
        for offset, plan in enumerate(
            sorted(plans, key=lambda candidate: candidate.page_sort_key),
            start=1,
        )
    ]


def _with_document_summary(plan, summary):
    return replace(
        plan,
        document_activity_count=summary.activity_count,
        document_date_range_label=summary.date_range_label,
        document_total_distance_label=summary.total_distance_label,
        document_total_duration_label=summary.total_duration_label,
        document_total_elevation_gain_label=summary.total_elevation_gain_label,
        document_activity_types_label=summary.activity_types_label,
        document_cover_summary=summary.cover_summary,
    )


def _build_changed_layers(
    records,
    plans,
    summary,
    atlas_page_settings,
    *,
    write_activity_points,
    point_stride,
):
    return {
        "activity_tracks": build_track_layer(records),
        "activity_starts": build_start_layer(records),
        "activity_points": build_point_layer(
            records,
            write_activity_points,
            point_stride,
        ),
        "activity_atlas_pages": build_atlas_layer(
            records,
            atlas_page_settings,
            plans=plans,
        ),
        "atlas_document_summary": build_document_summary_layer(summary=summary),
        "atlas_cover_highlights": build_cover_highlight_layer(summary=summary),
        "atlas_page_detail_items": build_page_detail_item_layer(
            records,
            atlas_page_settings,
            plans=plans,
        ),
        "atlas_profile_samples": build_profile_sample_layer(
            records,
            atlas_page_settings,
            plans=plans,
        ),
        "atlas_toc_entries": build_toc_layer(
            records,
            atlas_page_settings,
            plans=plans,
        ),
    }


def _write_staging_gpkg(layers, output_path):
    directory = os.path.dirname(os.path.abspath(output_path)) or "."
    descriptor, staging_path = tempfile.mkstemp(
        prefix=".qfit-incremental-",
        suffix=".gpkg",
        dir=directory,
    )
    os.close(descriptor)
    try:
        first = True
        for layer_name, layer in layers.items():
            write_layer_to_gpkg(
                layer,
                staging_path,
                layer_name,
                overwrite_file=first,
            )
            first = False
    except Exception:
        _remove_staging_gpkg(staging_path)
        raise
    return staging_path


def _merge_staged_layers(
    output_path,
    staging_path,
    changed_keys,
    affected_sort_keys,
    summary,
    *,
    cancelled=None,
):
    ogr = _import_ogr()
    target = ogr.Open(str(output_path), update=1)
    staged = ogr.Open(str(staging_path), update=0)
    if target is None or staged is None:
        raise RuntimeError("Failed to open incremental GeoPackage transaction")

    started = target.StartTransaction(1)
    if started != ogr.OGRERR_NONE:
        raise RuntimeError("GeoPackage does not support atomic incremental publication")
    try:
        key_filter = _activity_key_filter(changed_keys)
        for table_name in KEYED_TABLES:
            _check_cancelled(cancelled)
            _replace_filtered_features(
                ogr,
                target,
                staged,
                table_name,
                key_filter,
                cancelled=cancelled,
            )

        sort_filter = _value_filter("page_sort_key", affected_sort_keys)
        for table_name in PAGE_KEYED_TABLES:
            _check_cancelled(cancelled)
            _replace_filtered_features(
                ogr,
                target,
                staged,
                table_name,
                sort_filter,
                cancelled=cancelled,
            )

        for table_name in GLOBAL_TABLES:
            _check_cancelled(cancelled)
            _replace_filtered_features(
                ogr,
                target,
                staged,
                table_name,
                None,
                cancelled=cancelled,
            )

        _update_document_fields(target, summary, cancelled=cancelled)
        if target.CommitTransaction() != ogr.OGRERR_NONE:
            raise RuntimeError("Failed to commit incremental GeoPackage publication")
    except Exception:
        target.RollbackTransaction()
        raise
    finally:
        staged = None
        target = None


def _import_ogr():
    try:
        from osgeo import ogr
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("GDAL Python bindings are required for incremental publication") from exc

    ogr.UseExceptions()
    return ogr


def _replace_filtered_features(
    ogr,
    target,
    staged,
    table_name,
    attribute_filter,
    *,
    cancelled=None,
):
    target_layer = target.GetLayerByName(table_name)
    staged_layer = staged.GetLayerByName(table_name)
    if target_layer is None or staged_layer is None:
        raise IncrementalPublicationNotEligible(
            f"derived table is unavailable: {table_name}"
        )
    _validate_layer_schema(target_layer, staged_layer, table_name)

    target_layer.SetAttributeFilter(attribute_filter)
    feature_ids = [feature.GetFID() for feature in target_layer]
    target_layer.SetAttributeFilter(None)
    for feature_id in feature_ids:
        if target_layer.DeleteFeature(feature_id) != 0:
            raise RuntimeError(f"Failed to delete stale {table_name} feature")

    staged_layer.ResetReading()
    for index, staged_feature in enumerate(staged_layer):
        if index % 250 == 0:
            _check_cancelled(cancelled)
        _copy_feature(ogr, staged_feature, target_layer)
    target_layer.SyncToDisk()


def _validate_layer_schema(target_layer, staged_layer, table_name):
    target_definition = target_layer.GetLayerDefn()
    staged_definition = staged_layer.GetLayerDefn()
    target_fields = {
        target_definition.GetFieldDefn(index).GetName()
        for index in range(target_definition.GetFieldCount())
    }
    staged_fields = {
        staged_definition.GetFieldDefn(index).GetName()
        for index in range(staged_definition.GetFieldCount())
    }
    if target_fields != staged_fields:
        raise IncrementalPublicationNotEligible(
            f"derived table schema mismatch: {table_name}"
        )


def _copy_feature(ogr, source_feature, target_layer):
    target_definition = target_layer.GetLayerDefn()
    source_definition = source_feature.GetDefnRef()
    target_feature = ogr.Feature(target_definition)
    for index in range(source_definition.GetFieldCount()):
        if not source_feature.IsFieldSet(index):
            continue
        field_name = source_definition.GetFieldDefn(index).GetName()
        target_index = target_definition.GetFieldIndex(field_name)
        target_feature.SetField(target_index, source_feature.GetField(index))
    geometry = source_feature.GetGeometryRef()
    if geometry is not None:
        target_feature.SetGeometry(geometry.Clone())
    if target_layer.CreateFeature(target_feature) != 0:
        raise RuntimeError(f"Failed to insert {target_layer.GetName()} feature")


def _update_document_fields(target, summary, *, cancelled=None):
    layer = target.GetLayerByName("activity_atlas_pages")
    values = {
        "document_activity_count": summary.activity_count,
        "document_date_range_label": summary.date_range_label,
        "document_total_distance_label": summary.total_distance_label,
        "document_total_duration_label": summary.total_duration_label,
        "document_total_elevation_gain_label": summary.total_elevation_gain_label,
        "document_activity_types_label": summary.activity_types_label,
        "document_cover_summary": summary.cover_summary,
    }
    layer.ResetReading()
    for index, feature in enumerate(layer):
        if index % 250 == 0:
            _check_cancelled(cancelled)
        for field_name, value in values.items():
            feature.SetField(field_name, value)
        if layer.SetFeature(feature) != 0:
            raise RuntimeError("Failed to update atlas document metadata")
    layer.SyncToDisk()


def _activity_key_filter(keys):
    clauses = []
    for source, source_activity_id in keys:
        clauses.append(
            f'(source = {_sql_literal(source)} AND '
            f'source_activity_id = {_sql_literal(source_activity_id)})'
        )
    return " OR ".join(clauses) or "0 = 1"


def _value_filter(field_name, values):
    if not values:
        return "0 = 1"
    literals = ", ".join(_sql_literal(value) for value in values)
    return f'{field_name} IN ({literals})'


def _sql_literal(value):
    return "'" + str(value).replace("'", "''") + "'"


def _remove_staging_gpkg(staging_path):
    gc.collect()
    for suffix in ("", "-wal", "-shm"):
        try:
            os.remove(staging_path + suffix)
        except FileNotFoundError:
            pass


def _report(progress, phase, completed, total):
    if progress is not None:
        progress(phase, completed, total)


def _check_cancelled(cancelled):
    if cancelled is not None and cancelled():
        raise IncrementalPublicationCancelled("incremental publication cancelled")
