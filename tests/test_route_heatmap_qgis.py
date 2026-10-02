"""Real storage/raster/rendering invariants in both required QGIS lanes."""
import hashlib
import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

from tests import _path  # noqa: F401
from tests.route_heatmap_fixture import write_route_heatmap_fixture

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
        self.assertTrue(tile.exists())
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
