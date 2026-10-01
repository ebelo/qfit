#!/usr/bin/env python3
"""Credential-free, synthetic matched heatmap captures and cold/warm timings.

Run in a real QGIS runtime with --baseline pointing to the baseline module.
Outputs are review evidence, not private activity data or plugin assets.
"""
import argparse
import hashlib
import importlib.util
import json
import math
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from qgis.core import (QgsApplication, QgsCoordinateTransform, QgsMapSettings,
                       QgsMapRendererSequentialJob, QgsProject, QgsRectangle, QgsVectorLayer)
from qgis.PyQt.QtCore import QSize
from qgis.PyQt.QtGui import QColor
from tests.qgis_app import get_shared_qgis_app
from tests.route_heatmap_fixture import write_route_heatmap_fixture
from qfit.analysis.application.route_heatmap import RouteHeatmapRequest
from qfit.analysis.infrastructure.route_heatmap_raster import build_route_heatmap
from qfit.analysis.infrastructure.route_heatmap_layer import create_route_heatmap_layer


def _colored_pixels(image):
    return sum(image.pixelColor(x, y) != QColor('#f3f4f6')
               for y in range(image.height()) for x in range(image.width()))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--commit', required=True)
    parser.add_argument('--runtime', required=True)
    args = parser.parse_args()
    app = get_shared_qgis_app(QgsApplication)
    args.output.mkdir(parents=True, exist_ok=True)
    # Artificial curved routes: shared corridor, several branches and a few
    # isolated rides. All points below are generated, not copied from a user.
    routes = []
    for index in range(30):
        routes.append([(7.30 + step * .003,
                        46.22 + .008 * math.sin(step / 5) +
                        (max(0, step - 20) * .00012 * (index % 6)))
                       for step in range(55)])
    source = write_route_heatmap_fixture(args.output / 'synthetic.gpkg', routes)
    tracks = QgsVectorLayer(source + '|layername=activity_tracks', 'Synthetic tracks', 'ogr')
    spec = importlib.util.spec_from_file_location('qfit.analysis.infrastructure._baseline_heatmap', args.baseline)
    baseline = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(baseline)
    started = time.perf_counter()
    before, _ = baseline.build_activity_heatmap_layer(tracks, None)
    baseline_seconds = time.perf_counter() - started
    request = RouteHeatmapRequest(source, '', str(args.output / 'cache'))
    started = time.perf_counter()
    artifact = build_route_heatmap(request)
    cold_seconds = time.perf_counter() - started
    started = time.perf_counter()
    reused = build_route_heatmap(request)
    warm_seconds = time.perf_counter() - started
    after = create_route_heatmap_layer(artifact)
    destination = after.crs()
    transform = QgsCoordinateTransform(tracks.crs(), destination, QgsProject.instance())
    full = transform.transformBoundingBox(tracks.extent())
    full.scale(1.2)
    center = transform.transform(7.375, 46.212)
    matrix = {'regional': full,
              'town': QgsRectangle(center.x()-3000, center.y()-1950, center.x()+3000, center.y()+1950),
              'detail': QgsRectangle(center.x()-600, center.y()-390, center.x()+600, center.y()+390)}
    captures = []
    for camera, extent in matrix.items():
        for label, layer in [('before', before), ('after', after)]:
            for repeat in range(2):
                settings = QgsMapSettings()
                settings.setDestinationCrs(destination)
                settings.setLayers([layer])
                settings.setBackgroundColor(QColor('#f3f4f6'))
                settings.setExtent(extent)
                settings.setOutputSize(QSize(1000, 650))
                job = QgsMapRendererSequentialJob(settings)
                start = time.perf_counter()
                job.start()
                job.waitForFinished()
                seconds = time.perf_counter() - start
                image = job.renderedImage()
                name = f'{args.runtime}-{camera}-{label}-{repeat}.png'
                if image.isNull() or not image.save(str(args.output / name)):
                    raise RuntimeError('Synthetic capture failed')
                colored = _colored_pixels(image)
                if colored < 50:
                    raise RuntimeError(f'Capture has no route content: {name}')
                captures.append({'file': name, 'camera': camera, 'role': label, 'repeat': repeat,
                                 'sha256': hashlib.sha256((args.output/name).read_bytes()).hexdigest(),
                                 'size': [1000,650], 'extent': [extent.xMinimum(),extent.yMinimum(),extent.xMaximum(),extent.yMaximum()],
                                 'non_background_pixels': colored, 'render_seconds': seconds})
    report = {'baseline_commit': 'dac69530fde27a77fe39d158f929cc2fee1814ce',
              'candidate_commit': args.commit, 'runtime': args.runtime, 'synthetic_activities': len(routes),
              'geometry_sha256': hashlib.sha256(json.dumps(routes).encode()).hexdigest(),
              'cache_key': artifact.cache_key, 'crs': artifact.crs,
              'baseline_build_seconds': baseline_seconds, 'cold_build_seconds': cold_seconds,
              'warm_build_seconds': warm_seconds, 'cache_reused': reused.reused,
              'captures': captures}
    (args.output / f'{args.runtime}-manifest.json').write_text(json.dumps(report,indent=2))
    print(json.dumps({k:v for k,v in report.items() if k != 'captures'}))
    app.processEvents()


if __name__ == '__main__':
    main()
