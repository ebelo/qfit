"""Real storage/raster/rendering invariants in both required QGIS lanes."""
import hashlib
import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

from tests import _path  # noqa: F401
from tests.route_heatmap_fixture import write_route_heatmap_fixture, sparse_heatmap_routes

REQUIRE_QGIS = os.environ.get("QFIT_REQUIRE_QGIS") == "1"
if REQUIRE_QGIS:
    import numpy as np
    from osgeo import gdal
    from qgis.core import QgsApplication, QgsProject, QgsMapSettings, QgsMapRendererSequentialJob, QgsRectangle
    from qgis.PyQt.QtCore import QSize
    from qgis.PyQt.QtGui import QColor
    from tests.qgis_app import get_shared_qgis_app
    from qfit.analysis.infrastructure.route_heatmap_layer import create_route_heatmap_layer
    from qfit.analysis.infrastructure.route_heatmap_raster import build_route_heatmap, _smooth_tile
    from qfit.analysis.application.route_heatmap import RouteHeatmapRequest
    from qfit.analysis.domain.route_density import HeatmapCancelled, RouteDensityParameters


@unittest.skipUnless(REQUIRE_QGIS, "Real QGIS heatmap integration lane")
class RouteHeatmapQgisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = get_shared_qgis_app(QgsApplication)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = write_route_heatmap_fixture(self.root / "routes.gpkg")
        self.request = RouteHeatmapRequest(self.source, "", str(self.root / "cache"))

    def test_cache_reuse_selection_geometry_and_missing_tile_invalidation(self):
        artifact = build_route_heatmap(self.request)
        self.assertEqual(artifact.activity_count, 3)
        self.assertFalse(artifact.reused)
        directory = Path(artifact.path).parent
        original = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in directory.iterdir()}
        reused = build_route_heatmap(self.request)
        self.assertTrue(reused.reused)
        self.assertEqual(artifact.cache_key, reused.cache_key)
        self.assertEqual(original, {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in directory.iterdir()})
        selected = build_route_heatmap(RouteHeatmapRequest(self.source, "source_activity_id = '0'", self.request.cache_dir))
        self.assertEqual(selected.activity_count, 1)
        self.assertNotEqual(artifact.cache_key, selected.cache_key)
        from osgeo import ogr
        source = ogr.Open(self.source, 1)
        source.ExecuteSQL("UPDATE activity_tracks SET name = 'Renamed'")
        source = None
        self.assertTrue(build_route_heatmap(self.request).reused)
        tile = next(directory.glob("*.tif"))
        tile.unlink()
        repaired = build_route_heatmap(self.request)
        self.assertFalse(repaired.reused)
        self.assertFalse(tile.exists())  # Old generations are never rewritten.
        self.assertTrue((Path(repaired.path).parent / tile.name).exists())
        self.assertTrue(build_route_heatmap(self.request).reused)
        from osgeo import ogr
        source = ogr.Open(self.source, 1)
        layer = source.GetLayerByName("activity_tracks")
        feature = layer.GetNextFeature()
        geometry = feature.GetGeometryRef().Clone()
        geometry.SetPoint_2D(0, 7.339, 46.231)
        feature.SetGeometry(geometry)
        layer.SetFeature(feature)
        feature = None
        layer = None
        source = None
        self.assertNotEqual(artifact.cache_key, build_route_heatmap(self.request).cache_key)

    def test_loading_and_closing_layer_preserves_cache_and_reuses_result(self):
        artifact = build_route_heatmap(self.request)
        directory = Path(artifact.path).parent
        original = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in directory.iterdir()}
        layer = create_route_heatmap_layer(artifact)
        self.assertTrue(layer.isValid())
        layer = None  # GDAL flushes derived statistics on provider close.
        self.assertEqual(original, {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in directory.iterdir()})
        self.assertTrue(build_route_heatmap(self.request).reused)

    def test_repair_preserves_open_raster_and_publishes_new_generation(self):
        artifact = build_route_heatmap(self.request)
        directory = Path(artifact.path).parent
        layer = create_route_heatmap_layer(artifact)
        tile = next(directory.glob("*.tif"))
        reader = gdal.Open(str(tile))
        original_pixels = reader.ReadAsArray()
        original_vrt = Path(artifact.path).read_bytes()
        (directory / "manifest.sha256").write_text("invalid checksum")
        repaired = build_route_heatmap(self.request)
        self.assertFalse(repaired.reused)
        self.assertNotEqual(repaired.path, artifact.path)
        self.assertTrue(np.array_equal(original_pixels, reader.ReadAsArray()))
        self.assertEqual(original_vrt, Path(artifact.path).read_bytes())
        self.assertTrue(layer.isValid())
        self.assertEqual(build_route_heatmap(self.request).path, repaired.path)
        self.assertTrue(build_route_heatmap(self.request).reused)
        # Statistics describe non-nodata density, not a sampled sparse extent.
        arrays = [gdal.Open(str(p)).ReadAsArray() for p in Path(repaired.path).parent.glob("*.tif")]
        values = np.concatenate([a[a > 0].astype("float64") for a in arrays])
        dataset = gdal.Open(repaired.path)
        stats = dataset.GetRasterBand(1).GetStatistics(False, False)
        self.assertTrue(np.allclose(stats, [values.min(), values.max(), values.mean(), values.std()]))
        dataset = None
        reader = None
        layer = None
        self.assertTrue(build_route_heatmap(self.request).reused)

    def test_multiple_activity_types_select_stored_routes_with_or(self):
        from osgeo import ogr
        from qfit.activities.domain.activity_query import ActivityQuery, build_subset_string
        source = ogr.Open(self.source, 1)
        source.ExecuteSQL("UPDATE activity_tracks SET activity_type = CASE source_activity_id WHEN '0' THEN 'Walk' WHEN '1' THEN 'Hike' ELSE 'Run' END")
        source.ExecuteSQL("UPDATE activity_tracks SET sport_type = activity_type")
        source = None
        query = ActivityQuery(activity_types=("Walk", "Hike"))
        subset = build_subset_string(query)
        artifact = build_route_heatmap(RouteHeatmapRequest(self.source, subset, self.request.cache_dir))
        self.assertEqual(artifact.activity_count, 2)
        self.assertNotEqual(artifact.cache_key, build_route_heatmap(self.request).cache_key)
        reversed_subset = build_subset_string(ActivityQuery(activity_types=("Hike", "Walk")))
        self.assertEqual(subset, reversed_subset)
        self.assertTrue(build_route_heatmap(RouteHeatmapRequest(self.source, reversed_subset, self.request.cache_dir)).reused)

    def test_fixed_red_renderer_and_raster_values_survive_navigation(self):
        artifact = build_route_heatmap(self.request)
        layer = create_route_heatmap_layer(artifact)
        dataset = gdal.Open(artifact.path)
        self.assertIsNotNone(dataset)
        # Read a physical tile, not the potentially huge sparse VRT bounding box.
        tile = next(Path(artifact.path).parent.glob("*.tif"))
        data = gdal.Open(str(tile)).ReadAsArray()
        self.assertGreater(float(data.max()), 0)
        maximum = layer.renderer().classificationMax()
        for extent, size in ((layer.extent(), QSize(600, 400)),
                             (QgsRectangle(layer.extent().center().x() - 500, layer.extent().center().y() - 500,
                                           layer.extent().center().x() + 500, layer.extent().center().y() + 500), QSize(900, 600))):
            settings = QgsMapSettings()
            settings.setLayers([layer])
            settings.setDestinationCrs(layer.crs())
            settings.setExtent(extent)
            settings.setOutputSize(size)
            settings.setBackgroundColor(QColor("white"))
            job = QgsMapRendererSequentialJob(settings)
            job.start()
            job.waitForFinished()
            self.assertFalse(job.renderedImage().isNull())
            self.assertEqual(layer.renderer().classificationMax(), maximum)
            self.assertTrue(np.array_equal(data, gdal.Open(str(tile)).ReadAsArray()))
        colors = layer.renderer().shader().rasterShaderFunction().colorRampItemList()
        self.assertTrue(all(item.color.red() >= item.color.green() and item.color.red() >= item.color.blue()
                            for item in colors))
        layer = None
        dataset = None

    def test_cancel_never_publishes_partial_cache_and_empty_selection_is_empty(self):
        with self.assertRaises(HeatmapCancelled):
            build_route_heatmap(self.request, cancelled=lambda: True)
        self.assertEqual(list((self.root / "cache").iterdir()), [])
        request = RouteHeatmapRequest(self.source, "source_activity_id = 'missing'", self.request.cache_dir)
        self.assertIsNone(build_route_heatmap(request))

    def test_sparse_separated_regions_do_not_allocate_empty_world_raster(self):
        other = write_route_heatmap_fixture(self.root / "separated.gpkg", [
            [(7.34, 46.23), (7.35, 46.24)], [(-73.99, 40.73), (-73.98, 40.74)]])
        artifact = build_route_heatmap(RouteHeatmapRequest(other, "", self.request.cache_dir))
        manifest = json.loads((Path(artifact.path).parent / "manifest.json").read_text())
        self.assertEqual(artifact.crs, "EPSG:3857")
        self.assertLess(manifest["tile_count"], 20)
        self.assertLess(sum(p.stat().st_size for p in Path(artifact.path).parent.iterdir()), 2_000_000)

    def test_smoothing_is_continuous_across_tile_boundaries(self):
        parameters = RouteDensityParameters(cell_size=10, sigma=20, tile_size=32)
        tiles = {}
        for x in (0, 1):
            path = self.root / f"counts-{x}.bin"
            data = np.memmap(path, dtype="uint32", mode="w+", shape=(32, 32))
            data[:] = 0
            data[16, :] = 1
            data.flush()
            del data
            tiles[x, 0] = path
        left = _smooth_tile((0, 0), tiles, parameters)
        right = _smooth_tile((1, 0), tiles, parameters)
        self.assertTrue(np.allclose(left[:, -1], right[:, 0]))

    def test_large_sparse_selection_builds_real_raster_without_false_budget_error(self):
        source = write_route_heatmap_fixture(self.root / "large-sparse.gpkg", sparse_heatmap_routes())
        parameters = RouteDensityParameters(tile_size=32)
        request = RouteHeatmapRequest(source, "", self.request.cache_dir, parameters)
        source_digest = hashlib.sha256(Path(source).read_bytes()).hexdigest()
        artifact = build_route_heatmap(request)
        directory = Path(artifact.path).parent
        manifest = json.loads((directory / "manifest.json").read_text())
        self.assertEqual(artifact.activity_count, 457)
        self.assertEqual(manifest["tile_count"], 457)
        self.assertEqual(manifest["parameters"]["cell_size"], 10)
        self.assertEqual(manifest["parameters"]["sigma"], 20)
        self.assertEqual(source_digest, hashlib.sha256(Path(source).read_bytes()).hexdigest())
        dataset = gdal.Open(artifact.path)
        self.assertEqual(dataset.GetGeoTransform()[1], 10)
        self.assertGreater(float(gdal.Open(str(next(directory.glob("*.tif")))).ReadAsArray().max()), 0)
        self.assertTrue(build_route_heatmap(request).reused)
        layer = create_route_heatmap_layer(artifact)
        self.assertTrue(layer.isValid())
        self.assertEqual(layer.renderer().classificationMax(), artifact.maximum)
        dataset = None
        layer = None
