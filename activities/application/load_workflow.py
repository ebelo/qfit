import logging
import os
from dataclasses import dataclass, field
from typing import Callable

from ...atlas.publish_atlas import (
    DEFAULT_ATLAS_MARGIN_PERCENT,
    DEFAULT_ATLAS_TARGET_ASPECT_RATIO,
    DEFAULT_MIN_EXTENT_DEGREES,
)
from ...sync_repository import SyncStats
from ...visualization.application.layer_gateway import LayerGateway

logger = logging.getLogger(__name__)


@dataclass
class StoreActivitiesRequest:
    """Structured input for qfit's store-activities workflow."""

    activities: list = field(default_factory=list)
    output_path: str = ""
    write_activity_points: bool = True
    point_stride: int = 5
    atlas_margin_percent: float = DEFAULT_ATLAS_MARGIN_PERCENT
    atlas_min_extent_degrees: float = DEFAULT_MIN_EXTENT_DEGREES
    atlas_target_aspect_ratio: float = DEFAULT_ATLAS_TARGET_ASPECT_RATIO
    sync_metadata: dict | None = None
    last_sync_date: str | None = None


@dataclass
class LoadDatasetRequest:
    """Structured input for loading an existing qfit dataset."""

    output_path: str = ""


@dataclass
class ClearDatabaseRequest:
    """Structured input for clearing a qfit GeoPackage and loaded layers."""

    output_path: str = ""
    layers: list = field(default_factory=list)


# Backward-compatible aliases while issue #175 lands incrementally.
LoadDatabaseRequest = StoreActivitiesRequest
LoadExistingRequest = LoadDatasetRequest


@dataclass
class StoreActivitiesResult:
    """Focused result from persisting activities into the GeoPackage."""

    output_path: str = ""
    total_stored: int = 0
    status: str = ""
    sync: SyncStats | None = None
    fetched_count: int = 0
    track_count: int = 0
    start_count: int = 0
    point_count: int = 0
    atlas_count: int = 0


@dataclass
class LoadDatasetResult:
    """Focused result from loading stored qfit layers into QGIS."""

    output_path: str = ""
    activities_layer: object = None
    starts_layer: object = None
    points_layer: object = None
    atlas_layer: object = None
    route_tracks_layer: object = None
    route_points_layer: object = None
    route_profile_samples_layer: object = None
    total_stored: int = 0
    status: str = ""


@dataclass
class LoadResult:
    """Structured legacy result from a load workflow operation."""

    output_path: str = ""
    activities_layer: object = None
    starts_layer: object = None
    points_layer: object = None
    atlas_layer: object = None
    route_tracks_layer: object = None
    route_points_layer: object = None
    route_profile_samples_layer: object = None
    total_stored: int = 0
    status: str = ""
    sync: SyncStats | None = None
    fetched_count: int = 0
    track_count: int = 0
    start_count: int = 0
    point_count: int = 0
    atlas_count: int = 0


@dataclass
class ClearDatabaseResult:
    """Structured result from clearing a qfit GeoPackage and loaded layers."""

    output_path: str = ""
    deleted: bool = False
    status: str = ""


class LoadWorkflowError(Exception):
    """Raised when a load workflow step fails validation."""


GeoPackageWriterFactory = Callable[..., object]


def _default_geopackage_writer_factory(**kwargs):
    from ..infrastructure.geopackage.gpkg_writer import GeoPackageWriter

    return GeoPackageWriter(**kwargs)


def _build_store_database_status(result: StoreActivitiesResult) -> str:
    return (
        "Synced {fetched} fetched activities into GeoPackage: "
        "inserted {inserted}, updated {updated}, unchanged {unchanged}, "
        "stored total {total}. GeoPackage updated at {path}. "
        "Use Load activity layers in Visualize when you want the stored data in QGIS."
    ).format(
        fetched=result.fetched_count,
        inserted=result.sync.inserted if result.sync else 0,
        updated=result.sync.updated if result.sync else 0,
        unchanged=result.sync.unchanged if result.sync else 0,
        total=result.total_stored,
        path=result.output_path,
    )


