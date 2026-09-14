"""Replay public source properties through qfit's real native boundary predicates."""
import argparse, hashlib, itertools, json, sys
from pathlib import Path
from unittest.mock import MagicMock

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--repo',type=Path,required=True);ap.add_argument('--evidence',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
    sys.path.insert(0,str(a.repo.parent))
    from qgis.core import Qgis,QgsApplication,QgsExpression,QgsExpressionContext,QgsFeature,QgsField,QgsFields,QgsSymbolLayer,QgsExpressionContextScope
    from qgis.PyQt.QtCore import QVariant
    from qfit.mapbox_config import simplify_mapbox_style_expressions
    from qfit.visualization.infrastructure.background_map_service import BackgroundMapService
    from qfit.validation.mapbox_outdoors_runtime import qgis_runtime_snapshot
    app=QgsApplication([],False);app.initQgis()
    source=json.loads((a.evidence/'source.json').read_text());converted=simplify_mapbox_style_expressions(source)
    layer=MagicMock();service=BackgroundMapService();service._apply_mapbox_gl_style(layer,converted,source_style_definition=source)
    rules=[r for r in layer.setRenderer.call_args.args[0].styles() if r.styleName().startswith('admin-')]
    contracts={'admin-1-boundary-bg':(1,None),'admin-0-boundary-bg':(0,None),'admin-1-boundary':(1,None),'admin-0-boundary':(0,'false'),'admin-0-boundary-disputed':(0,'true')}
    assert [r.styleName() for r in rules]==list(contracts)
    fields=QgsFields();fields.append(QgsField('admin_level',QVariant.Int))
    for name in ('disputed','maritime','worldview'):fields.append(QgsField(name))
    context=QgsExpressionContext();context.setFields(fields)
    rows=[]
    for file in sorted((a.evidence/'reference').glob('*/mapbox.png.features.json')):
        data=json.loads(file.read_text()); tuples=sorted({tuple(f['properties'].get(k) for k in ('admin_level','disputed','maritime','worldview')) for f in data['source_features']},key=repr)
        for values in tuples:
            feature=QgsFeature(fields);feature.setAttributes(list(values));context.setFeature(feature)
            level,disputed,maritime,worldview=values;observed={}
            for rule in rules:
                required_level,required_dispute=contracts[rule.styleName()]
                expected=level==required_level and maritime=='false' and worldview in ('all','US') and (required_dispute is None or disputed==required_dispute)
                expr=QgsExpression(rule.filterExpression());actual=expr.evaluate(context)==1
                assert not expr.hasEvalError();assert actual==expected,(file.parent.name,values,rule.styleName())
                observed[rule.styleName()]=actual
            rows.append({'camera':file.parent.name,'properties':dict(zip(('admin_level','disputed','maritime','worldview'),values)),'eligible_owners':observed})
    inventory=[]
    for rule in rules:
        symbol=rule.symbol();stroke=symbol.symbolLayer(0);widthprop=stroke.dataDefinedProperties().property(QgsSymbolLayer.PropertyStrokeWidth)
        widths={}
        for zoom in (3,6.9,7,7.1,8,12):
            ctx=QgsExpressionContext();scope=QgsExpressionContextScope();scope.setVariable('vector_tile_zoom',zoom);ctx.appendScope(scope)
            widths[str(zoom)]=QgsExpression(widthprop.asExpression()).evaluate(ctx) if widthprop.isActive() else stroke.width()
        inventory.append({'owner':rule.styleName(),'filter':rule.filterExpression(),'minzoom':rule.minZoomLevel(),'maxzoom':rule.maxZoomLevel(),'symbol_opacity':symbol.opacity(),'properties':stroke.properties(),'width_mm_by_native_zoom':widths,'width_expression':widthprop.asExpression() if widthprop.isActive() else None})
    result={'runtime':qgis_runtime_snapshot(Qgis),'rows':rows,'native_boundary_inventory':inventory,'preprocessed_owners':[x for x in converted['layers'] if x['id'].startswith('admin-')],'source_sha256':hashlib.sha256((a.evidence/'source.json').read_bytes()).hexdigest(),'scope':'Replay of distinct properties from browser loaded source-tile queries; not a QGIS decoded-feature or request trace. No image is rendered.'}
    a.output.write_text(json.dumps(result,indent=2)+'\n');print('verified',len(rows)*5,'source-property/owner combinations',flush=True)
    import os;os._exit(0)
if __name__=='__main__':main()
