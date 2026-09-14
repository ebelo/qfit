"""Replay fixed-revision Light national-background probes with explicit paths.

Use the baseline checkout for control/repeat/diagnostic variants, candidate for
production/final. The source/runtime hashes are checked before native rendering.
Use a writable copy of the evidence directory. Credentials follow the authorized
harness route; no credentials are stored by this generator.
"""
import argparse,hashlib,json,os,sys
from pathlib import Path
from dataclasses import replace
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--repo',type=Path,required=True)
parser.add_argument('--evidence',type=Path,required=True)
parser.add_argument('--camera',required=True)
parser.add_argument('--qgis-major',choices=['3','4'],default='3')
parser.add_argument('--variant',choices=['pdf-before','pdf-after'],default='pdf-before')
parser.add_argument('--mode',choices=['native','browser'],default='native')
parser.add_argument('--projection',choices=['source','mercator'],default='source')
parser.add_argument('--chromium')
args=parser.parse_args()
sys.path.insert(0,str(args.repo.resolve().parent))
from qfit.validation import mapbox_outdoors_comparison as cmp
ROOT=args.repo.resolve();OUT=args.evidence.resolve()
CAMERAS=dict(cmp.LIGHT_CAMERAS)
for name,lon,lat,zoom in (('kashmir-z6.9',75.1,34.6,6.9),('kashmir-z7',75.1,34.6,7),('kashmir-z7.1',75.1,34.6,7.1),('cyprus-z7',33.1,35.05,7),('swiss-admin1-z8',8.3,47.1,8),('us-admin1-z7',-105.7,40.95,7)):
    CAMERAS[name]=replace(cmp.LIGHT_CAMERAS['zurich-region-z8-light'],name=name,longitude=lon,latitude=lat,zoom=zoom)
for z in (2.9,3,3.1,3.9,4,4.1):
    n=f'overview-opacity-z{z}'
    CAMERAS[n]=replace(cmp.LIGHT_CAMERAS['switzerland-alps-z5-light'],name=n,zoom=z)
for z in (11.9,12,12.1):
    n=f'lausanne-width-z{z}'
    CAMERAS[n]=replace(cmp.LIGHT_CAMERAS['lausanne-lavaux-z10-light'],name=n,zoom=z)
for parent in ('lausanne-lavaux-z10-light','zurich-region-z8-light'):
    n=parent+'-activity';CAMERAS[n]=replace(CAMERAS[parent],name=n)
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
        if variant in ('width-opacity', 'opacity-only', 'width-only'):
            from qgis.core import QgsProperty, QgsSymbolLayer, QgsSymbol
            styles=list(layer.renderer().styles())
            for rule in styles:
                if rule.styleName() != 'admin-0-boundary-bg': continue
                stroke=rule.symbol().symbolLayer(0)
                if variant != 'opacity-only':
                    stroke.setDataDefinedProperty(QgsSymbolLayer.PropertyStrokeWidth, QgsProperty.fromExpression('(CASE WHEN @vector_tile_zoom <= 3 THEN 5.2 WHEN @vector_tile_zoom <= 12 THEN 5.2 + 5.2 * (@vector_tile_zoom - 3) / 9 ELSE 10.4 END) * 25.4 / 96'))
                if variant != 'width-only':
                    rule.symbol().setDataDefinedProperty(QgsSymbol.PropertyOpacity, QgsProperty.fromExpression('CASE WHEN @vector_tile_zoom <= 3 THEN 0 WHEN @vector_tile_zoom < 4 THEN 50 * (@vector_tile_zoom - 3) ELSE 50 END'))
            layer.renderer().setStyles(styles)
        from qgis.core import QgsSymbolLayer
        for rule in layer.renderer().styles():
            if not rule.styleName().startswith('admin-'):continue
            symbol=rule.symbol()
            changed.append({'owner':rule.styleName(),'filter':rule.filterExpression(),'minzoom':rule.minZoomLevel(),'maxzoom':rule.maxZoomLevel(),'symbol_opacity':symbol.opacity(),'symbol_dd':{str(k):symbol.dataDefinedProperties().property(k).asExpression() for k in symbol.dataDefinedProperties().propertyKeys()},'layers':[{'properties':sl.properties(),'dd':{str(k): {'active':sl.dataDefinedProperties().property(k).isActive(),'expression':sl.dataDefinedProperties().property(k).asExpression()} for k in sl.dataDefinedProperties().propertyKeys()}} for sl in symbol.symbolLayers()]})
    BackgroundMapService._apply_mapbox_gl_style=apply
    folder=OUT/version/camera_name/variant; folder.mkdir(parents=True,exist_ok=True)
    from pdf_worker import install
    install(CAMERAS[camera_name],folder)
    token=cmp.resolve_mapbox_token(provided_token=None)
    cmp.render_qgis_vector(camera=CAMERAS[camera_name],token=token,output_path=folder/'qgis.png',style_definition=source,qgis_label_styles_path=folder/'labels.json',qgis_runtime_path=folder/'runtime.json',activity_overlay=camera_name.endswith('-activity'))
    metrics=cmp.build_image_diff(reference_path=OUT/'reference'/camera_name/'mapbox.png',candidate_path=folder/'qgis.png',output_path=folder/'diff.png')
    (folder/'metrics.json').write_text(json.dumps(metrics,indent=2)); (folder/'changed.json').write_text(json.dumps(changed,indent=2))
    print(camera_name,variant,metrics['normalized_mean_absolute_channel_delta'],flush=True)
    # Native renderer cleanup remains process-scoped.
    os._exit(0)

