from __future__ import annotations

from dataclasses import dataclass
from math import hypot
from statistics import median


@dataclass(frozen=True)
class StartPointSample:
    """Metric-space sample used for clustering frequent start locations."""

    x: float
    y: float
    source_activity_id: str | None = None


@dataclass(frozen=True)
class FrequentStartCluster:
    """Cluster summary returned by the frequent-start analysis."""

    rank: int
    center_x: float
    center_y: float
    activity_count: int
    marker_size: float


def analyze_frequent_start_points(
    samples: list[StartPointSample], max_clusters: int = 10
) -> tuple[list[FrequentStartCluster], float]:
    """Cluster start points, rank the busiest clusters, and size them for display."""

    if not samples:
        return [], 0.0

    radius_m = _adaptive_radius_m(samples)
    grouped = _cluster_samples(samples, radius_m)
    grouped.sort(
        key=lambda cluster: (
            -len(cluster),
            round(_cluster_center(cluster)[0], 6),
            round(_cluster_center(cluster)[1], 6),
        )
    )
    top_clusters = grouped[: max(1, int(max_clusters or 10))]
    counts = [len(cluster) for cluster in top_clusters]
    max_count = max(counts) if counts else 1
    min_count = min(counts) if counts else 1

    ranked = []
    for rank, cluster in enumerate(top_clusters, start=1):
        center_x, center_y = _cluster_center(cluster)
        ranked.append(
            FrequentStartCluster(
                rank=rank,
                center_x=center_x,
                center_y=center_y,
                activity_count=len(cluster),
                marker_size=_marker_size(len(cluster), min_count, max_count),
            )
        )
    return ranked, radius_m


def _adaptive_radius_m(samples: list[StartPointSample]) -> float:
    if len(samples) < 2:
        return 75.0

    nearest_neighbor_distances = []
    for index, sample in enumerate(samples):
        nearest = min(
            _distance(sample, other)
            for other_index, other in enumerate(samples)
            if other_index != index
        )
        nearest_neighbor_distances.append(nearest)

    median_nearest = median(nearest_neighbor_distances)
    xs = [sample.x for sample in samples]
    ys = [sample.y for sample in samples]
    diagonal = hypot(max(xs) - min(xs), max(ys) - min(ys))
    density_adjustment = min(1.35, 1.0 + (len(samples) / 250.0))

    base_radius = median_nearest * 1.6 if median_nearest > 0 else diagonal * 0.02
    if base_radius <= 0:
        base_radius = 75.0

    return max(40.0, min(250.0, base_radius * density_adjustment))


def _cluster_samples(samples: list[StartPointSample], radius_m: float) -> list[list[StartPointSample]]:
    unassigned = list(samples)
    clusters: list[list[StartPointSample]] = []

    while unassigned:
        clusters.append(_collect_cluster(unassigned, radius_m))

    return clusters


def _collect_cluster(unassigned: list[StartPointSample], radius_m: float) -> list[StartPointSample]:
    seed = unassigned.pop(0)
    cluster = [seed]
    queue = [seed]
    while queue:
        current = queue.pop(0)
        attached = _pop_attached_samples(unassigned, current, radius_m)
        cluster.extend(attached)
        queue.extend(attached)
    return cluster


def _pop_attached_samples(
    unassigned: list[StartPointSample], current: StartPointSample, radius_m: float
) -> list[StartPointSample]:
    attached = [candidate for candidate in unassigned if _distance(current, candidate) <= radius_m]
    for candidate in attached:
        unassigned.remove(candidate)
    return attached


def _cluster_center(cluster: list[StartPointSample]) -> tuple[float, float]:
    return (
        sum(sample.x for sample in cluster) / float(len(cluster)),
        sum(sample.y for sample in cluster) / float(len(cluster)),
    )


def _marker_size(count: int, min_count: int, max_count: int) -> float:
    if max_count <= min_count:
        return 7.0
    ratio = (count - min_count) / float(max_count - min_count)
    return round(5.0 + (ratio * 7.0), 2)


def _distance(a: StartPointSample, b: StartPointSample) -> float:
    return hypot(a.x - b.x, a.y - b.y)
