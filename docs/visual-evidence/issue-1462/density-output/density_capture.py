"""Reproduce the audited Light density/PDF worker from an ordinary qfit checkout.

Requires PyQGIS, the existing open fonts, and the harness's authorized inherited
network/credential environment. Never put tokens on the command line. See README.
"""
import argparse,json,os,sys
from pathlib import Path
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--repo',type=Path,required=True,help='qfit source checkout')
parser.add_argument('--output-root',type=Path,required=True)
parser.add_argument('--source-style',type=Path,required=True,help='audited Light style JSON')
parser.add_argument('--version',choices=('3','4'),required=True,help='runtime label, not a QGIS selector')
parser.add_argument('--camera',choices=('bern-urban-z12-light','geneva-urban-z14-light'),required=True)
parser.add_argument('--variant',choices=('dpi96','dpi96-repeat','dpr2','dpr2-repeat','dpi192','dpi192-repeat','dpr2-trace','pdfs-trace','pdfs-control'),required=True)
args=parser.parse_args()
repo=args.repo.resolve();OUT=args.output_root.resolve();source_path=args.source_style.resolve()
sys.path.insert(0,str(repo.parent))
from qfit.validation import mapbox_outdoors_comparison as cmp
from dataclasses import replace
CAMERAS={k:cmp.LIGHT_CAMERAS[k] for k in ('bern-urban-z12-light','geneva-urban-z14-light')}
def source_for(camera):
    return json.loads(source_path.read_text())
def worker(version,name,variant):
    from qgis.core import QgsApplication
    app=QgsApplication([],False);app.initQgis()
    camera=CAMERAS[name];folder=OUT/version/name/variant;folder.mkdir(parents=True,exist_ok=True)
    density=2 if '192' in variant else 1
    if density==2: camera=replace(camera,width=camera.width*2,height=camera.height*2,zoom=camera.zoom+1)
    if True:

        import qgis.core
        original=qgis.core.QgsMapSettings
        class ProbeMapSettings(original):
            def __init__(self):
                super().__init__(); self.setOutputDpi(96*density)
                if variant.startswith('dpr2'):self.setDevicePixelRatio(2)
        qgis.core.QgsMapSettings=ProbeMapSettings

    trace=set()
    if variant.endswith('-trace'):
        from qgis.core import QgsExpressionFunction,QgsExpression,QgsSymbolLayer,QgsProperty
        from qfit.visualization.infrastructure.background_map_service import BackgroundMapService
        class Trace(QgsExpressionFunction):
            def __init__(self):super().__init__('qfitNativeZoomTrace',4,'qfit validation')
            def func(self,values,context,parent,node):
                trace.add(tuple(float(v) for v in values[:3]));return values[3]
        trace_function=Trace();QgsExpression.registerFunction(trace_function)
        original_apply=BackgroundMapService._apply_mapbox_gl_style
        def trace_apply(service,layer,*args,**kwargs):
            result=original_apply(service,layer,*args,**kwargs);renderer=layer.renderer();styles=list(renderer.styles())
            for style in styles:
                if style.styleName() not in ('road-simple','tunnel-simple','bridge-simple','bridge-case-simple'):continue
                symbol=style.symbol();sl=symbol.symbolLayer(0);properties=sl.dataDefinedProperties();prop=properties.property(QgsSymbolLayer.PropertyStrokeWidth)
                expression=prop.asExpression();assert expression
                wrapped='qfitNativeZoomTrace(@vector_tile_zoom,@zoom_level,coalesce(@map_scale,-1),('+expression+'))'
                assert not QgsExpression(wrapped).hasParserError()
                properties.setProperty(QgsSymbolLayer.PropertyStrokeWidth,QgsProperty.fromExpression(wrapped));sl.setDataDefinedProperties(properties)
            renderer.setStyles(styles);return result
        BackgroundMapService._apply_mapbox_gl_style=trace_apply
    if variant.startswith('pdf'):
        import qgis.core
        original_job=qgis.core.QgsMapRendererParallelJob
        class ExportJob:
            def __init__(self,settings):
                self.settings=settings; self.inner=original_job(settings)
            def start(self):self.inner.start()
            def waitForFinished(self):
                self.inner.waitForFinished()
                from qgis.core import QgsProject,QgsPrintLayout,QgsLayoutItemMap,QgsLayoutSize,QgsLayoutExporter
                from qfit.atlas.export_task import AtlasExportTask
                project=QgsProject();layout=QgsPrintLayout(project);layout.initializeDefaults()
                width=camera.width*25.4/96;height=camera.height*25.4/96
                layout.pageCollection().pages()[0].setPageSize(QgsLayoutSize(width,height))
                item=QgsLayoutItemMap(layout);layout.addLayoutItem(item)
                item.attemptResize(QgsLayoutSize(width,height));item.setCrs(self.settings.destinationCrs())
                item.setLayers(self.settings.layers());item.setKeepLayerSet(True);item.zoomToExtent(self.settings.visibleExtent())
                exporter=QgsLayoutExporter(layout);pdf_settings=AtlasExportTask._build_pdf_export_settings()
                original_dpi=pdf_settings.dpi
                for export_dpi in (96,150,192):
                    for repeated in (False,True):
                        prefix='pdf'+str(export_dpi)+('-repeat' if repeated else '')
                        pdf_settings.dpi=export_dpi;trace.clear();item.invalidateCache()
                        result=exporter.exportToPdf(str(folder/(prefix+'.pdf')),pdf_settings)
                        assert result==QgsLayoutExporter.Success, 'PDF export failed'
                        extent=item.extent()
                        (folder/(prefix+'-context.json')).write_text(json.dumps(dict(dpi=pdf_settings.dpi,production_default_dpi=original_dpi,force_vector=pdf_settings.forceVectorOutput,rasterize_whole_image=pdf_settings.rasterizeWholeImage,page_mm=[width,height],map_scale=item.scale(),extent=[extent.xMinimum(),extent.yMinimum(),extent.xMaximum(),extent.yMaximum()],renderer_trace=sorted(trace)),indent=2)+'\n')
            def renderedImage(self):return self.inner.renderedImage()
        qgis.core.QgsMapRendererParallelJob=ExportJob
    token=cmp.resolve_mapbox_token(provided_token=None)
    cmp.render_qgis_vector(camera=camera,token=token,output_path=folder/'qgis.png',style_definition=source_for(camera),qgis_label_styles_path=folder/'labels.json',qgis_runtime_path=folder/'runtime.json',qgis_preprocessed_style_path=folder/'style.json')
    if variant.endswith('-trace'):
        assert trace, 'No renderer trace obtained'
        (folder/'renderer-trace.json').write_text(json.dumps({'fields':['vector_tile_zoom','zoom_level','map_scale'],'values':sorted(trace)},indent=2)+'\n')
    print('qgis',version,name,variant,flush=True);os._exit(0)
if (OUT/args.version/args.camera/args.variant).exists():
    parser.error('Refusing to overwrite an existing variant directory')
try:
    worker(args.version,args.camera,args.variant)
except Exception as exc:
    # Qt/provider errors may contain request URLs; do not print exception text.
    print('density_capture_failed',type(exc).__name__,flush=True)
    os._exit(1)
