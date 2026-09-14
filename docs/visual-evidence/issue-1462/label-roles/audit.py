"""Audit exact source text contracts against every current native label rule.

This evaluates content, not source/native feature eligibility or glyph shaping.
Run in a font-enabled QGIS process: audit.py REPO SOURCE OUTPUT.
"""
import hashlib,json,sys
from pathlib import Path
from unittest.mock import MagicMock
repo,source_path,out=map(Path,sys.argv[1:]);sys.path.insert(0,str(repo.resolve().parent))
from qgis.core import NULL,QgsApplication,QgsExpression,QgsExpressionContext,QgsFeature,QgsField,QgsFields,QgsGeometry,QgsRenderContext
from qfit.mapbox_config import simplify_mapbox_style_expressions
from qfit.visualization.infrastructure.background_map_service import BackgroundMapService
from qfit.validation.mapbox_outdoors_comparison import qgis_label_styles_snapshot,qgis_runtime_snapshot
app=QgsApplication([],False);app.initQgis()
source=json.loads(source_path.read_text());converted=simplify_mapbox_style_expressions(source)
layer=MagicMock();BackgroundMapService()._apply_mapbox_gl_style(layer,converted,source_style_definition=source)
labeling=layer.setLabeling.call_args.args[0];layer.labeling.return_value=labeling
owners=[x for x in source['layers'] if x.get('type')=='symbol']
cases=[('english',{'name_en':'English name','name':'Nom local'}),('null-english',{'name_en':None,'name':'Genève'}),('missing-english',{'name':'القاهرة'}),('empty-english',{'name_en':'','name':'ירושלים'}),('diacritics',{'name_en':'Zürich — L’Aquila','name':'local'}),('mixed-script',{'name_en':'القاهرة / ירושלים 12','name':'local'}),('english-only',{'name_en':'English only'}),('both-missing',{})]
# Exact recorded source contracts, deliberately not a general GL evaluator.
coalesce=['coalesce',['get','name_en'],['get','name']]
def expected_text(owner,props):
    expr=owner['layout']['text-field'];name=props.get('name_en')
    if name is None:name=props.get('name')
    if owner['id']=='airport-label':
        assert expr==['step',['get','sizerank'],['case',['has','ref'],['concat',['get','ref'],' -\n',coalesce],coalesce],15,['get','ref']]
        value=props.get('ref') if props['sizerank']>=15 else ((str(props['ref'])+' -\n'+(name or '')) if 'ref' in props else name)
    else:
        assert expr==coalesce,(owner['id'],expr);value=name
    transform=owner['layout'].get('text-transform','none')
    assert transform in ('none','uppercase','lowercase')
    if value is not None and transform!='none':value=value.upper() if transform=='uppercase' else value.lower()
    return value
rows=[]
for rule in labeling.styles():
    candidates=[o for o in owners if rule.styleName()==o['id'] or rule.styleName().startswith(o['id']+'-')]
    assert len(candidates)==1,(rule.styleName(),len(candidates));owner=candidates[0];settings=rule.labelSettings()
    assert settings.isExpression
    predicate=QgsExpression(rule.filterExpression());expr=QgsExpression(settings.fieldName)
    requested=sorted(settings.referencedFields(QgsRenderContext()))
    # Content schema is precisely label settings' requests. Predicate evaluation
    # is separate: its extra fields must not hide a missing text-field request.
    fields=QgsFields()
    for name in requested:fields.append(QgsField(name))
    values=[]
    airport=[('small-no-ref',{'sizerank':10}),('small-ref',{'sizerank':10,'ref':'CAI'}),('large-ref',{'sizerank':15,'ref':'JRS'})] if owner['id']=='airport-label' else [('default',{})]
    for case,props0 in cases:
      for airport_case,extra in airport:
        props={**props0,**extra};feature=QgsFeature(fields);feature.setGeometry(QgsGeometry.fromWkt('POINT (0 0)'))
        for name,value in props.items():
          if name in requested:feature.setAttribute(name,value)
        context=QgsExpressionContext();context.setFields(fields);context.setFeature(feature)
        assert expr.prepare(context),(rule.styleName(),expr.evalErrorString())
        actual=expr.evaluate(context);assert not expr.hasEvalError(),expr.evalErrorString();actual=None if actual==NULL else actual
        expected=expected_text(owner,props)
        # Companion rules are assessed only on their own name availability arm.
        eligible=True
        if rule.styleName().endswith('-name-en'):eligible=props.get('name_en') is not None
        elif rule.styleName().endswith('-name'):eligible=props.get('name_en') is None
        values.append({'case':case,'airport_case':airport_case,'properties':props,'companion_arm_eligible':eligible,'source_text':expected,'native_text':actual,'matches':actual==expected})
    rows.append({'owner':owner['id'],'source_layer':owner.get('source-layer'),'source_text':owner['layout']['text-field'],'source_transform':owner['layout'].get('text-transform','none'),'rule':rule.styleName(),'filter':rule.filterExpression(),'native_text':settings.fieldName,'requested_fields':requested,'minzoom':rule.minZoomLevel(),'maxzoom':rule.maxZoomLevel(),'cases':values})
assert {r['owner'] for r in rows}=={o['id'] for o in owners}
summary=[]
for owner in owners:
    group=[r for r in rows if r['owner']==owner['id']];cases2=[c for r in group for c in r['cases'] if c['companion_arm_eligible']]
    failures=sum(not c['matches'] for c in cases2)
    summary.append({'owner':owner['id'],'native_rules':len(group),'eligible_content_cases':len(cases2),'mismatches':failures,'verdict':'OPEN' if failures else 'PASS (scoped content)'})
out.mkdir(parents=True,exist_ok=True)
(out/'audit.json').write_text(json.dumps({'scope':'Text evaluation in requested native schema; companion name arms only; no feature/zoom eligibility, render or shaping certification','source_sha256':hashlib.sha256(source_path.read_bytes()).hexdigest(),'runtime':qgis_runtime_snapshot(__import__('qgis.core',fromlist=['Qgis']).Qgis),'summary':summary,'rules':rows},ensure_ascii=False,indent=2)+'\n')
(out/'labels.json').write_text(json.dumps(qgis_label_styles_snapshot(layer),ensure_ascii=False,indent=2)+'\n')
(out/'processed.json').write_text(json.dumps(converted,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(summary),flush=True)
# QGIS objects remain alive until process teardown, avoiding destructor-order noise.
import os
os._exit(0)
