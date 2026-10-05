"""Bounded tiled route density, atomic cache publication and one raster artifact."""
import hashlib
import json
import math
import os
import re
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from uuid import uuid4

from ..application.route_heatmap import RouteHeatmapArtifact
from ..domain.route_density import activity_cells, check_cancelled, tile_cell
from .route_heatmap_cache_lock import publication_lock
from .route_heatmap_source import projected_crs, projected_parts, snapshot_tracks

MAX_TILES = 4096
HEATMAP_VRT_NAME = "heatmap.vrt"
MANIFEST_NAME = "manifest.json"
CURRENT_GENERATION = "current.json"


@dataclass
class _DensityStatistics:
    count: int = 0
    minimum: float = math.inf
    maximum: float = 0.0
    total: float = 0.0
    squares: float = 0.0

    def add(self, density):
        # Zero is nodata. Accumulate while each bounded tile is already in RAM,
        # rather than sampling the potentially world-sized sparse VRT in QGIS.
        values = density[density > 0].astype("float64")
        if not values.size:
            return
        self.count += values.size
        self.minimum = min(self.minimum, float(values.min()))
        self.maximum = max(self.maximum, float(values.max()))
        self.total += float(values.sum())
        self.squares += float((values * values).sum())

    def write(self, band):
        mean = self.total / self.count
        deviation = math.sqrt(max(0.0, self.squares / self.count - mean * mean))
        band.SetStatistics(self.minimum, self.maximum, mean, deviation)


def build_route_heatmap(request, cancelled=lambda: False, progress=lambda value: None):
    cache = Path(request.cache_dir)
    cache.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="heatmap-work-", dir=cache) as scratch:
        work = Path(scratch)
        snapshot, key, source_crs, bounds, count = snapshot_tracks(request, work, cancelled)
        if not count:
            return None
        cached = _cached_artifact(cache / key, key, cancelled)
        if cached is not None:
            check_cancelled(cancelled)
            return cached
        target_crs, authid = projected_crs(bounds)
        tiles, visits = _count_tiles(request, work, snapshot, source_crs, target_crs, count, cancelled, progress)
        artifact_dir = work / "result"
        artifact_dir.mkdir()
        statistics = _DensityStatistics()
        maximum, paths = _write_tiles(tiles, request.parameters, artifact_dir, target_crs, cancelled, progress, statistics)
        if not paths:
            return None
        from osgeo import gdal
        vrt = gdal.BuildVRT(str(artifact_dir / HEATMAP_VRT_NAME), [str(p) for p in paths], srcNodata=0, VRTNodata=0)
        if vrt is None:
            raise ValueError("Could not build the heatmap mosaic")
        statistics.write(vrt.GetRasterBand(1))
        vrt.FlushCache()
        vrt = None
        files = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in artifact_dir.iterdir()}
        manifest = {"cache_key": key, "activity_count": count, "crs": authid,
                    "maximum": maximum, "parameters": asdict(request.parameters), "files": files,
                    "tile_count": len(paths), "maximum_visits": visits}
        manifest_bytes = json.dumps(manifest, sort_keys=True).encode()
        (artifact_dir / MANIFEST_NAME).write_bytes(manifest_bytes)
        (artifact_dir / "manifest.sha256").write_text(hashlib.sha256(manifest_bytes).hexdigest())
        check_cancelled(cancelled)
        destination = cache / key
        concurrent = _publish_artifact(artifact_dir, destination, key, cancelled)
        if concurrent is not None:
            return concurrent
        progress(100)
        return RouteHeatmapArtifact(str(destination / HEATMAP_VRT_NAME), key, count, authid, maximum)


