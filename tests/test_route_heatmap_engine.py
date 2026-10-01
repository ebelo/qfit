import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
from tests import _path  # noqa: F401
from qfit.analysis.application.route_heatmap import RouteHeatmapRequest
from qfit.analysis.domain.route_density import RouteDensityParameters, HeatmapCancelled
from qfit.analysis.infrastructure.route_heatmap_raster import (
    build_route_heatmap, _cached_artifact, _count_tiles, _smooth_tile, _write_tiles,
)


class _Band:
    def __init__(self, dataset, main=False):
        self.dataset = dataset
        self.main = main
        self.pixels = None

    def SetNoDataValue(self, value):
        self.dataset.nodata = value

    def WriteArray(self, pixels):
        self.pixels = pixels.copy()
        if self.main:
            self.dataset.path.write_bytes(pixels.tobytes())
        return 0

    def GetOverview(self, index):
        return self.dataset.overviews[index]


class _Dataset:
    def __init__(self, path):
        self.path = Path(path)
        self.band = _Band(self, True)
        self.overviews = [_Band(self) for _ in range(4)]

    def GetRasterBand(self, number):
        return self.band

    def SetProjection(self, value):
        self.projection = value

    def SetGeoTransform(self, value):
        self.transform = value

    def BuildOverviews(self, method, factors):
        self.factors = factors
        return 0


class _RasterBackend:
    GDT_Float32 = 6

    def __init__(self):
        self.datasets = []

    def GetDriverByName(self, name):
        return self

    def Create(self, path, *args, **kwargs):
        dataset = _Dataset(path)
        self.datasets.append(dataset)
        return dataset

    def BuildVRT(self, path, paths, **kwargs):
        Path(path).write_text(json.dumps([Path(p).name for p in paths]))
        return SimpleNamespace(FlushCache=lambda: None)


class RouteHeatmapEngineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.parameters = RouteDensityParameters(tile_size=32)
        self.request = RouteHeatmapRequest("unused.gpkg", "", str(self.root / "cache"), self.parameters)
        self.backend = _RasterBackend()
        self.crs = SimpleNamespace(ExportToWkt=lambda: "metric-crs")

    def _counts(self):
        routes = [(('test', '1'), [[(1, 1), (101, 1)], [(101, 1), (1, 1)]]),
                  (('test', '2'), [[(1, 1), (101, 1)]])]
        with patch("qfit.analysis.infrastructure.route_heatmap_raster.projected_parts", return_value=routes):
            return _count_tiles(self.request, self.root, None, None, None, 2, lambda: False, lambda _: None)

    def test_each_activity_counts_once_and_tile_budget_is_bounded(self):
        tiles, maximum = self._counts()
        self.assertEqual(maximum, 2)
        data = np.memmap(tiles[0, 0], dtype="uint32", mode="r", shape=(32, 32))
        self.assertTrue(np.all(data[0, :11] == 2))
        self.assertEqual(int(data.sum()), 22)
        del data
        with patch("qfit.analysis.infrastructure.route_heatmap_raster.MAX_TILES", 0), self.assertRaises(ValueError):
            self._counts()

    def test_gaussian_mass_symmetry_and_missing_tiles(self):
        path = self.root / "impulse.bin"
        data = np.memmap(path, dtype="uint32", mode="w+", shape=(32, 32))
        data[:] = 0
        data[16, 16] = 1
        data.flush()
        del data
        density = _smooth_tile((0, 0), {(0, 0): path}, self.parameters)
        self.assertAlmostEqual(float(density.sum()), 1, places=6)
        self.assertEqual(density[16, 14], density[16, 18])
        self.assertEqual(density[14, 16], density[18, 16])
        self.assertEqual(float(_smooth_tile((10, 10), {}, self.parameters).sum()), 0)
        no_smoothing = RouteDensityParameters(sigma=0, tile_size=32)
        self.assertEqual(float(_smooth_tile((0, 0), {(0, 0): path}, no_smoothing).max()), 1)

    def test_raster_tiles_have_fixed_coordinates_and_peak_preserving_overviews(self):
        tiles, _ = self._counts()
        directory = self.root / "output"
        directory.mkdir()
        with patch.dict("sys.modules", {"osgeo": SimpleNamespace(gdal=self.backend)}):
            maximum, paths = _write_tiles(tiles, self.parameters, directory, self.crs, lambda: False, lambda _: None)
        self.assertGreater(maximum, 0)
        self.assertGreater(len(paths), 0)
        for dataset in self.backend.datasets:
            self.assertEqual(dataset.nodata, 0)
            self.assertEqual(dataset.projection, "metric-crs")
            self.assertEqual(dataset.transform[1:3], (10, 0))
            self.assertEqual(dataset.transform[5], -10)
            self.assertAlmostEqual(float(dataset.band.pixels.max()), float(dataset.overviews[0].pixels.max()))
        with patch("qfit.analysis.infrastructure.route_heatmap_raster.MAX_TILES", 0), self.assertRaises(ValueError):
            _write_tiles(tiles, self.parameters, directory, self.crs, lambda: False, lambda _: None)

    def test_atomic_cache_reuse_repair_and_cancellation(self):
        key = "a" * 64
        def snapshot(request, work, cancelled):
            if cancelled():
                raise HeatmapCancelled()
            return work / "snapshot", key, self.crs, (0, 1, 0, 1), 1
        routes = [(('test', '1'), [[(1, 1), (101, 1)]])]
        with patch.dict("sys.modules", {"osgeo": SimpleNamespace(gdal=self.backend)}), patch(
            "qfit.analysis.infrastructure.route_heatmap_raster.snapshot_tracks", side_effect=snapshot,
        ), patch("qfit.analysis.infrastructure.route_heatmap_raster.projected_crs", return_value=(self.crs, "metric")), patch(
            "qfit.analysis.infrastructure.route_heatmap_raster.projected_parts", return_value=routes,
        ):
            artifact = build_route_heatmap(self.request)
            self.assertFalse(artifact.reused)
            self.assertTrue(build_route_heatmap(self.request).reused)
            directory = Path(artifact.path).parent
            next(directory.glob("*.tif")).write_bytes(b"corrupted")
            self.assertIsNone(_cached_artifact(directory, key))
            self.assertFalse(build_route_heatmap(self.request).reused)
            with self.assertRaises(HeatmapCancelled):
                build_route_heatmap(self.request, lambda: True)
        self.assertFalse(any(p.name.startswith("heatmap-work-") for p in Path(self.request.cache_dir).iterdir()))
        self.assertIsNone(_cached_artifact(self.root / "missing", key))
        manifest = directory / "manifest.json"
        original = json.loads(manifest.read_text())
        original["cache_key"] = "wrong"
        manifest.write_text(json.dumps(original))
        self.assertIsNone(_cached_artifact(directory, key))

    def test_empty_input_and_failed_backend_do_not_publish(self):
        with patch("qfit.analysis.infrastructure.route_heatmap_raster.snapshot_tracks", return_value=(None, "key", None, None, 0)):
            self.assertIsNone(build_route_heatmap(self.request))
        tiles, _ = self._counts()
        with patch.dict("sys.modules", {"osgeo": SimpleNamespace(gdal=self.backend)}), patch.object(self.backend, "Create", return_value=None):
            with self.assertRaises(ValueError):
                _write_tiles(tiles, self.parameters, self.root, self.crs, lambda: False, lambda _: None)

    def test_incomplete_manifests_and_failed_raster_writes_are_rejected(self):
        directory = self.root / "invalid-cache"
        directory.mkdir()
        for files, count, maximum in (({}, 1, 1), ({"heatmap.vrt": "bad", "tile.tif": "bad"}, 0, 1),
                                       ({"heatmap.vrt": "bad", "tile.tif": "bad"}, 1, 0)):
            (directory / "manifest.json").write_text(json.dumps({"cache_key": "key", "files": files,
                                                                "activity_count": count, "maximum": maximum}))
            self.assertIsNone(_cached_artifact(directory, "key"))
        tiles, _ = self._counts()
        for method, message in (("WriteArray", "raster"), ("BuildOverviews", "raster")):
            target = _Band if method == "WriteArray" else _Dataset
            with patch.dict("sys.modules", {"osgeo": SimpleNamespace(gdal=self.backend)}), patch.object(target, method, return_value=1):
                with self.assertRaisesRegex(ValueError, message):
                    _write_tiles(tiles, self.parameters, directory, self.crs, lambda: False, lambda _: None)
        with patch.dict("sys.modules", {"osgeo": SimpleNamespace(gdal=self.backend)}), patch.object(_Band, "GetOverview", return_value=SimpleNamespace(WriteArray=lambda _: 1)):
            with self.assertRaisesRegex(ValueError, "overview"):
                _write_tiles(tiles, self.parameters, directory, self.crs, lambda: False, lambda _: None)

    def test_empty_cells_and_vrt_failure_leave_no_published_artifact(self):
        from contextlib import ExitStack
        with ExitStack() as stack:
            stack.enter_context(patch.dict("sys.modules", {"osgeo": SimpleNamespace(gdal=self.backend)}))
            stack.enter_context(patch("qfit.analysis.infrastructure.route_heatmap_raster.snapshot_tracks",
                                      return_value=(None, "key", self.crs, (0,1,0,1), 1)))
            stack.enter_context(patch("qfit.analysis.infrastructure.route_heatmap_raster.projected_crs",
                                      return_value=(self.crs, "metric")))
            stack.enter_context(patch("qfit.analysis.infrastructure.route_heatmap_raster.projected_parts", return_value=[]))
            self.assertIsNone(build_route_heatmap(self.request))
            with patch("qfit.analysis.infrastructure.route_heatmap_raster.projected_parts",
                       return_value=[(('test','1'), [[(1,1),(20,20)]])]), patch.object(self.backend, "BuildVRT", return_value=None):
                with self.assertRaisesRegex(ValueError, "mosaic"):
                    build_route_heatmap(self.request)
            self.assertEqual(list(Path(self.request.cache_dir).iterdir()), [])
