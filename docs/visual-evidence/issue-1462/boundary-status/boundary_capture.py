"""Public six-camera C15 replay; install qfit, PyQGIS or browser dependencies first.
Native mode uses the captured source.json and reference tree. Browser mode requires
Mapbox access and refuses a changed live source. Credentials remain in memory.
"""
import argparse,json,os,sys
from pathlib import Path
ap=argparse.ArgumentParser();ap.add_argument('--repo',type=Path,required=True);ap.add_argument('--evidence',type=Path,required=True);ap.add_argument('--mode',choices=['native','browser'],required=True);ap.add_argument('--camera',required=True);ap.add_argument('--variant',default='control');ap.add_argument('--qgis-major',choices=['3','4']);ap.add_argument('--chromium');a=ap.parse_args()
sys.path.insert(0,str(a.repo.parent))
from qfit.validation import mapbox_outdoors_comparison as cmp
OUT=a.evidence
CAMERAS={name:cmp.MapboxComparisonCamera(**row) for name,row in {'kashmir-z6.9': {'name': 'kashmir-z6.9', 'description': 'z8 regional context around Zurich for settlement hierarchy, major roads, water, and landuse balance.', 'longitude': 75.1, 'latitude': 34.6, 'zoom': 6.9, 'width': 1280, 'height': 900, 'bearing': 0.0, 'pitch': 0.0, 'style_owner': 'mapbox', 'style_id': 'light-v11'}, 'kashmir-z7': {'name': 'kashmir-z7', 'description': 'z8 regional context around Zurich for settlement hierarchy, major roads, water, and landuse balance.', 'longitude': 75.1, 'latitude': 34.6, 'zoom': 7, 'width': 1280, 'height': 900, 'bearing': 0.0, 'pitch': 0.0, 'style_owner': 'mapbox', 'style_id': 'light-v11'}, 'kashmir-z7.1': {'name': 'kashmir-z7.1', 'description': 'z8 regional context around Zurich for settlement hierarchy, major roads, water, and landuse balance.', 'longitude': 75.1, 'latitude': 34.6, 'zoom': 7.1, 'width': 1280, 'height': 900, 'bearing': 0.0, 'pitch': 0.0, 'style_owner': 'mapbox', 'style_id': 'light-v11'}, 'cyprus-z7': {'name': 'cyprus-z7', 'description': 'z8 regional context around Zurich for settlement hierarchy, major roads, water, and landuse balance.', 'longitude': 33.1, 'latitude': 35.05, 'zoom': 7, 'width': 1280, 'height': 900, 'bearing': 0.0, 'pitch': 0.0, 'style_owner': 'mapbox', 'style_id': 'light-v11'}, 'swiss-admin1-z8': {'name': 'swiss-admin1-z8', 'description': 'z8 regional context around Zurich for settlement hierarchy, major roads, water, and landuse balance.', 'longitude': 8.3, 'latitude': 47.1, 'zoom': 8, 'width': 1280, 'height': 900, 'bearing': 0.0, 'pitch': 0.0, 'style_owner': 'mapbox', 'style_id': 'light-v11'}, 'us-admin1-z7': {'name': 'us-admin1-z7', 'description': 'z8 regional context around Zurich for settlement hierarchy, major roads, water, and landuse balance.', 'longitude': -105.7, 'latitude': 40.95, 'zoom': 7, 'width': 1280, 'height': 900, 'bearing': 0.0, 'pitch': 0.0, 'style_owner': 'mapbox', 'style_id': 'light-v11'}}.items()}
def worker(camera_name, variant, version):
    from qgis.core import QgsApplication
    from qgis.core import Qgis
    from qfit.visualization.infrastructure.background_map_service import BackgroundMapService
    app=QgsApplication([],False); app.initQgis()
    source=json.loads((OUT/'source.json').read_text())
    owners={x['id']:x.get('layout',{}).get('text-font',[]) for x in source['layers']}
    original=BackgroundMapService._apply_mapbox_gl_style
    changed=[]
    def apply(self, layer, definition, **kw):
        import copy
        definition=copy.deepcopy(definition)
        original(self,layer,definition,**kw)
        if variant.startswith('without-'):
            owner=variant.removeprefix('without-')
            layer.renderer().setStyles([r for r in layer.renderer().styles() if r.styleName()!=owner])
        from qgis.core import QgsSymbolLayer
        for rule in layer.renderer().styles():
            if not rule.styleName().startswith('admin-'):continue
            symbol=rule.symbol()
            changed.append({'owner':rule.styleName(),'filter':rule.filterExpression(),'minzoom':rule.minZoomLevel(),'maxzoom':rule.maxZoomLevel(),'layers':[{'properties':sl.properties(),'dd':{str(k): {'active':sl.dataDefinedProperties().property(k).isActive(),'expression':sl.dataDefinedProperties().property(k).asExpression()} for k in sl.dataDefinedProperties().propertyKeys()}} for sl in symbol.symbolLayers()]})
    BackgroundMapService._apply_mapbox_gl_style=apply
    folder=OUT/version/camera_name/variant; folder.mkdir(parents=True,exist_ok=True)
    token=cmp.resolve_mapbox_token(provided_token=None)
    cmp.render_qgis_vector(camera=CAMERAS[camera_name],token=token,output_path=folder/'qgis.png',style_definition=source,qgis_label_styles_path=folder/'labels.json',qgis_runtime_path=folder/'runtime.json',activity_overlay=camera_name.endswith('-activity'))
    metrics=cmp.build_image_diff(reference_path=OUT/'reference'/camera_name/'mapbox.png',candidate_path=folder/'qgis.png',output_path=folder/'diff.png')
    (folder/'metrics.json').write_text(json.dumps(metrics,indent=2)); (folder/'changed.json').write_text(json.dumps(changed,indent=2))
    print(camera_name,variant,metrics['normalized_mean_absolute_channel_delta'],flush=True)
    # Native renderer cleanup remains process-scoped.
    os._exit(0)