def _publish_artifact(artifact_dir, destination, key, cancelled):
    with publication_lock(destination.parent / (key + ".lock"), cancelled):
        # Recheck under the cross-process lock, including repairs. A second
        # worker must never remove a replacement already published by the first.
        concurrent = _cached_artifact(destination, key, cancelled)
        if concurrent is not None:
            return concurrent
        if not destination.exists():
            artifact_dir.rename(destination)
            return None
        # Never remove published files: QGIS providers, renderer clones or saved
        # projects may retain readers even after the dock switches analysis.
        generation = "generation-" + uuid4().hex
        replacement = destination / generation
        artifact_dir.rename(replacement)
        pointer = destination / ("current-" + uuid4().hex + ".tmp")
        try:
            pointer.write_text(json.dumps({"generation": generation}))
            os.replace(pointer, destination / CURRENT_GENERATION)
        except OSError:
            # No reader can discover this generation until its pointer is
            # published. Return it to scratch so caller cleanup cannot leak
            # a full unreachable raster generation after publication failure.
            replacement.rename(artifact_dir)
            raise
        finally:
            pointer.unlink(missing_ok=True)
        manifest = json.loads((replacement / MANIFEST_NAME).read_text())
        return RouteHeatmapArtifact(str(replacement / HEATMAP_VRT_NAME), key,
                                    manifest["activity_count"], manifest["crs"], manifest["maximum"])


def _current_directory(directory):
    pointer = directory / CURRENT_GENERATION
    if not pointer.exists():
        return directory
    generation = json.loads(pointer.read_text())["generation"]
    if not isinstance(generation, str) or re.fullmatch(r"generation-[0-9a-f]{32}", generation) is None:
        raise ValueError("Invalid heatmap cache generation")
    return directory / generation


def _cached_artifact(directory, key, cancelled=lambda: False):
    try:
        check_cancelled(cancelled)
        directory = _current_directory(directory)
        manifest_bytes = (directory / MANIFEST_NAME).read_bytes()
        if hashlib.sha256(manifest_bytes).hexdigest() != (directory / "manifest.sha256").read_text():
            return None
        manifest = json.loads(manifest_bytes)
        if manifest["cache_key"] != key:
            return None
        files = manifest["files"]
        if not isinstance(files, dict) or HEATMAP_VRT_NAME not in files or not any(name.endswith(".tif") for name in files):
            return None
        if manifest["activity_count"] <= 0 or not math.isfinite(manifest["maximum"]) or manifest["maximum"] <= 0:
            return None
        for filename, digest in files.items():
            check_cancelled(cancelled)
            if Path(filename).name != filename or hashlib.sha256((directory / filename).read_bytes()).hexdigest() != digest:
                return None
        return RouteHeatmapArtifact(str(directory / HEATMAP_VRT_NAME), key, manifest["activity_count"],
                                    manifest["crs"], manifest["maximum"], True)
    except (OSError, ValueError, KeyError, TypeError):
        return None


def _count_tiles(request, work, snapshot, source_crs, target_crs, count, cancelled, progress):
    import numpy as np

    size = request.parameters.tile_size
    tile_paths = {}
    maximum = 0
    for index, (_, parts) in enumerate(projected_parts(snapshot, source_crs, target_crs, cancelled), 1):
        grouped = {}
        for cell in activity_cells(parts, request.parameters, cancelled):
            tile, local = tile_cell(cell, size)
            grouped.setdefault(tile, []).append(local)
        for tile, cells in grouped.items():
            check_cancelled(cancelled)
            if tile not in tile_paths:
                if len(tile_paths) >= MAX_TILES:
                    raise ValueError("Heatmap selection exceeds the tile budget; narrow the activity filters")
                path = work / f"counts-{tile[0]}-{tile[1]}.bin"
                tile_paths[tile] = path
                data = np.memmap(path, dtype="uint32", mode="w+", shape=(size, size))
                data[:] = 0
            else:
                data = np.memmap(tile_paths[tile], dtype="uint32", mode="r+", shape=(size, size))
            rows, cols = zip(*cells)
            data[rows, cols] += 1
            maximum = max(maximum, int(data.max()))
            data.flush()
            del data
        progress(10 + 50 * index / count)
    return tile_paths, maximum


def _halo_slices(offset, size, halo):
    """Neighbour source and compact canvas destination intervals on one axis."""
    if offset < 0:
        return slice(size - halo, size), slice(0, halo)
    if offset > 0:
        return slice(0, halo), slice(size + halo, size + 2 * halo)
    return slice(0, size), slice(halo, size + halo)


