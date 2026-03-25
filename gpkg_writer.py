import os

from qgis.core import (
    QgsCoordinateTransformContext,
    QgsProject,
    QgsVectorFileWriter,
)

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
from .gpkg_schema import GPKG_LAYER_SCHEMA
from .publish_atlas import (
    build_atlas_page_plans,
    normalize_atlas_page_settings,
)
from .sync_repository import SyncRepository


class GeoPackageWriter:
    """Persist qfit sync data to a GeoPackage and rebuild derived visualization layers."""

    def __init__(
        self,
        output_path=None,
        write_activity_points=False,
        point_stride=5,
        atlas_margin_percent=None,
        atlas_min_extent_degrees=None,
        atlas_target_aspect_ratio=None,
    ):
        self.output_path = output_path
        self.write_activity_points = bool(write_activity_points)
        self.point_stride = max(1, int(point_stride or 1))
        self.atlas_page_settings = normalize_atlas_page_settings(
            margin_percent=atlas_margin_percent,
            min_extent_degrees=atlas_min_extent_degrees,
            target_aspect_ratio=atlas_target_aspect_ratio,
        )

    def schema(self):
        return dict(GPKG_LAYER_SCHEMA)

    def write_activities(self, activities, sync_metadata=None):
        if not self.output_path:
            raise ValueError("output_path is required")
        os.makedirs(os.path.dirname(self.output_path) or ".", exist_ok=True)

        repository = SyncRepository(self.output_path)
        new_file = not os.path.exists(self.output_path) or os.path.getsize(self.output_path) == 0
        if new_file:
            self._write_layer(build_track_layer([]), "activity_tracks", overwrite_file=True)
            self._write_layer(build_start_layer([]), "activity_starts", overwrite_file=False)
            self._write_layer(build_point_layer([]), "activity_points", overwrite_file=False)
            self._write_layer(
                build_atlas_layer([], self.atlas_page_settings),
                "activity_atlas_pages", overwrite_file=False,
            )
            self._write_layer(build_document_summary_layer(), "atlas_document_summary", overwrite_file=False)
            self._write_layer(build_cover_highlight_layer(), "atlas_cover_highlights", overwrite_file=False)
            self._write_layer(build_page_detail_item_layer([]), "atlas_page_detail_items", overwrite_file=False)
            self._write_layer(build_profile_sample_layer([]), "atlas_profile_samples", overwrite_file=False)
            self._write_layer(build_toc_layer([]), "atlas_toc_entries", overwrite_file=False)

        repository.ensure_schema()
        sync_result = repository.upsert_activities(activities, sync_metadata=sync_metadata)
        records = repository.load_all_activity_records()

        plans = build_atlas_page_plans(records, settings=self.atlas_page_settings)
        track_layer = build_track_layer(records)
        start_layer = build_start_layer(records)
        point_layer = build_point_layer(records, self.write_activity_points, self.point_stride)
        atlas_layer = build_atlas_layer(records, self.atlas_page_settings, plans=plans)
        document_summary_layer = build_document_summary_layer(plans=plans)
        cover_highlight_layer = build_cover_highlight_layer(plans=plans)
        page_detail_item_layer = build_page_detail_item_layer(records, self.atlas_page_settings, plans=plans)
        profile_sample_layer = build_profile_sample_layer(records, self.atlas_page_settings, plans=plans)
        toc_layer = build_toc_layer(records, self.atlas_page_settings, plans=plans)
        self._write_layer(track_layer, "activity_tracks", overwrite_file=False)
        self._write_layer(start_layer, "activity_starts", overwrite_file=False)
        self._write_layer(point_layer, "activity_points", overwrite_file=False)
        self._write_layer(atlas_layer, "activity_atlas_pages", overwrite_file=False)
        self._write_layer(document_summary_layer, "atlas_document_summary", overwrite_file=False)
        self._write_layer(cover_highlight_layer, "atlas_cover_highlights", overwrite_file=False)
        self._write_layer(page_detail_item_layer, "atlas_page_detail_items", overwrite_file=False)
        self._write_layer(profile_sample_layer, "atlas_profile_samples", overwrite_file=False)
        self._write_layer(toc_layer, "atlas_toc_entries", overwrite_file=False)

        return {
            "schema": self.schema(),
            "path": self.output_path,
            "fetched_count": len(activities),
            "track_count": track_layer.featureCount(),
            "start_count": start_layer.featureCount(),
            "point_count": point_layer.featureCount(),
            "atlas_count": atlas_layer.featureCount(),
            "document_summary_count": document_summary_layer.featureCount(),
            "cover_highlight_count": cover_highlight_layer.featureCount(),
            "page_detail_item_count": page_detail_item_layer.featureCount(),
            "profile_sample_count": profile_sample_layer.featureCount(),
            "toc_count": toc_layer.featureCount(),
            "sync": sync_result,
        }

    def _write_layer(self, layer, layer_name, overwrite_file):
        options = QgsVectorFileWriter.SaveVectorOptions()
        options.driverName = "GPKG"
        options.layerName = layer_name
        options.fileEncoding = "UTF-8"
        options.actionOnExistingFile = (
            QgsVectorFileWriter.CreateOrOverwriteFile
            if overwrite_file
            else QgsVectorFileWriter.CreateOrOverwriteLayer
        )

        result = QgsVectorFileWriter.writeAsVectorFormatV3(
            layer,
            self.output_path,
            QgsProject.instance().transformContext() if QgsProject.instance() else QgsCoordinateTransformContext(),
            options,
        )
        if result[0] != QgsVectorFileWriter.NoError:
            raise RuntimeError(
                "Failed to write layer '{name}' to {path}: {result}".format(
                    name=layer_name,
                    path=self.output_path,
                    result=result,
                )
            )