def reference(names,projection="source"):
    import math
    original_html=cmp.build_mapbox_gl_html
    def audited_html(**kw):
        camera=kw['camera'];cx,cy=cmp.camera_center_web_mercator(camera)
        mpp=cmp.WEB_MERCATOR_HALF_WORLD*2/(512*2**camera.zoom);anchors=[]
        for dx,dy in ((0,0),(-300,-200),(300,200),(-300,200),(300,-200)):
            x=cx+dx*mpp;y=cy-dy*mpp
            anchors.append({'lnglat':[x/cmp.WEB_MERCATOR_HALF_WORLD*180,math.degrees(2*math.atan(math.exp(y/6378137))-math.pi/2)],'expected_pixel':[camera.width/2+dx,camera.height/2+dy]})
        html=original_html(**kw).replace('mapbox_gl_version: mapboxgl.version,','mapbox_gl_version: mapboxgl.version,projection_anchors: '+json.dumps(anchors)+'.map(a=>{const p=map.project(a.lnglat);return {...a,actual_pixel:[p.x,p.y]};}),')
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
            folder=OUT/('reference'+('' if projection=='source' else '-mercator')+suffix)/name;folder.mkdir(parents=True,exist_ok=True)
            if (folder/'mapbox.png').exists():continue
            try:
                cmp.render_browser_reference(camera=CAMERAS[name],token=token,output_path=folder/'mapbox.png',timeout_ms=90000,style_definition=source,browser_runtime_path=folder/'runtime.json',reference_projection=projection,activity_overlay=name.endswith('-activity'))
            except Exception:
                print('browser_capture_failed',name,flush=True);raise SystemExit(1)
            print('reference',name,suffix,flush=True)

if args.mode=='native':
    provenance=json.loads((OUT/'generator-provenance.json').read_text())
    assert hashlib.sha256((OUT/'source.json').read_bytes()).hexdigest()==provenance['source_sha256'], 'Source snapshot differs'
    variant='candidate' if args.variant=='pdf-after' else 'baseline'
    for filename,expected in provenance['runtime_sources'][variant].items():
        assert hashlib.sha256((ROOT/filename).read_bytes()).hexdigest()==expected, ('Runtime differs from captured '+variant,filename)
    worker(args.camera,args.variant,args.qgis_major)
else:
    if args.chromium:cmp._chromium_executable=lambda:args.chromium
    reference([args.camera],args.projection)
