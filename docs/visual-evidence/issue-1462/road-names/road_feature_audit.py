"""Replay observed source road properties through archived native text/filter rules.

Usage: road_feature_audit.py EVIDENCE QGIS_MAJOR
Run in an offline QGIS process. This proves content and property eligibility,
not identical native tile decoding, collision survival, or geometry association.
"""
import json,sys
from pathlib import Path
from qgis.core import NULL,QgsExpression,QgsExpressionContext,QgsFeature,QgsField,QgsFields,QgsGeometry
root=Path(sys.argv[1]);version=sys.argv[2]
source=json.loads((root/'source.json').read_text())
owner=next(r for r in source['layers'] if r['id']=='road-label-simple')
allowed=['motorway','trunk','primary','secondary','tertiary','street','street_limited']
assert owner['filter']==['all',['has','name'],['match',['get','class'],allowed,True,False]]
assert owner['layout']['text-field']==['coalesce',['get','name_en'],['get','name']]
inventories={v:json.loads((root/f'audit{version}-{v}/labels.json').read_text()) for v in ('before','after')}
rows=[];summary=[]
for path in sorted((root/'reference-mercator').glob('*/mapbox.png.features.json')):
    camera=path.parent.name
    observed=[r for r in json.loads(path.read_text())['features'] if r['owner']==owner['id']]
    # Preserve each distinct observed property set; repeated geometry fragments
    # do not inflate the count of source name/class cases.
    unique={json.dumps(r['properties'],sort_keys=True,ensure_ascii=False):r['properties'] for r in observed}
    first=len(rows)
    for properties in unique.values():
        expected_name=properties.get('name_en')
        if expected_name is None:expected_name=properties.get('name')
        expected_selected='name' in properties and properties.get('class') in allowed
        assert expected_selected
        for variant,inventory in inventories.items():
            rules=[r for r in inventory if r['layer_name']=='road']
            assert [r['style_name'] for r in rules]==['road-label-simple','road-label-simple-z12-to-z15']
            for rule in rules:
                predicate=QgsExpression(rule['filter_expression']);text=QgsExpression(rule['label_settings']['field_name'])
                fields=QgsFields()
                for key in sorted(predicate.referencedColumns() | text.referencedColumns()):fields.append(QgsField(key))
                feature=QgsFeature(fields);feature.setGeometry(QgsGeometry.fromWkt('LINESTRING (0 0,1 1)'))
                for key in fields.names():feature.setAttribute(key,properties.get(key))
                context=QgsExpressionContext();context.setFields(fields);context.setFeature(feature)
                assert predicate.prepare(context) and text.prepare(context)
                selected=predicate.evaluate(context)==1;actual=text.evaluate(context)
                assert not predicate.hasEvalError() and not text.hasEvalError()
                if actual==NULL:actual=None
                assert selected==expected_selected
                if variant=='after':assert actual==expected_name
                rows.append({'camera':camera,'properties':properties,'variant':variant,'rule':rule['style_name'],
                             'source_property_eligible':expected_selected,'native_property_eligible':selected,
                             'source_text':expected_name,'native_text':actual,'content_matches':actual==expected_name})
    summary.append({'camera':camera,'source_rendered_fragments':len(observed),'distinct_properties':len(unique),
                    'before_content_mismatches':sum(not r['content_matches'] for r in rows[first:] if r['variant']=='before'),
                    'after_content_mismatches':sum(not r['content_matches'] for r in rows[first:] if r['variant']=='after')})
(root/f'road-features-qgis{version}.json').write_text(json.dumps({'scope':__doc__,'summary':summary,'evaluations':rows},ensure_ascii=False,indent=2)+'\n')
print('QGIS',version,'observed camera/property cases',sum(r['distinct_properties'] for r in summary),
      'before mismatches',sum(r['before_content_mismatches'] for r in summary),'after0; property predicate mismatches0')
