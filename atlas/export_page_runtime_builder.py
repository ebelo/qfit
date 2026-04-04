from __future__ import annotations

import logging

from .export_page_runner import (
    AtlasPageExportRuntime,
    AtlasPageExportRunner,
    AtlasPerPageFieldIndexes,
    AtlasPerPageLayoutItems,
)
from .profile_item import build_profile_item_adapter

logger = logging.getLogger(__name__)


class AtlasPageRuntimeBuilder:
    """Build the runtime/dependencies required for per-page atlas export."""

    def __init__(
        self,
        *,
        atlas_layer,
        output_path: str,
        detail_item_fields: list[tuple[str, str]],
        profile_picture_id: str,
        profile_summary_id: str,
        detail_block_id: str,
        profile_sample_lookup,
        build_page_profile_payload,
        apply_page_profile_payload,
        normalize_extent,
        target_aspect_ratio: float,
        is_canceled,
    ):
        self.atlas_layer = atlas_layer
        self.output_path = output_path
        self.detail_item_fields = detail_item_fields
        self.profile_picture_id = profile_picture_id
        self.profile_summary_id = profile_summary_id
        self.detail_block_id = detail_block_id
        self.profile_sample_lookup = profile_sample_lookup
        self.build_page_profile_payload = build_page_profile_payload
        self.apply_page_profile_payload = apply_page_profile_payload
        self.normalize_extent = normalize_extent
        self.target_aspect_ratio = target_aspect_ratio
        self.is_canceled = is_canceled

    def build_runner(self, *, layout, exporter, settings) -> AtlasPageExportRunner:
        fields = self.atlas_layer.fields()
        map_item = self.find_map_item(layout)
        profile_adapter, profile_summary_label, detail_block_label = self.find_per_page_layout_items(layout)
        filterable_layers = self.collect_filterable_layers(map_item)

        runtime = AtlasPageExportRuntime(
            atlas=layout.atlas(),
            exporter=exporter,
            settings=settings,
            output_path=self.output_path,
            field_indexes=AtlasPerPageFieldIndexes(
                cx_idx=fields.indexOf("center_x_3857"),
                cy_idx=fields.indexOf("center_y_3857"),
                ew_idx=fields.indexOf("extent_width_m"),
                eh_idx=fields.indexOf("extent_height_m"),
                sid_atlas_idx=fields.indexOf("source_activity_id"),
                profile_summary_idx=fields.indexOf("page_profile_summary"),
                detail_field_indices=[
                    (fields.indexOf(field_name), human_label)
                    for field_name, human_label in self.detail_item_fields
                    if fields.indexOf(field_name) >= 0
                ],
            ),
            layout_items=AtlasPerPageLayoutItems(
                map_item=map_item,
                profile_adapter=profile_adapter,
                profile_summary_label=profile_summary_label,
                detail_block_label=detail_block_label,
            ),
            filterable_layers=filterable_layers,
            profile_sample_lookup=self.profile_sample_lookup,
            build_page_profile_payload=self.build_page_profile_payload,
            apply_page_profile_payload=self.apply_page_profile_payload,
            normalize_extent=self.normalize_extent,
            target_aspect_ratio=self.target_aspect_ratio,
            is_canceled=self.is_canceled,
        )
        return AtlasPageExportRunner(runtime)

    @staticmethod
    def find_map_item(layout):
        for item in layout.items():
            if callable(getattr(item, "setExtent", None)) and callable(getattr(item, "layers", None)):
                return item
        return None

    def find_per_page_layout_items(self, layout):
        profile_pic = None
        profile_summary_label = None
        detail_block_label = None
        for item in layout.items():
            item_id = getattr(item, "id", lambda: None)()
            if item_id == self.profile_picture_id:
                profile_pic = item
            elif item_id == self.profile_summary_id:
                profile_summary_label = item
            elif item_id == self.detail_block_id:
                detail_block_label = item

        profile_adapter = build_profile_item_adapter(profile_pic) if profile_pic is not None else None
        return profile_adapter, profile_summary_label, detail_block_label

    @staticmethod
    def collect_filterable_layers(map_item) -> list[tuple]:
        filterable_layers: list[tuple] = []
        if map_item is None:
            return filterable_layers

        for layer in map_item.layers():
            try:
                layer_fields = layer.fields()
                sid_idx = layer_fields.indexOf("source_activity_id")
                if sid_idx >= 0:
                    filterable_layers.append((layer, layer.subsetString()))
            except (RuntimeError, AttributeError):
                logger.debug("Skipping non-filterable layer", exc_info=True)
        return filterable_layers