def _density_candidates(tiles, parameters, cancelled):
    """Only expand neighbours reached by occupied edge/corner cells."""
    import numpy as np

    size = parameters.tile_size
    halo = math.ceil(3 * parameters.sigma / parameters.cell_size)
    offsets = (-1, 0, 1) if halo else (0,)
    candidates = set()
    for (x, y), path in tiles.items():
        check_cancelled(cancelled)
        data = np.memmap(path, dtype="uint32", mode="r", shape=(size, size))
        for dx in offsets:
            cols, _ = _halo_slices(-dx, size, halo)
            for dy in offsets:
                rows, _ = _halo_slices(-dy, size, halo)
                if np.any(data[rows, cols]):
                    candidates.add((x + dx, y + dy))
        del data
    return sorted(candidates)


def _smooth_tile(tile, tiles, parameters):
    import numpy as np

    size = parameters.tile_size
    halo = math.ceil(3 * parameters.sigma / parameters.cell_size)
    canvas = np.zeros((size + 2 * halo, size + 2 * halo), dtype="float32")
    offsets = (-1, 0, 1) if halo else (0,)
    for dx in offsets:
        source_cols, target_cols = _halo_slices(dx, size, halo)
        for dy in offsets:
            path = tiles.get((tile[0] + dx, tile[1] + dy))
            if path is not None:
                data = np.memmap(path, dtype="uint32", mode="r", shape=(size, size))
                source_rows, target_rows = _halo_slices(dy, size, halo)
                canvas[target_rows, target_cols] = data[source_rows, source_cols]
                del data
    if halo:
        distances = np.arange(-halo, halo + 1)
        kernel = np.exp(-0.5 * (distances / (parameters.sigma / parameters.cell_size)) ** 2)
        kernel /= kernel.sum()
        canvas = np.apply_along_axis(lambda row: np.convolve(row, kernel, mode="valid"), 1, canvas)
        canvas = np.apply_along_axis(lambda col: np.convolve(col, kernel, mode="valid"), 0, canvas)
    return canvas.astype("float32")


def _write_tiles(tiles, parameters, directory, crs, cancelled, progress, statistics=None):
    import numpy as np
    from osgeo import gdal

    candidates = _density_candidates(tiles, parameters, cancelled)
    paths = []
    maximum = 0.0
    for index, tile in enumerate(candidates):
        check_cancelled(cancelled)
        density = _smooth_tile(tile, tiles, parameters)
        if not np.any(density):
            continue
        if len(paths) >= MAX_TILES:
            raise ValueError(f"Heatmap exceeds the budget of {MAX_TILES:,} non-empty density tiles; narrow the activity filters")
        if statistics is not None:
            statistics.add(density)
        maximum = max(maximum, float(density.max()))
        path = directory / f"tile-{tile[0]}-{tile[1]}.tif"
        dataset = gdal.GetDriverByName("GTiff").Create(str(path), parameters.tile_size, parameters.tile_size, 1,
                    gdal.GDT_Float32, options=["TILED=YES", "COMPRESS=DEFLATE", "PREDICTOR=3"])
        if dataset is None:
            raise ValueError("Could not create a heatmap tile")
        unit = parameters.cell_size
        dataset.SetGeoTransform((tile[0] * parameters.tile_size * unit, unit, 0,
                                 (tile[1] + 1) * parameters.tile_size * unit, 0, -unit))
        dataset.SetProjection(crs.ExportToWkt())
        band = dataset.GetRasterBand(1)
        band.SetNoDataValue(0)
        pixels = np.flipud(density)
        if band.WriteArray(pixels) != 0 or dataset.BuildOverviews("NEAREST", [2, 4, 8, 16]) != 0:
            raise ValueError("Could not write the heatmap raster")
        # GDAL BuildOverviews does not support MAX on all supported runtimes.
        # Populate allocated overview bands explicitly, preserving narrow routes.
        _write_peak_overviews(band, pixels, parameters.tile_size)
        band = None
        dataset = None
        paths.append(path)
        progress(60 + 35 * (index + 1) / len(candidates))
    return maximum, paths


def _write_peak_overviews(band, pixels, tile_size):
    for overview_index, factor in enumerate((2, 4, 8, 16)):
        side = tile_size // factor
        pooled = pixels.reshape(side, factor, side, factor).max(axis=(1, 3))
        if band.GetOverview(overview_index).WriteArray(pooled) != 0:
            raise ValueError("Could not write the heatmap overview")
