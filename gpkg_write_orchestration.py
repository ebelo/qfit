"""
GeoPackage bootstrap and layer-write sequencing for qfit.

This module owns the two write-orchestration steps that were previously
inlined in :class:`~qfit.gpkg_writer.GeoPackageWriter`:

- :func:`bootstrap_empty_gpkg` — create a fresh GeoPackage with empty layers
  in the canonical order.
- :func:`build_and_write_all_layers` — rebuild every visualization layer from
  activity records and write them to disk, returning the built layers for
  result summarization.

It depends on :mod:`gpkg_io` (disk writes), :mod:`gpkg_layer_builders`
(layer construction), and :mod:`atlas.publish_atlas` (plan computation)
but contains no schema definitions or repository logic.
"""

from .gpkg_io import write_layer_to_gpkg
from .gpkg_layer_builders import (
    build_atlas_layer,
    build_cover_highlight_layer,
    build_document_summary_layer,
    build_page_detail_item_layer,
    build_point_layer,
    build_profile_sample_layer,
    build_start_layer,
    build_toc_layer,
    build_track_layer,
)
from .atlas.publish_atlas import build_atlas_page_plans


def bootstrap_empty_gpkg(output_path, atlas_page_settings):
    """Create a new GeoPackage with empty layers in the canonical order.

    The first layer (``activity_tracks``) overwrites any existing file;
    subsequent layers are appended.
    """
    write_layer_to_gpkg(build_track_layer([]), output_path, "activity_tracks", overwrite_file=True)
    write_layer_to_gpkg(build_start_layer([]), output_path, "activity_starts", overwrite_file=False)
    write_layer_to_gpkg(build_point_layer([]), output_path, "activity_points", overwrite_file=False)
    write_layer_to_gpkg(
        build_atlas_layer([], atlas_page_settings),
        output_path, "activity_atlas_pages", overwrite_file=False,
    )
    write_layer_to_gpkg(build_document_summary_layer(), output_path, "atlas_document_summary", overwrite_file=False)
    write_layer_to_gpkg(build_cover_highlight_layer(), output_path, "atlas_cover_highlights", overwrite_file=False)
    write_layer_to_gpkg(build_page_detail_item_layer([]), output_path, "atlas_page_detail_items", overwrite_file=False)
    write_layer_to_gpkg(build_profile_sample_layer([]), output_path, "atlas_profile_samples", overwrite_file=False)
    write_layer_to_gpkg(build_toc_layer([]), output_path, "atlas_toc_entries", overwrite_file=False)


def build_and_write_all_layers(
    records, output_path, atlas_page_settings,
    write_activity_points=False, point_stride=1,
):
    """Build all visualization layers from *records* and write them to *output_path*.

    Returns an ``OrderedDict``-style dict mapping layer names to the built
    ``QgsVectorLayer`` objects so callers can inspect feature counts without
    re-reading the file.
    """
    plans = build_atlas_page_plans(records, settings=atlas_page_settings)

    layers = {
        "activity_tracks": build_track_layer(records),
        "activity_starts": build_start_layer(records),
        "activity_points": build_point_layer(records, write_activity_points, point_stride),
        "activity_atlas_pages": build_atlas_layer(records, atlas_page_settings, plans=plans),
        "atlas_document_summary": build_document_summary_layer(plans=plans),
        "atlas_cover_highlights": build_cover_highlight_layer(plans=plans),
        "atlas_page_detail_items": build_page_detail_item_layer(records, atlas_page_settings, plans=plans),
        "atlas_profile_samples": build_profile_sample_layer(records, atlas_page_settings, plans=plans),
        "atlas_toc_entries": build_toc_layer(records, atlas_page_settings, plans=plans),
    }

    for layer_name, layer in layers.items():
        write_layer_to_gpkg(layer, output_path, layer_name, overwrite_file=False)

    return layers
