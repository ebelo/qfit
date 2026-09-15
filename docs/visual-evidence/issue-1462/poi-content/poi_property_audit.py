"""Replay observed POI property sets through all three native density bands.

Saved source-property replay, not native decoding/fetch/zoom or visible-label parity.
Source rank eligibility is evaluated at each band's representative zoom, not the
camera zoom; native/source zoom alignment is a separate open criterion.
"""
import json,sys
from pathlib import Path
from qgis.core import NULL,QgsExpression,QgsExpressionContext,QgsFeature,QgsField,QgsFields,QgsGeometry
P=Path(sys.argv[1]);v=sys.argv[2]
source=json.loads((P/'source.json').read_text());owner=next(r for r in source['layers'] if r['id']=='poi-label')
assert owner['layout']['text-field']==['coalesce',['get','name_en'],['get','name']]
assert owner['layout'].get('text-transform','none')=='none'
assert owner['filter']==['<=',['get','filterrank'],['+',['step',['zoom'],0,16,1,17,2],1]]
bands={'poi-label-below-z16':(15,1),'poi-label-z16-to-z17':(16,2),'poi-label-z17-plus':(17,3)}
rules={}
for variant in ('before','after'):
 inventory=json.loads((P/f'audit{v}-{variant}/labels.json').read_text())
 rules[variant]=[r for r in inventory if r['style_name'] in bands];assert len(rules[variant])==3
rows=[];summary=[]
for path in sorted((P/'reference-mercator').glob('*/mapbox.png.features.json')):
 observed=[r for r in json.loads(path.read_text())['features'] if r['owner']=='poi-label']
 unique={json.dumps(r['properties'],sort_keys=True,ensure_ascii=False):r for r in observed};first=len(rows)
 for record in unique.values():
  props=record['properties'];expected=props.get('name_en')
  if expected is None:expected=props.get('name')
  for variant,population in rules.items():
   for rule in population:
    zoom,limit=bands[rule['style_name']];selected=props.get('filterrank') is not None and props['filterrank']<=limit
    predicate=QgsExpression(rule['filter_expression']);expression=QgsExpression(rule['label_settings']['field_name'])
    fields=QgsFields()
    for key in sorted(predicate.referencedColumns()|expression.referencedColumns()):fields.append(QgsField(key))
    feature=QgsFeature(fields);feature.setGeometry(QgsGeometry.fromWkt('POINT (0 0)'))
    for key in fields.names():feature.setAttribute(key,props.get(key))
    context=QgsExpressionContext();context.setFields(fields);context.setFeature(feature)
    assert expression.prepare(context) and predicate.prepare(context)
    actual=expression.evaluate(context);actual=None if actual==NULL else actual
    actual_selected=predicate.evaluate(context)==1
    assert not expression.hasEvalError() and not predicate.hasEvalError()
    assert actual_selected==selected
    if variant=='after':assert actual==expected
    rows.append({'camera':path.parent.name,'variant':variant,'rule':rule['style_name'],'band_representative_zoom':zoom,'source_id':record.get('id'),
     'properties':props,'source_selected':selected,'native_selected':actual_selected,'source_text':expected,'native_text':actual,'matches':actual==expected})
 summary.append({'camera':path.parent.name,'observed_records':len(observed),'distinct_property_sets':len(unique),
  'before_mismatches':sum(not r['matches'] for r in rows[first:] if r['variant']=='before'),
  'after_mismatches':sum(not r['matches'] for r in rows[first:] if r['variant']=='after')})
(P/f'poi-properties-qgis{v}.json').write_text(json.dumps({'scope':__doc__,'summary':summary,'evaluations':rows},ensure_ascii=False,indent=2)+'\n')
print(v,'property_sets',sum(r['distinct_property_sets'] for r in summary),'before_mismatches',sum(r['before_mismatches'] for r in summary),'after_mismatches',sum(r['after_mismatches'] for r in summary))