def _build_write_and_load_status(result: StoreActivitiesResult) -> str:
    return (
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


class StoreActivitiesWorkflow:
    """Write fetched activities into qfit's GeoPackage dataset."""

    def __init__(self, writer_factory: GeoPackageWriterFactory | None = None):
        self._writer_factory = writer_factory

    @staticmethod
    def build_write_request(
        activities,
        output_path,
        write_activity_points=True,
        point_stride=5,
        atlas_margin_percent=DEFAULT_ATLAS_MARGIN_PERCENT,
        atlas_min_extent_degrees=DEFAULT_MIN_EXTENT_DEGREES,
        atlas_target_aspect_ratio=DEFAULT_ATLAS_TARGET_ASPECT_RATIO,
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

    def _build_writer(self, request: StoreActivitiesRequest):
        writer_factory = self._writer_factory or _default_geopackage_writer_factory
        return writer_factory(
            output_path=request.output_path,
            # Preserve the current workflow contract while issue #175 is still
            # migrating call sites incrementally.
            write_activity_points=True,
            point_stride=request.point_stride,
            atlas_margin_percent=request.atlas_margin_percent,
            atlas_min_extent_degrees=request.atlas_min_extent_degrees,
            atlas_target_aspect_ratio=request.atlas_target_aspect_ratio,
        )

    @staticmethod
    def _validate_request(request: StoreActivitiesRequest) -> None:
        if not request.activities:
            raise LoadWorkflowError("Fetch activities from Strava first.")
        if not request.output_path:
            raise LoadWorkflowError("Choose a GeoPackage output path first.")

    def _write_database(self, request: StoreActivitiesRequest) -> StoreActivitiesResult:
        """Write activities to the GeoPackage without loading layers into QGIS.

        Raises ``LoadWorkflowError`` for validation failures and
        ``RuntimeError | OSError | ValueError`` for write failures.
        """
        self._validate_request(request)

        writer = self._build_writer(request)
        write_result = writer.write_activities(request.activities, sync_metadata=request.sync_metadata)
        sync: SyncStats | None = write_result.get("sync") or None
        result = StoreActivitiesResult(
            output_path=write_result["path"],
            total_stored=sync.total_count if sync else 0,
            sync=sync,
            fetched_count=write_result.get("fetched_count", len(request.activities)),
            track_count=write_result.get("track_count", 0),
            start_count=write_result.get("start_count", 0),
            point_count=write_result.get("point_count", 0),
            atlas_count=write_result.get("atlas_count", 0),
        )
        result.status = _build_store_database_status(result)
        return result

    def write_database(
        self,
        request: StoreActivitiesRequest | None = None,
        **legacy_kwargs,
    ) -> StoreActivitiesResult:
        if request is None:
            request = self.build_write_request(**legacy_kwargs)
        return self._write_database(request)

    def write_database_request(self, request: StoreActivitiesRequest) -> StoreActivitiesResult:
        return self._write_database(request)


class LoadDatasetWorkflow:
    """Load an existing qfit GeoPackage dataset into QGIS layers."""

    def __init__(
        self,
        layer_gateway: LayerGateway,
        path_exists: Callable[[str], bool] | None = None,
    ):
        self.layer_gateway = layer_gateway
        self._path_exists = path_exists

    @staticmethod
    def build_load_existing_request(output_path) -> LoadDatasetRequest:
        return LoadDatasetRequest(output_path=output_path)

    def _exists(self, output_path: str) -> bool:
        if self._path_exists is not None:
            return self._path_exists(output_path)
        return os.path.exists(output_path)

    def load_existing(self, request: LoadDatasetRequest | str) -> LoadDatasetResult:
        """Load layers from an existing GeoPackage without writing.

        Raises ``LoadWorkflowError`` for validation failures and
        ``RuntimeError | OSError`` for load failures.
        """
        if isinstance(request, str):
            request = self.build_load_existing_request(request)

        if not request.output_path:
            raise LoadWorkflowError("Choose a GeoPackage output path first.")
        if not self._exists(request.output_path):
            raise LoadWorkflowError(
                "No database found at:\n  {path}\n\n"
                "Store activities first to create it.".format(path=request.output_path)
            )

        activities_layer, starts_layer, points_layer, atlas_layer = (
            self.layer_gateway.load_output_layers(request.output_path)
        )
        route_tracks_layer, route_points_layer, route_profile_samples_layer = (
            self.layer_gateway.load_route_layers(request.output_path)
        )
        total = activities_layer.featureCount() if activities_layer else 0

        return LoadDatasetResult(
            output_path=request.output_path,
            activities_layer=activities_layer,
            starts_layer=starts_layer,
            points_layer=points_layer,
            atlas_layer=atlas_layer,
            route_tracks_layer=route_tracks_layer,
            route_points_layer=route_points_layer,
            route_profile_samples_layer=route_profile_samples_layer,
            total_stored=total,
            status="Layers loaded from {path}.".format(path=request.output_path),
        )

    def load_existing_request(self, request: LoadDatasetRequest) -> LoadDatasetResult:
        return self.load_existing(request)


class ClearDatabaseWorkflow:
    """Clear loaded qfit layers and delete the GeoPackage when present."""

    def __init__(
        self,
        layer_gateway: LayerGateway,
        path_exists: Callable[[str], bool] | None = None,
        remove_file: Callable[[str], None] | None = None,
    ):
        self.layer_gateway = layer_gateway
        self._path_exists = path_exists
        self._remove_file = remove_file

    @staticmethod
    def build_clear_database_request(output_path, layers=None) -> ClearDatabaseRequest:
        return ClearDatabaseRequest(
            output_path=output_path,
            layers=list(layers or []),
        )

    def _exists(self, output_path: str) -> bool:
        if self._path_exists is not None:
            return self._path_exists(output_path)
        return os.path.exists(output_path)

    def _delete_file(self, output_path: str) -> None:
        if self._remove_file is not None:
            self._remove_file(output_path)
            return
        os.remove(output_path)

    def clear_database(
        self,
        request: ClearDatabaseRequest | None = None,
        **legacy_kwargs,
    ) -> ClearDatabaseResult:
        """Remove qfit layers from QGIS and delete the GeoPackage when present."""
        if request is None:
            request = self.build_clear_database_request(**legacy_kwargs)

        if not request.output_path:
            raise LoadWorkflowError("Set a GeoPackage output path first.")

        self.layer_gateway.remove_layers(request.layers)

        deleted = False
        if self._exists(request.output_path):
            self._delete_file(request.output_path)
            deleted = True

        if deleted:
            status = (
                f"Database cleared: {request.output_path} deleted. "
                "Fetch and store activities to start fresh."
            )
        else:
            status = "Layers cleared. No file to delete at the specified path."

        return ClearDatabaseResult(
            output_path=request.output_path,
            deleted=deleted,
            status=status,
        )

    def clear_database_request(self, request: ClearDatabaseRequest) -> ClearDatabaseResult:
        return self.clear_database(request=request)


class LoadWorkflowService:
    """Backward-compatible facade over narrower dataset workflows."""

    def __init__(
        self,
        layer_gateway: LayerGateway,
        store_workflow: StoreActivitiesWorkflow | None = None,
        dataset_load_workflow: LoadDatasetWorkflow | None = None,
        clear_database_workflow: ClearDatabaseWorkflow | None = None,
    ):
        self.layer_gateway = layer_gateway
        self.store_workflow = store_workflow or StoreActivitiesWorkflow()
        self.dataset_load_workflow = dataset_load_workflow or LoadDatasetWorkflow(layer_gateway)
        self.clear_database_workflow = clear_database_workflow or ClearDatabaseWorkflow(layer_gateway)

    @staticmethod
    def build_write_request(*args, **kwargs) -> StoreActivitiesRequest:
        return StoreActivitiesWorkflow.build_write_request(*args, **kwargs)

    @staticmethod
    def build_load_existing_request(output_path) -> LoadDatasetRequest:
        return LoadDatasetWorkflow.build_load_existing_request(output_path)

    @staticmethod
    def build_clear_database_request(output_path, layers=None) -> ClearDatabaseRequest:
        return ClearDatabaseWorkflow.build_clear_database_request(output_path, layers=layers)

    @staticmethod
    def _build_legacy_store_result(result: StoreActivitiesResult) -> LoadResult:
        return LoadResult(
            output_path=result.output_path,
            total_stored=result.total_stored,
            status=result.status,
            sync=result.sync,
            fetched_count=result.fetched_count,
            track_count=result.track_count,
            start_count=result.start_count,
            point_count=result.point_count,
            atlas_count=result.atlas_count,
        )

    @staticmethod
    def _build_legacy_load_result(result: LoadDatasetResult) -> LoadResult:
        return LoadResult(
            output_path=result.output_path,
            activities_layer=result.activities_layer,
            starts_layer=result.starts_layer,
            points_layer=result.points_layer,
            atlas_layer=result.atlas_layer,
            route_tracks_layer=result.route_tracks_layer,
            route_points_layer=result.route_points_layer,
            route_profile_samples_layer=result.route_profile_samples_layer,
            total_stored=result.total_stored,
            status=result.status,
        )

    @staticmethod
    def _build_legacy_write_and_load_result(
        store_result: StoreActivitiesResult,
        load_result: LoadDatasetResult,
    ) -> LoadResult:
        return LoadResult(
            output_path=store_result.output_path,
            activities_layer=load_result.activities_layer,
            starts_layer=load_result.starts_layer,
            points_layer=load_result.points_layer,
            atlas_layer=load_result.atlas_layer,
            total_stored=store_result.total_stored,
            status=_build_write_and_load_status(store_result),
            sync=store_result.sync,
            fetched_count=store_result.fetched_count,
            track_count=store_result.track_count,
            start_count=store_result.start_count,
            point_count=store_result.point_count,
            atlas_count=store_result.atlas_count,
        )

    def write_database(
        self,
        request: StoreActivitiesRequest | None = None,
        **legacy_kwargs,
    ) -> LoadResult:
        result = self.store_workflow.write_database(request=request, **legacy_kwargs)
        return self._build_legacy_store_result(result)

    def write_database_request(self, request: StoreActivitiesRequest) -> LoadResult:
        result = self.store_workflow.write_database_request(request)
        return self._build_legacy_store_result(result)

    def write_and_load(
        self,
        request: StoreActivitiesRequest | None = None,
        **legacy_kwargs,
    ) -> LoadResult:
        if request is None:
            request = self.build_write_request(**legacy_kwargs)

        store_result = self.store_workflow.write_database_request(request)
        activities_layer, starts_layer, points_layer, atlas_layer = (
            self.layer_gateway.load_output_layers(store_result.output_path)
        )
        load_result = LoadDatasetResult(
            output_path=store_result.output_path,
            activities_layer=activities_layer,
            starts_layer=starts_layer,
            points_layer=points_layer,
            atlas_layer=atlas_layer,
            total_stored=store_result.total_stored,
            status="Layers loaded from {path}.".format(path=store_result.output_path),
        )
        return self._build_legacy_write_and_load_result(store_result, load_result)

    def write_and_load_request(self, request: StoreActivitiesRequest) -> LoadResult:
        return self.write_and_load(request=request)

    def load_existing(self, request: LoadDatasetRequest | str) -> LoadResult:
        result = self.dataset_load_workflow.load_existing(request)
        return self._build_legacy_load_result(result)

    def load_existing_request(self, request: LoadDatasetRequest) -> LoadResult:
        result = self.dataset_load_workflow.load_existing_request(request)
        return self._build_legacy_load_result(result)

    def clear_database(
        self,
        request: ClearDatabaseRequest | None = None,
        **legacy_kwargs,
    ) -> ClearDatabaseResult:
        return self.clear_database_workflow.clear_database(request=request, **legacy_kwargs)

    def clear_database_request(self, request: ClearDatabaseRequest) -> ClearDatabaseResult:
        return self.clear_database_workflow.clear_database_request(request)
