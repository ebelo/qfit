"""Bounded tiled route density, atomic cache publication and one raster artifact."""
import hashlib
import json
import math
import shutil
import tempfile
from dataclasses import asdict
from pathlib import Path

from ..application.route_heatmap import RouteHeatmapArtifact
from ..domain.route_density import activity_cells, check_cancelled, tile_cell
from .route_heatmap_source import projected_crs, projected_parts, snapshot_tracks

MAX_TILES = 4096


def build_route_heatmap(request, cancelled=lambda: False, progress=lambda value: None):
    cache = Path(request.cache_dir)
    cache.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="heatmap-work-", dir=cache) as scratch:
        work = Path(scratch)
        snapshot, key, source_crs, bounds, count = snapshot_tracks(request, work, cancelled)
        if not count:
            return None
        cached = _cached_artifact(cache / key, key)
        if cached is not None:
            check_cancelled(cancelled)
            return cached
        target_crs, authid = projected_crs(bounds)
        tiles, visits = _count_tiles(request, work, snapshot, source_crs, target_crs, count, cancelled, progress)
        artifact_dir = work / "result"
        artifact_dir.mkdir()
        maximum, paths = _write_tiles(tiles, request.parameters, artifact_dir, target_crs, cancelled, progress)
        if not paths:
            return None
        from osgeo import gdal
        vrt = gdal.BuildVRT(str(artifact_dir / "heatmap.vrt"), [str(p) for p in paths], srcNodata=0, VRTNodata=0)
        if vrt is None:
            raise ValueError("Could not build the heatmap mosaic")
        vrt.FlushCache()
        vrt = None
        files = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in artifact_dir.iterdir()}
        manifest = {"cache_key": key, "activity_count": count, "crs": authid,
                    "maximum": maximum, "parameters": asdict(request.parameters), "files": files,
                    "tile_count": len(paths), "maximum_visits": visits}
        (artifact_dir / "manifest.json").write_text(json.dumps(manifest, sort_keys=True))
        check_cancelled(cancelled)
        destination = cache / key
        if destination.exists():
            concurrent = _cached_artifact(destination, key)
            if concurrent is not None:
                return concurrent
            shutil.rmtree(destination)
        try:
            artifact_dir.rename(destination)
        except OSError:
            # Another worker may have published this same immutable selection.
            concurrent = _cached_artifact(destination, key)
            if concurrent is None:
                raise
            return concurrent
        progress(100)
        return RouteHeatmapArtifact(str(destination / "heatmap.vrt"), key, count, authid, maximum)


def _cached_artifact(directory, key):
    try:
        manifest = json.loads((directory / "manifest.json").read_text())
        if manifest["cache_key"] != key:
            return None
        files = manifest["files"]
        if not isinstance(files, dict) or "heatmap.vrt" not in files or not any(name.endswith(".tif") for name in files):
            return None
        if manifest["activity_count"] <= 0 or not math.isfinite(manifest["maximum"]) or manifest["maximum"] <= 0:
            return None
        for filename, digest in files.items():
            if Path(filename).name != filename or hashlib.sha256((directory / filename).read_bytes()).hexdigest() != digest:
                return None
        return RouteHeatmapArtifact(str(directory / "heatmap.vrt"), key, manifest["activity_count"],
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


def _smooth_tile(tile, tiles, parameters):
    import numpy as np

    size = parameters.tile_size
    halo = math.ceil(3 * parameters.sigma / parameters.cell_size)
    canvas = np.zeros((size * 3, size * 3), dtype="float32")
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            path = tiles.get((tile[0] + dx, tile[1] + dy))
            if path is not None:
                data = np.memmap(path, dtype="uint32", mode="r", shape=(size, size))
                canvas[(dy + 1) * size:(dy + 2) * size, (dx + 1) * size:(dx + 2) * size] = data
                del data
    canvas = canvas[size - halo:2 * size + halo, size - halo:2 * size + halo]
    if halo:
        distances = np.arange(-halo, halo + 1)
        kernel = np.exp(-0.5 * (distances / (parameters.sigma / parameters.cell_size)) ** 2)
        kernel /= kernel.sum()
        canvas = np.apply_along_axis(lambda row: np.convolve(row, kernel, mode="valid"), 1, canvas)
        canvas = np.apply_along_axis(lambda col: np.convolve(col, kernel, mode="valid"), 0, canvas)
    return canvas.astype("float32")


def _write_tiles(tiles, parameters, directory, crs, cancelled, progress):
    import numpy as np
    from osgeo import gdal

    candidates = sorted({(x + dx, y + dy) for x, y in tiles for dx in (-1, 0, 1) for dy in (-1, 0, 1)})
    if len(candidates) > MAX_TILES:
        raise ValueError("Smoothed heatmap exceeds the tile budget; narrow the activity filters")
    paths = []
    maximum = 0.0
    for index, tile in enumerate(candidates):
        check_cancelled(cancelled)
        density = _smooth_tile(tile, tiles, parameters)
        if not np.any(density):
            continue
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
        for overview_index, factor in enumerate((2, 4, 8, 16)):
            side = parameters.tile_size // factor
            pooled = pixels.reshape(side, factor, side, factor).max(axis=(1, 3))
            if band.GetOverview(overview_index).WriteArray(pooled) != 0:
                raise ValueError("Could not write the heatmap overview")
        band = None
        dataset = None
        paths.append(path)
        progress(60 + 35 * (index + 1) / len(candidates))
    return maximum, paths