def reference(names):
    original_html=cmp.build_mapbox_gl_html
    def audited_html(**kw):
        html=original_html(**kw)
        return html.replace("map.once('idle', () => { window.qfitMapboxReady = true; });", "map.once('idle', () => { window.qfitMapboxFeatures=map.queryRenderedFeatures().filter(f=>f.sourceLayer==='admin').map(f=>({id:f.id,owner:f.layer.id,properties:f.properties,geometry:f.geometry})); window.qfitSourceAdmin=map.querySourceFeatures('composite',{sourceLayer:'admin'}).map(f=>({id:f.id,properties:f.properties})); window.qfitMapboxReady = true; });")
    cmp.build_mapbox_gl_html=audited_html
    original_js=cmp.build_node_playwright_capture_script
    def audited_js():
        return original_js().replace("await page.screenshot({ path: outputPath, fullPage: false });", "const audit=await page.evaluate(()=>({features:window.qfitMapboxFeatures||[],source_features:window.qfitSourceAdmin||[]})); fs.writeFileSync(outputPath+'.features.json',JSON.stringify(audit,null,2)); await page.screenshot({ path: outputPath, fullPage: false });")
    cmp.build_node_playwright_capture_script=audited_js
    token=cmp.resolve_mapbox_token(provided_token=None)
    source=cmp.fetch_comparison_style_definition(token,'mapbox','light-v11')
    if (OUT/'source.json').exists(): assert source==json.loads((OUT/'source.json').read_text())
    cmp.write_redacted_style(OUT/'source.json',source,token=token)
    for name in names:
        for suffix in ('','-repeat'):
            folder=OUT/('reference'+suffix)/name;folder.mkdir(parents=True,exist_ok=True)
            try:
                cmp.render_browser_reference(camera=CAMERAS[name],token=token,output_path=folder/'mapbox.png',timeout_ms=90000,style_definition=source,browser_runtime_path=folder/'runtime.json')
            except Exception:
                print('browser_capture_failed',name,flush=True);raise SystemExit(1)
            print('reference',name,suffix,flush=True)


if a.chromium: cmp._chromium_executable=lambda:a.chromium
if a.mode=='browser':reference([a.camera])
else:
    if not a.qgis_major:ap.error('--qgis-major is required for native mode')
    if a.variant not in ('control','repeat') and not a.variant.startswith('without-admin-'):ap.error('unsupported diagnostic variant')
    worker(a.camera,a.variant,a.qgis_major)
