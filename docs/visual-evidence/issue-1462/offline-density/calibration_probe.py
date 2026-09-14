"""Rejected diagnostic: layer-local Esri method and 96-DPI matrix scaling."""
import argparse,json
from pathlib import Path
from qgis.core import QgsApplication,Qgis,QgsExpression,QgsExpressionFunction,QgsRectangle
import vector_tile_density_probe as probe
parser=argparse.ArgumentParser();parser.add_argument('--output-dir',type=Path,required=True);parser.add_argument('--fixture-mbtiles',type=Path,required=True);args=parser.parse_args()
app=QgsApplication([],False);app.initQgis()
args.output_dir.mkdir(parents=True,exist_ok=False)
layer,original_extent=probe._fixture(args.output_dir,args.fixture_mbtiles)
matrix=layer.tileMatrixSet();matrix.setScaleToTileZoomMethod(Qgis.ScaleToTileZoomLevelMethod.Esri)
for z in range(matrix.minimumZoom(),matrix.maximumZoom()+1):
 tile=matrix.tileMatrix(z);tile.setScale(tile.scale()*(96*0.00028/0.0254)/2);matrix.addMatrix(tile)
trace=set()
class Trace(QgsExpressionFunction):
 def __init__(self):super().__init__('qfitDensityTrace',4,'qfit validation')
 def func(self,values,context,parent,node):trace.add(tuple(float(x) for x in values[:3]));return values[3]
function=Trace();assert QgsExpression.registerFunction(function)
records=[]
for zoom in (12.25,12.9,13,13.1):
 extent=QgsRectangle(original_extent);extent.scale(2**(12.25-zoom))
 for dpi in (96,150,192):
  for kind,export in [('png',probe._export_png),('pdf',probe._export_pdf)]:
   for traced in (False,True):
    probe._renderer(layer,traced)
    for repeat in (0,1):
     trace.clear();name=f'z{zoom}-{kind}-{dpi}-{"trace" if traced else "plain"}-{repeat}.{kind}'
     scale=export(layer,extent,dpi,args.output_dir/name)
     records.append(dict(file=name,source_zoom=zoom,dpi=dpi,kind=kind,traced=traced,repeat=repeat,map_scale=scale,trace=sorted(trace)))
QgsExpression.unregisterFunction('qfitDensityTrace')
(args.output_dir/'report.json').write_text(json.dumps(dict(qgis=Qgis.QGIS_VERSION,qgis_revision=Qgis.QGIS_DEV_VERSION,records=records),indent=2)+'\n')
print('calibration',Qgis.QGIS_VERSION,'completed',len(records),'outputs')
