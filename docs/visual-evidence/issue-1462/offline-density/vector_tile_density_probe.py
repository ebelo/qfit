"""Credential-free native vector-tile density reproduction (not a parity gate).

Run with real PyQGIS: python3 vector_tile_density_probe.py
--output-dir <new-directory>. All geometry is synthetic; no Mapbox access occurs.
"""

import argparse
import hashlib
import json
import shutil
from pathlib import Path


def _fixture(output, fixture=None):
    from qgis.core import (
        QgsFeature, QgsGeometry, QgsRectangle, QgsVectorLayer,
        QgsVectorTileLayer, QgsVectorTileWriter,
    )

    # Web Mercator, a fixed 640 x 480 logical-pixel view at source zoom 12.25.
    resolution = 40075016.6855784 / (512 * 2 ** 12.25)
    width, height = 640 * resolution, 480 * resolution
    extent = QgsRectangle(829000, 5930000, 829000 + width, 5930000 + height)
    source = QgsVectorLayer('LineString?crs=EPSG:3857&field=role:string', 'density', 'memory')
    features = []
    for role, fraction in [('always', 0.25), ('zoom13', 0.5), ('width', 0.75)]:
        feature = QgsFeature(source.fields())
        feature['role'] = role
        y = extent.yMinimum() + height * fraction
        feature.setGeometry(QgsGeometry.fromWkt(
            f'LINESTRING ({extent.xMinimum() + width * .1} {y}, '
            f'{extent.xMinimum() + width * .5} {y + height * .02}, '
            f'{extent.xMaximum() - width * .1} {y})'
        ))
        features.append(feature)
    if not source.dataProvider().addFeatures(features)[0]:
        raise RuntimeError('Could not create synthetic features')
    source.updateExtents()
    tile_path = output / 'fixture.mbtiles'
    if any(char in str(tile_path) for char in '&?#'):
        raise ValueError('Use an output path without URI query delimiters')
    uri = 'type=mbtiles&url=' + str(tile_path)
    if fixture is not None:
        shutil.copyfile(fixture, tile_path)
        layer = QgsVectorTileLayer(uri, 'Synthetic density fixture')
        if not layer.isValid():
            raise RuntimeError('Provided fixture is invalid')
        return layer, extent
    writer = QgsVectorTileWriter()
    writer.setDestinationUri(uri)
    writer.setExtent(extent)
    writer.setMinZoom(11)
    writer.setMaxZoom(15)
    writer.setLayers([QgsVectorTileWriter.Layer(source)])
    if not writer.writeTiles():
        raise RuntimeError('Synthetic tile generation failed: ' + writer.errorMessage())
    layer = QgsVectorTileLayer(uri, 'Synthetic density fixture')
    if not layer.isValid():
        raise RuntimeError('Synthetic tile layer is invalid')
    return layer, extent


def _renderer(layer, traced):
    from qgis.core import (
        Qgis, QgsLineSymbol, QgsProperty, QgsSymbolLayer,
        QgsVectorTileBasicRenderer, QgsVectorTileBasicRendererStyle,
    )
    styles = []
    for role, color in [('always', '#b02020'), ('zoom13', '#2040d0'), ('width', '#208020')]:
        style = QgsVectorTileBasicRendererStyle(role, 'density', Qgis.GeometryType.Line)
        style.setFilterExpression(f'"role" = \'{role}\'')
        if role == 'zoom13':
            style.setMinZoomLevel(13)
        symbol = QgsLineSymbol.createSimple({'line_color': color, 'line_width': '1'})
        expression = '@vector_tile_zoom * 0.08' if role == 'width' else '1'
        if traced:
            expression = ('qfitDensityTrace(@vector_tile_zoom, @zoom_level, '
                          f'coalesce(@map_scale, -1), {expression})')
        symbol.symbolLayer(0).setDataDefinedProperty(
            QgsSymbolLayer.PropertyStrokeWidth, QgsProperty.fromExpression(expression),
        )
        style.setSymbol(symbol)
        styles.append(style)
    renderer = QgsVectorTileBasicRenderer()
    renderer.setStyles(styles)
    layer.setRenderer(renderer)


