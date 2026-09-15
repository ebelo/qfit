"""Verify named controls, native settings, source anchors and independently report metrics.

Run after completing the 15-camera matrix. Input files are never regenerated here.
Generated JSON/crops are derived artifacts, not additional capture claims.
"""
import collections,copy,hashlib,json,math
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw,ImageStat
P=Path(__file__).resolve().parent
load=lambda p:json.loads(p.read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
cameras=load(P/'cameras.json');assert len(cameras)==15
pairs=[];anchors=[];metrics=[];placements=[];settings=[]
poi_names=['poi-label-below-z16','poi-label-z16-to-z17','poi-label-z17-plus']
def compare(a,b,kind='bytes'):
 same=sorted(load(a),key=lambda r:json.dumps(r,sort_keys=True))==sorted(load(b),key=lambda r:json.dumps(r,sort_keys=True)) if kind=='placement-records' else sha(a)==sha(b)
 pairs.append({'a':str(a.relative_to(P)),'b':str(b.relative_to(P)),'kind':kind,'identical':same,'a_sha256':sha(a),'b_sha256':sha(b)})
 assert same,(a,b,kind)
for projection in ('reference','reference-mercator'):
 for camera in cameras:
  for suffix in ('','-repeat'):
   folder=P/(projection+suffix)/camera;context=load(folder/'runtime.json')
   assert context['map_loaded'] and context['tiles_loaded'] and context['map_error_count']==0
   assert Image.open(folder/'mapbox.png').size==(1280,900)
  compare(P/projection/camera/'mapbox.png',P/(projection+'-repeat')/camera/'mapbox.png')
for v in ('3','4'):
 before=load(P/f'audit{v}-before/labels.json');after=load(P/f'audit{v}-after/labels.json')
 assert len(before)==len(after)==39
 normalized=copy.deepcopy(after)
 for row in normalized:
  if row['style_name'] in poi_names:
   assert row['label_settings']['field_name']=='coalesce("name_en", "name")'
   settings.append({'runtime':v,'rule':row['style_name'],'before':'"name"','after':row['label_settings']['field_name']})
   row['label_settings']['field_name']='"name"'
 assert normalized==before
 providers={str(i) for i,row in enumerate(after) if row['style_name'] in poi_names};assert len(providers)==3
 for camera in cameras:
  for variant in ('before','before-repeat','after','after-repeat'):
   folder=P/v/camera/variant
   im=Image.open(folder/'qgis.png').convert('RGB');assert im.size==(1280,900) and max(ImageStat.Stat(im).stddev)>1
   assert load(folder/'labels.json')==(after if variant.startswith('after') else before)
  for variant in ('before','after'):
   for name in ('qgis.png','labels.json','runtime.json'):compare(P/v/camera/variant/name,P/v/camera/(variant+'-repeat')/name)
   compare(P/v/camera/variant/'placed-labels.json',P/v/camera/(variant+'-repeat')/'placed-labels.json','placement-records')
  context=load(P/v/camera/'before/runtime.json');assert context==load(P/v/camera/'after/runtime.json')
  extent=context['render_context']['visible_extent'];browser=load(P/'reference-mercator'/camera/'runtime.json')
  for anchor in browser['projection_anchors']:
   lon,lat=anchor['lnglat'];x=lon*20037508.342789244/180;y=6378137*math.log(math.tan(math.pi/4+math.radians(lat)/2))
   native=[(x-extent[0])/(extent[2]-extent[0])*1280,(extent[3]-y)/(extent[3]-extent[1])*900]
   error=max(abs(a-b) for a,b in zip(native,anchor['actual_pixel']));assert error<1e-6
   anchors.append({'camera':camera,'runtime':v,'native_pixel':native,'browser_pixel':anchor['actual_pixel'],'max_error_px':error})
  a=np.asarray(Image.open(P/v/camera/'after/qgis.png').convert('RGB')).astype(float)
  b=np.asarray(Image.open(P/v/camera/'before/qgis.png').convert('RGB')).astype(float)
  row={'camera':camera,'runtime':v,'changed_pixels':int(np.any(a!=b,axis=2).sum()),'context':context['render_context']}
  for projection in ('reference','reference-mercator'):
   ref=np.asarray(Image.open(P/projection/camera/'mapbox.png').convert('RGB')).astype(float)
   mb=float(np.abs(b-ref).mean()/255);ma=float(np.abs(a-ref).mean()/255)
   row[projection]={'before_mae':mb,'after_mae':ma,'relative_change_percent':(ma-mb)/mb*100}
  metrics.append(row)
  groups=[load(P/v/camera/variant/'placed-labels.json') for variant in ('before','after')]
  targets=[[r for r in group if r['provider_id'] in providers] for group in groups]
  other=[[r for r in group if r['provider_id'] not in providers] for group in groups]
  key=lambda r:(r['provider_id'],r['text'],r['unplaced'])
  counts=[collections.Counter(key(r) for r in group) for group in other]
  exact=lambda group:sorted([{k:v for k,v in r.items() if k!='feature_id'} for r in group],key=lambda r:json.dumps(r,sort_keys=True))
  placements.append({'camera':camera,'runtime':v,'before_pois':targets[0],'after_pois':targets[1],
   'before_poi_texts':sorted({r['text'] for r in targets[0]}),'after_poi_texts':sorted({r['text'] for r in targets[1]}),
   'nonpoi_text_population_equal':counts[0]==counts[1],'nonpoi_text_and_corners_equal':exact(other[0])==exact(other[1]),
   'removed_nonpoi_distinct_texts':sorted({r['text'] for r in other[0]}-{r['text'] for r in other[1]}),
   'added_nonpoi_distinct_texts':sorted({r['text'] for r in other[1]}-{r['text'] for r in other[0]}),
   'removed_nonpoi_records':[{'key':k,'count':n} for k,n in (counts[0]-counts[1]).items()],
   'added_nonpoi_records':[{'key':k,'count':n} for k,n in (counts[1]-counts[0]).items()],
   'scope':'PNG placement records; curved labels emit multiple full-text records. Not unique labels/features or native/source-ID equality.'})
  crops={'full':(0,0,1280,900),'crop':(450,310,830,610)}
  if camera=='geneva-streets-z18-light':crops['crop']=(900,570,1280,870)
  elif camera=='geneva-urban-z14-light':crops['crop']=(780,0,1160,300)
  elif camera in ('geneva-poi-z16-9','geneva-poi-z17','geneva-poi-z17-1'):crops['crop']=(100,400,480,700)
  elif camera in ('geneva-poi-z15-9','geneva-poi-z16','geneva-poi-z16-1'):crops['crop']=(880,430,1260,730)
  for kind,box in crops.items():
   width,height=box[2]-box[0],box[3]-box[1];panel=Image.new('RGB',(width*3,height+35),'white');draw=ImageDraw.Draw(panel)
   for i,(path,label) in enumerate([(P/'reference-mercator'/camera/'mapbox.png','Mapbox Mercator reference'),(P/v/camera/'before/qgis.png',f'QGIS{v} Before a2d1f30'),(P/v/camera/'after/qgis.png',f'QGIS{v} After 9ff2eb6')]):
    panel.paste(Image.open(path).crop(box),(width*i,35));draw.text((width*i+8,10),label,fill='black')
   panel.save(P/f'{camera}-qgis{v}-{kind}.png')
for name,doc in [('repeat-controls.json',pairs),('registration.json',anchors),('metrics.json',metrics),('placement-audit.json',placements),('settings-changes.json',settings)]:
 (P/name).write_text(json.dumps(doc,ensure_ascii=False,indent=2)+'\n')
print('verified',len(pairs),'named repeat pairs;',len(anchors),'anchors;',len(settings),'field changes')
for row in metrics:print(row['runtime'],row['camera'],row['changed_pixels'],round(row['reference-mercator']['relative_change_percent'],6))
for row in placements:
 if not row['nonpoi_text_population_equal']:print('nonpoi_population_changed',row['runtime'],row['camera'],row['removed_nonpoi_records'],row['added_nonpoi_records'])
