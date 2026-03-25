import logging
import os
from dataclasses import dataclass, field
from datetime import date

logger = logging.getLogger(__name__)


@dataclass
class LoadResult:
    """Structured result from a load workflow operation."""

    output_path: str = ""
    activities_layer: object = None
    starts_layer: object = None
    points_layer: object = None
    atlas_layer: object = None
    total_stored: int = 0
    status: str = ""
    sync: dict = field(default_factory=dict)
    fetched_count: int = 0
    track_count: int = 0
    start_count: int = 0
    point_count: int = 0
    atlas_count: int = 0


class LoadWorkflowError(Exception):
    """Raised when a load workflow step fails validation."""


class LoadWorkflowService:
    """Orchestrates GeoPackage write and layer-load workflows independent of UI."""

    def __init__(self, layer_manager):
        self.layer_manager = layer_manager

    def write_and_load(
        self,
        activities,
        output_path,
        write_activity_points,
        point_stride,
        atlas_margin_percent,
        atlas_min_extent_degrees,
        atlas_target_aspect_ratio,
        sync_metadata=None,
        last_sync_date=None,
    ) -> LoadResult:
        """Write activities to GeoPackage and load layers into QGIS.

        Raises ``LoadWorkflowError`` for validation failures and
        ``RuntimeError | OSError | ValueError`` for write/load failures.
        """
        if not activities:
            raise LoadWorkflowError("Fetch activities from Strava first.")
        if not output_path:
            raise LoadWorkflowError("Choose a GeoPackage output path first.")

        from . import gpkg_writer

        writer = gpkg_writer.GeoPackageWriter(
            output_path=output_path,
            write_activity_points=write_activity_points,
            point_stride=point_stride,
            atlas_margin_percent=atlas_margin_percent,
            atlas_min_extent_degrees=atlas_min_extent_degrees,
            atlas_target_aspect_ratio=atlas_target_aspect_ratio,
        )
        write_result = writer.write_activities(activities, sync_metadata=sync_metadata)
        resolved_path = write_result["path"]

        activities_layer, starts_layer, points_layer, atlas_layer = (
            self.layer_manager.load_output_layers(resolved_path)
        )

        sync = write_result.get("sync") or {}
        total_stored = sync.get("total_count", 0)
        last_sync = last_sync_date or date.today().isoformat()

        status = (
            "Synced {fetched} fetched activities into GeoPackage: "
            "inserted {inserted}, updated {updated}, unchanged {unchanged}, "
            "stored total {total}. "
            "Loaded {track_count} tracks, {start_count} starts, "
            "{point_count} activity points, and {atlas_count} atlas pages "
            "into QGIS without auto-filtering the layer tables."
        ).format(
            fetched=write_result.get("fetched_count", len(activities)),
            inserted=sync.get("inserted", 0),
            updated=sync.get("updated", 0),
            unchanged=sync.get("unchanged", 0),
            total=total_stored,
            track_count=write_result.get("track_count", 0),
            start_count=write_result.get("start_count", 0),
            point_count=write_result.get("point_count", 0),
            atlas_count=write_result.get("atlas_count", 0),
        )

        return LoadResult(
            output_path=resolved_path,
            activities_layer=activities_layer,
            starts_layer=starts_layer,
            points_layer=points_layer,
            atlas_layer=atlas_layer,
            total_stored=total_stored,
            status=status,
            sync=sync,
            fetched_count=write_result.get("fetched_count", len(activities)),
            track_count=write_result.get("track_count", 0),
            start_count=write_result.get("start_count", 0),
            point_count=write_result.get("point_count", 0),
            atlas_count=write_result.get("atlas_count", 0),
        )

    def load_existing(self, output_path) -> LoadResult:
        """Load layers from an existing GeoPackage without writing.

        Raises ``LoadWorkflowError`` for validation failures and
        ``RuntimeError | OSError`` for load failures.
        """
        if not output_path:
            raise LoadWorkflowError("Choose a GeoPackage output path first.")
        if not os.path.exists(output_path):
            raise LoadWorkflowError(
                "No database found at:\n  {path}\n\n"
                "Fetch & Store activities first to create it.".format(path=output_path)
            )

        activities_layer, starts_layer, points_layer, atlas_layer = (
            self.layer_manager.load_output_layers(output_path)
        )

        total = activities_layer.featureCount() if activities_layer else 0

        return LoadResult(
            output_path=output_path,
            activities_layer=activities_layer,
            starts_layer=starts_layer,
            points_layer=points_layer,
            atlas_layer=atlas_layer,
            total_stored=total,
            status="Layers loaded from {path}.".format(path=output_path),
        )