def _export_png(layer, extent, dpi, output):
    from qgis.core import QgsMapRendererParallelJob, QgsMapSettings
    from qgis.PyQt.QtCore import QSize
    from qgis.PyQt.QtGui import QColor

    settings = QgsMapSettings()
    settings.setDestinationCrs(layer.crs())
    settings.setLayers([layer])
    settings.setOutputDpi(dpi)
    settings.setOutputSize(QSize(round(640 * dpi / 96), round(480 * dpi / 96)))
    settings.setExtent(extent)
    settings.setBackgroundColor(QColor('white'))
    job = QgsMapRendererParallelJob(settings)
    job.start()
    job.waitForFinished()
    if job.errors():
        raise RuntimeError('Native PNG rendering reported an error')
    image = job.renderedImage()
    if image.isNull() or not image.save(str(output)):
        raise RuntimeError('Native PNG export failed')
    # A persistent red feature must actually render; a blank success is invalid.
    if not any(image.pixelColor(x, y).red() > 2 * image.pixelColor(x, y).green()
               for y in range(image.height()) for x in (image.width() // 2,)):
        raise RuntimeError('Persistent synthetic feature did not render')
    return settings.scale()


def _export_pdf(layer, extent, dpi, output):
    from qgis.core import (
        QgsLayoutExporter, QgsLayoutItemMap, QgsLayoutSize, QgsPrintLayout, QgsProject,
    )
    project = QgsProject()
    layout = QgsPrintLayout(project)
    layout.initializeDefaults()
    size = QgsLayoutSize(640 * 25.4 / 96, 480 * 25.4 / 96)
    layout.pageCollection().pages()[0].setPageSize(size)
    item = QgsLayoutItemMap(layout)
    layout.addLayoutItem(item)
    item.attemptResize(size)
    item.setCrs(layer.crs())
    item.setLayers([layer])
    item.setKeepLayerSet(True)
    item.zoomToExtent(extent)
    settings = QgsLayoutExporter.PdfExportSettings()
    settings.dpi = dpi
    settings.forceVectorOutput = True
    settings.rasterizeWholeImage = False
    if QgsLayoutExporter(layout).exportToPdf(str(output), settings) != QgsLayoutExporter.Success:
        raise RuntimeError('Native PDF export failed')
    return item.scale()


def run_probe(output, fixture=None):
    """Write synthetic outputs and observations; OPEN is not a successful invariant."""
    from qgis.core import Qgis, QgsExpression, QgsExpressionFunction
    from qgis.PyQt.QtCore import QT_VERSION_STR

    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        raise ValueError('Output directory must be empty')
    layer, extent = _fixture(output, fixture)
    trace = set()

    class Trace(QgsExpressionFunction):
        def __init__(self):
            super().__init__('qfitDensityTrace', 4, 'qfit validation')

        def func(self, values, context, parent, node):
            trace.add(tuple(float(value) for value in values[:3]))
            return values[3]

    function = Trace()
    if not QgsExpression.registerFunction(function):
        raise RuntimeError('Density trace function already registered')
    records = []
    try:
        for kind, exporter in [('png', _export_png), ('pdf', _export_pdf)]:
            for dpi in (96, 150, 192):
                for traced in (False, True):
                    _renderer(layer, traced)
                    for repeat in range(2):
                        filename = f'{kind}-{dpi}-{"trace" if traced else "plain"}-{repeat}.{kind}'
                        trace.clear()
                        scale = exporter(layer, extent, dpi, output / filename)
                        if traced and not trace:
                            raise RuntimeError('Renderer trace is empty')
                        records.append(dict(file=filename, kind=kind, dpi=dpi, traced=traced,
                                            repeat=repeat, map_scale=scale, trace=sorted(trace),
                                            sha256=hashlib.sha256((output / filename).read_bytes()).hexdigest()))
    finally:
        QgsExpression.unregisterFunction('qfitDensityTrace')
    verdicts = {}
    for kind in ('png', 'pdf'):
        zooms = {tuple(row[:2]) for record in records if record['kind'] == kind
                 for row in record['trace']}
        verdicts[kind] = 'PASS (scoped native zoom only)' if len(zooms) == 1 else 'OPEN'
    report = dict(qgis=Qgis.QGIS_VERSION, qgis_revision=Qgis.QGIS_DEV_VERSION, qt=QT_VERSION_STR,
                  geometry='synthetic, not Mapbox data or a Light cartographic fixture',
                  fixture_sha256=hashlib.sha256((output / 'fixture.mbtiles').read_bytes()).hexdigest(),
                  generator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  crs=layer.crs().authid(), extent=[extent.xMinimum(), extent.yMinimum(),
                                                extent.xMaximum(), extent.yMaximum()],
                  logical_pixels=[640, 480], baseline_dpi=96,
                  trace_fields=['vector_tile_zoom', 'zoom_level', 'map_scale_or_minus_one'],
                  native_zoom_density_verdict=verdicts, records=records)
    (output / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', required=True, type=Path)
    parser.add_argument('--fixture-mbtiles', type=Path, help='Reuse the published synthetic MBTiles fixture')
    args = parser.parse_args()
    from qgis.core import QgsApplication
    app = QgsApplication([], False)
    app.initQgis()
    report = run_probe(args.output_dir, args.fixture_mbtiles)
    print(json.dumps(report['native_zoom_density_verdict']))
    # QGIS objects must be destroyed before shutting down the application.
    app.exitQgis()


if __name__ == '__main__':
    main()
