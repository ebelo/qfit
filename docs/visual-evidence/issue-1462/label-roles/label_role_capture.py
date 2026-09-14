"""Replay this audit's fixed Light cameras from an immutable source snapshot.

Use the recorded baseline checkout. Run native mode in a font-enabled QGIS
process; browser mode requires Playwright/Chromium. Credentials follow the
harness's authorized inherited route, never a command-line token.
"""
import argparse,json,os,sys
from pathlib import Path
from dataclasses import replace
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--repo',type=Path,required=True)
p.add_argument('--evidence',type=Path,required=True)
p.add_argument('--camera',required=True)
p.add_argument('--mode',choices=['native','browser'],required=True)
p.add_argument('--qgis-major',choices=['3','4'],default='3')
p.add_argument('--variant',choices=['control','repeat'],default='control')
p.add_argument('--projection',choices=['source','mercator'],default='source')
p.add_argument('--chromium')
a=p.parse_args();ROOT=a.repo.resolve();OUT=a.evidence.resolve();sys.path.insert(0,str(ROOT.parent))
from qfit.validation import mapbox_outdoors_comparison as cmp
CAMERAS={}
for name,lon,lat,zoom in (('cairo-region-z8',31.2357,30.0444,8),('cairo-nile-z14',31.224,30.0444,14),('jerusalem-region-z8',35.2137,31.7683,8),('jerusalem-city-z14',35.215,31.78,14)):
    CAMERAS[name]=replace(cmp.LIGHT_CAMERAS['zurich-region-z8-light'],name=name,longitude=lon,latitude=lat,zoom=zoom)
def worker(camera_name, variant, version):
    from qgis.core import QgsApplication
    from qgis.core import Qgis
    from qfit.visualization.infrastructure.background_map_service import BackgroundMapService
    app=QgsApplication([],False); app.initQgis()
    source=json.loads((OUT/'source.json').read_text())
    folder=OUT/version/camera_name/variant; folder.mkdir(parents=True,exist_ok=True)
    token=cmp.resolve_mapbox_token(provided_token=None)
    cmp.render_qgis_vector(camera=CAMERAS[camera_name],token=token,output_path=folder/'qgis.png',style_definition=source,qgis_label_styles_path=folder/'labels.json',qgis_runtime_path=folder/'runtime.json',activity_overlay=camera_name.endswith('-activity'))
    metrics=cmp.build_image_diff(reference_path=OUT/'reference'/camera_name/'mapbox.png',candidate_path=folder/'qgis.png',output_path=folder/'diff.png')
    (folder/'metrics.json').write_text(json.dumps(metrics,indent=2))
    print(camera_name,variant,metrics['normalized_mean_absolute_channel_delta'],flush=True)
    # Native renderer cleanup remains process-scoped.
    os._exit(0)

def reference(names,projection="source"):
    import math
    if a.chromium:cmp._chromium_executable=lambda:a.chromium
    original_html=cmp.build_mapbox_gl_html
    def audited_html(**kw):
        camera=kw['camera'];cx,cy=cmp.camera_center_web_mercator(camera)
        mpp=cmp.WEB_MERCATOR_HALF_WORLD*2/(512*2**camera.zoom);anchors=[]
        for dx,dy in ((0,0),(-300,-200),(300,200),(-300,200),(300,-200)):
            x=cx+dx*mpp;y=cy-dy*mpp
            anchors.append({'lnglat':[x/cmp.WEB_MERCATOR_HALF_WORLD*180,math.degrees(2*math.atan(math.exp(y/6378137))-math.pi/2)],'expected_pixel':[camera.width/2+dx,camera.height/2+dy]})
        html=original_html(**kw).replace('mapbox_gl_version: mapboxgl.version,','mapbox_gl_version: mapboxgl.version,projection_anchors: '+json.dumps(anchors)+'.map(a=>{const p=map.project(a.lnglat);return {...a,actual_pixel:[p.x,p.y]};}),')
        return html.replace("map.once('idle', () => { window.qfitMapboxReady = true; });", "map.once('idle', () => { window.qfitMapboxFeatures=map.queryRenderedFeatures().filter(f=>f.layer.type==='symbol').map(f=>({id:f.id,owner:f.layer.id,properties:f.properties,geometry:f.geometry})); window.qfitMapboxReady = true; });")
    cmp.build_mapbox_gl_html=audited_html
    original_js=cmp.build_node_playwright_capture_script
    def audited_js():
        return original_js().replace("await page.screenshot({ path: outputPath, fullPage: false });", "const audit=await page.evaluate(()=>({features:window.qfitMapboxFeatures||[],source_features:window.qfitSourceAdmin||[]})); fs.writeFileSync(outputPath+'.features.json',JSON.stringify(audit,null,2)); await page.screenshot({ path: outputPath, fullPage: false });")
    cmp.build_node_playwright_capture_script=audited_js
    token=cmp.resolve_mapbox_token(provided_token=None)
    source=json.loads((OUT/'source.json').read_text())
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

if a.mode=='native':worker(a.camera,a.variant,a.qgis_major)
else:reference([a.camera],a.projection)
