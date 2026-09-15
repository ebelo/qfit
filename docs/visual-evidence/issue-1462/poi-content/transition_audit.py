"""Compare explicit source/native POI transition contexts without equating feature counts."""
import json
from pathlib import Path
P=Path(__file__).resolve().parent
load=lambda path:json.loads(path.read_text())
rows=[]
for v in ('3','4'):
 for camera in load(P/'cameras.json'):
  if not camera.startswith('geneva-poi-'):continue
  browser=load(P/'reference-mercator'/camera/'mapbox.png.features.json')['features']
  context=load(P/v/camera/'before/runtime.json')['render_context']
  records=[r for r in load(P/v/camera/'before/placed-labels.json') if r['provider_id'] in ('25','26','27')]
  rows.append({'runtime':v,'camera':camera,'requested_zoom':context['requested_camera_zoom'],
   'native_continuous_zoom':context['vector_tile_zoom'],'native_integer_render_zoom':context['integer_render_zoom'],
   'native_integer_fetch_zoom':context['integer_fetch_zoom'],'source_rendered_poi_records':sum(r['owner']=='poi-label' for r in browser),
   'native_poi_placement_records':len(records),'native_active_provider_ids':sorted({r['provider_id'] for r in records}),
   'scope':'Counts from different pipelines, not unique features or source/native feature-ID parity. Baseline activation retained After; no interactive transition pass.'})
(P/'transition-audit.json').write_text(json.dumps(rows,indent=2)+'\n')
print('Transition cells',len(rows))
