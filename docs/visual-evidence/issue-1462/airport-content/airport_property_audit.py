"""Replay observed airport properties through exact native content/filter snapshots.

Run offline in QGIS: airport_property_audit.py EVIDENCE QGIS_MAJOR.
Rendered features and loaded source-tile features are separate populations;
neither is a native-decoder/request trace or a count of unique visible airports.
"""
import json,sys
from pathlib import Path
from qgis.core import NULL,QgsExpression,QgsExpressionContext,QgsFeature,QgsField,QgsFields,QgsGeometry
P=Path(sys.argv[1]);v=sys.argv[2]
source=json.loads((P/'source.json').read_text());owner=next(r for r in source['layers'] if r['id']=='airport-label')
coalesce=['coalesce',['get','name_en'],['get','name']]
assert owner['layout']['text-field']==['step',['get','sizerank'],['case',['has','ref'],['concat',['get','ref'],' -\n',coalesce],coalesce],15,['get','ref']]
allowed=['military','civil','disputed_military','disputed_civil']
assert owner['filter']==['match',['get','class'],allowed,['match',['get','worldview'],['all','US'],True,False],False]
rules={}
for variant in ('before','after'):
 inventory=json.loads((P/f'audit{v}-{variant}/labels.json').read_text())
 matches=[r for r in inventory if r['style_name']=='airport-label'];assert len(matches)==1
 rules[variant]=matches[0]
rows=[];summary=[]
paths=list((P/'reference-mercator').glob('*/mapbox.png.features.json'))
paths+=list((P/'reference-features-mercator').glob('*/mapbox.png.features.json'))
for path in sorted(paths):
 doc=json.loads(path.read_text());population='loaded-source' if path.parent.parent.name=='reference-features-mercator' else 'rendered'
 observed=doc['source_features'] if population=='loaded-source' else [r for r in doc['features'] if r['owner']=='airport-label']
 unique={json.dumps(r['properties'],sort_keys=True,ensure_ascii=False):r for r in observed}
 first=len(rows)
 for record in unique.values():
  props=record['properties'];rank=props.get('sizerank')
  assert isinstance(rank,(int,float)) and not isinstance(rank,bool)
  assert 'ref' not in props or isinstance(props['ref'],str)
  name=props.get('name_en')
  if name is None:name=props.get('name')
  expected=props.get('ref') if rank>=15 else (props['ref']+' -\n'+(name or '') if 'ref' in props else name)
  selected=props.get('class') in allowed and props.get('worldview') in ('all','US')
  for variant,rule in rules.items():
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
   rows.append({'camera':path.parent.name,'population':population,'variant':variant,'source_id':record.get('id'),'geometry':record.get('geometry'),
    'properties':props,'source_selected':selected,'native_selected':actual_selected,'source_text':expected,'native_text':actual,'matches':actual==expected})
 summary.append({'camera':path.parent.name,'population':population,'observed_records':len(observed),'distinct_property_sets':len(unique),
  'before_mismatches':sum(not r['matches'] for r in rows[first:] if r['variant']=='before'),
  'after_mismatches':sum(not r['matches'] for r in rows[first:] if r['variant']=='after')})
(P/f'airport-properties-qgis{v}.json').write_text(json.dumps({'scope':__doc__,'summary':summary,'evaluations':rows},ensure_ascii=False,indent=2)+'\n')
print(v,summary)
