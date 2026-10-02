"""Host-free request/cache contracts for the static heatmap workflow."""
import hashlib
import json
from dataclasses import asdict, dataclass, field

from ..domain.route_density import RouteDensityParameters
from ...activities.domain.activity_query import ActivityQuery, build_subset_string


@dataclass(frozen=True)
class RouteHeatmapRequest:
    source_path: str
    subset: str
    cache_dir: str
    parameters: RouteDensityParameters = field(default_factory=RouteDensityParameters)
    source_revision: tuple = ()


@dataclass(frozen=True)
class RouteHeatmapArtifact:
    path: str
    cache_key: str
    activity_count: int
    crs: str
    maximum: float
    reused: bool = False


def build_route_heatmap_request(source_path, cache_dir, selection_state=None, source_revision=()):
    query = selection_state.query if selection_state is not None else ActivityQuery()
    return RouteHeatmapRequest(str(source_path), build_subset_string(query), str(cache_dir), source_revision=source_revision)


def heatmap_fingerprint(parameters, crs):
    digest = hashlib.sha256()
    digest.update(json.dumps({"parameters": asdict(parameters), "crs": crs}, sort_keys=True).encode())
    return digest


def add_track_fingerprint(digest, identity, geometry):
    for value in (json.dumps(identity).encode(), geometry):
        digest.update(len(value).to_bytes(8, "big"))
        digest.update(value)
