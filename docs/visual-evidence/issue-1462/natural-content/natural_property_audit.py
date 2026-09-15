"""Offline native replay of distinct rendered-camera natural-feature property sets.

Not unique features, native decoding/fetch parity, collision survival or glyph proof.
Each property set is replayed through both native font bands, without
pretending its source camera zoom is the native renderer zoom.
"""
import json,sys
from pathlib import Path
from qgis.core import NULL,QgsExpression,QgsExpressionContext,QgsFeature,QgsField,QgsFields,QgsGeometry
P=Path(sys.argv[1]);v=sys.argv[2]
source=json.loads((P/'source.json').read_text())
owners={r['id']:r for r in source['layers'] if r['id'] in ('natural-line-label','natural-point-label')}
for owner in owners.values():
 assert owner['layout']['text-field']==['coalesce',['get','name_en'],['get','name']]
 assert owner['layout'].get('text-transform','none')=='none'
rules={}
for variant in ('before','after'):
 inventory=json.loads((P/f'audit{v}-{variant}/labels.json').read_text())
 rules[variant]=[r for r in inventory if r['style_name'].split('-qfit-open-fonts-')[0] in owners]
 assert len(rules[variant])==4
rows=[];summary=[]
for path in sorted((P/'reference-mercator').glob('*/mapbox.png.features.json')):
 observed=[r for r in json.loads(path.read_text())['features'] if r['owner'] in owners]
 unique={r['owner']+json.dumps(r['properties'],sort_keys=True,ensure_ascii=False):r for r in observed};first=len(rows)
 for record in unique.values():
  props=record['properties'];expected=props.get('name_en')
  if expected is None:expected=props.get('name')
  owner=owners[record['owner']];allowed=owner['filter'][1][2]
  geometry_type=record['geometry']['type'];native_geometry='LineString' if 'LineString' in geometry_type else 'Point'
  selected=(props.get('class') in allowed and props.get('worldview') in ('all','US')
            and props.get('filterrank') is not None and props['filterrank']<=1
            and native_geometry==owner['filter'][3][2])
  for variant,population in rules.items():
   for rule in population:
    if rule['style_name'].split('-qfit-open-fonts-')[0]!=record['owner']:continue
    predicate=QgsExpression(rule['filter_expression']);expression=QgsExpression(rule['label_settings']['field_name'])
    fields=QgsFields()
    for key in sorted(predicate.referencedColumns()|expression.referencedColumns()):fields.append(QgsField(key))
    feature=QgsFeature(fields);feature.setGeometry(QgsGeometry.fromWkt('LINESTRING (0 0,1 1,2 0)'))
    for key in fields.names():feature.setAttribute(key,native_geometry if key=='_geom_type' else props.get(key))
    context=QgsExpressionContext();context.setFields(fields);context.setFeature(feature)
    assert expression.prepare(context) and predicate.prepare(context)
    actual=expression.evaluate(context);actual=None if actual==NULL else actual
    actual_selected=predicate.evaluate(context)==1
    assert not expression.hasEvalError() and not predicate.hasEvalError()
    assert actual_selected==selected
    if variant=='after':assert actual==expected
    rows.append({'camera':path.parent.name,'variant':variant,'rule':rule['style_name'],'source_id':record.get('id'),
     'properties':props,'source_geometry_type':geometry_type,'source_selected':selected,'native_selected':actual_selected,
     'source_text':expected,'native_text':actual,'matches':actual==expected})
 summary.append({'camera':path.parent.name,'observed_records':len(observed),'distinct_property_sets':len(unique),
  'before_mismatches':sum(not r['matches'] for r in rows[first:] if r['variant']=='before'),
  'after_mismatches':sum(not r['matches'] for r in rows[first:] if r['variant']=='after')})
(P/f'natural-properties-qgis{v}.json').write_text(json.dumps({'scope':__doc__,'summary':summary,'evaluations':rows},ensure_ascii=False,indent=2)+'\n')
print(v,'property_sets',sum(r['distinct_property_sets'] for r in summary),'before_mismatches',sum(r['before_mismatches'] for r in summary),'after_mismatches',sum(r['after_mismatches'] for r in summary))
