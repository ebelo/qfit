import logging
import os
from dataclasses import dataclass, field
from datetime import date

from .sync_repository import SyncStats

logger = logging.getLogger(__name__)


@dataclass
class StoreActivitiesRequest:
    """Structured input for qfit's store-activities workflow."""

    activities: list = field(default_factory=list)
    output_path: str = ""
    write_activity_points: bool = False
    point_stride: int = 0
    atlas_margin_percent: float = 0.0
    atlas_min_extent_degrees: float = 0.0
    atlas_target_aspect_ratio: float = 0.0
    sync_metadata: dict | None = None
    last_sync_date: str | None = None


@dataclass
class LoadDatasetRequest:
    """Structured input for loading an existing qfit dataset."""

    output_path: str = ""


# Backward-compatible aliases while issue #175 lands incrementally.
LoadDatabaseRequest = StoreActivitiesRequest
LoadExistingRequest = LoadDatasetRequest


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
    sync: SyncStats | None = None
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

    @staticmethod
    def build_write_request(
        activities,
        output_path,
        write_activity_points,
        point_stride,
        atlas_margin_percent,
        atlas_min_extent_degrees,
        atlas_target_aspect_ratio,
        sync_metadata=None,
        last_sync_date=None,
    ) -> StoreActivitiesRequest:
        return StoreActivitiesRequest(
            activities=list(activities),
            output_path=output_path,
            write_activity_points=write_activity_points,
            point_stride=point_stride,
            atlas_margin_percent=atlas_margin_percent,
            atlas_min_extent_degrees=atlas_min_extent_degrees,
            atlas_target_aspect_ratio=atlas_target_aspect_ratio,
            sync_metadata=sync_metadata,
            last_sync_date=last_sync_date,
        )

    @staticmethod
    def build_load_existing_request(output_path) -> LoadDatasetRequest:
        return LoadDatasetRequest(output_path=output_path)

    def _write_database(self, request: StoreActivitiesRequest) -> LoadResult:
        """Write activities to the GeoPackage without loading layers into QGIS.

        Raises ``LoadWorkflowError`` for validation failures and
        ``RuntimeError | OSError | ValueError`` for write failures.
        """
        if not request.activities:
            raise LoadWorkflowError("Fetch activities from Strava first.")
        if not request.output_path:
            raise LoadWorkflowError("Choose a GeoPackage output path first.")

        from . import gpkg_writer

        writer = gpkg_writer.GeoPackageWriter(
            output_path=request.output_path,
            write_activity_points=request.write_activity_points,
            point_stride=request.point_stride,
            atlas_margin_percent=request.atlas_margin_percent,
            atlas_min_extent_degrees=request.atlas_min_extent_degrees,
            atlas_target_aspect_ratio=request.atlas_target_aspect_ratio,
        )
        write_result = writer.write_activities(request.activities, sync_metadata=request.sync_metadata)
        resolved_path = write_result["path"]

        sync: SyncStats | None = write_result.get("sync") or None
        total_stored = sync.total_count if sync else 0
        _last_sync = request.last_sync_date or date.today().isoformat()

        status = (
            "Synced {fetched} fetched activities into GeoPackage: "
            "inserted {inserted}, updated {updated}, unchanged {unchanged}, "
            "stored total {total}. GeoPackage updated at {path}. "
            "Use Load activity layers in Visualize when you want the stored data in QGIS."
        ).format(
            fetched=write_result.get("fetched_count", len(request.activities)),
            inserted=sync.inserted if sync else 0,
            updated=sync.updated if sync else 0,
            unchanged=sync.unchanged if sync else 0,
            total=total_stored,
            path=resolved_path,
        )

        return LoadResult(
            output_path=resolved_path,
            total_stored=total_stored,
            status=status,
            sync=sync,
            fetched_count=write_result.get("fetched_count", len(request.activities)),
            track_count=write_result.get("track_count", 0),
            start_count=write_result.get("start_count", 0),
            point_count=write_result.get("point_count", 0),
            atlas_count=write_result.get("atlas_count", 0),
        )

    def write_database(self, request: StoreActivitiesRequest | None = None, **legacy_kwargs) -> LoadResult:
        """Write activities to the GeoPackage without loading them into QGIS."""
        if request is None:
            request = self.build_write_request(**legacy_kwargs)
        return self._write_database(request)

    def write_database_request(self, request: StoreActivitiesRequest) -> LoadResult:
        return self._write_database(request)

    def write_and_load(self, request: StoreActivitiesRequest | None = None, **legacy_kwargs) -> LoadResult:
        """Write activities to GeoPackage and load layers into QGIS."""
        if request is None:
            request = self.build_write_request(**legacy_kwargs)
        result = self._write_database(request)

        activities_layer, starts_layer, points_layer, atlas_layer = (
            self.layer_manager.load_output_layers(result.output_path)
        )

        result.activities_layer = activities_layer
        result.starts_layer = starts_layer
        result.points_layer = points_layer
        result.atlas_layer = atlas_layer
        result.status = (
            "Synced {fetched} fetched activities into GeoPackage: inserted {inserted}, "
            "updated {updated}, unchanged {unchanged}, stored total {total}. "
            "Loaded {track_count} tracks, {start_count} starts, {point_count} activity points, "
            "and {atlas_count} atlas pages into QGIS without auto-filtering the layer tables."
        ).format(
            fetched=result.fetched_count,
            inserted=result.sync.inserted if result.sync else 0,
            updated=result.sync.updated if result.sync else 0,
            unchanged=result.sync.unchanged if result.sync else 0,
            total=result.total_stored,
            track_count=result.track_count,
            start_count=result.start_count,
            point_count=result.point_count,
            atlas_count=result.atlas_count,
        )
        return result

    def write_and_load_request(self, request: StoreActivitiesRequest) -> LoadResult:
        return self.write_and_load(request=request)

    def load_existing(self, request: LoadDatasetRequest | str) -> LoadResult:
        """Load layers from an existing GeoPackage without writing.

        Raises ``LoadWorkflowError`` for validation failures and
        ``RuntimeError | OSError`` for load failures.
        """
        if isinstance(request, str):
            request = self.build_load_existing_request(request)

        if not request.output_path:
            raise LoadWorkflowError("Choose a GeoPackage output path first.")
        if not os.path.exists(request.output_path):
            raise LoadWorkflowError(
                "No database found at:\n  {path}\n\n"
                "Store activities first to create it.".format(path=request.output_path)
            )

        activities_layer, starts_layer, points_layer, atlas_layer = (
            self.layer_manager.load_output_layers(request.output_path)
        )

        total = activities_layer.featureCount() if activities_layer else 0

        return LoadResult(
            output_path=request.output_path,
            activities_layer=activities_layer,
            starts_layer=starts_layer,
            points_layer=points_layer,
            atlas_layer=atlas_layer,
            total_stored=total,
            status="Layers loaded from {path}.".format(path=request.output_path),
        )

    def load_existing_request(self, request: LoadDatasetRequest) -> LoadResult:
        return self.load_existing(request)
