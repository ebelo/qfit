"""Inspect layer-local matrix mutation, clone and project persistence offline."""
import argparse,json
from pathlib import Path
from qgis.core import QgsApplication,Qgis,QgsVectorTileLayer,QgsProject
parser=argparse.ArgumentParser();parser.add_argument('--fixture-mbtiles',required=True,type=Path);parser.add_argument('--project',required=True,type=Path);args=parser.parse_args()
app=QgsApplication([],False);app.initQgis()
layer=QgsVectorTileLayer('type=mbtiles&url='+str(args.fixture_mbtiles.resolve()),'synthetic')
assert layer.isValid()
before=layer.tileMatrixSet().scaleToTileZoomMethod();matrix=layer.tileMatrixSet()
matrix.setScaleToTileZoomMethod(Qgis.ScaleToTileZoomLevelMethod.Esri)
for z in range(matrix.minimumZoom(),matrix.maximumZoom()+1):
 tile=matrix.tileMatrix(z);tile.setScale(tile.scale()*(96*0.00028/0.0254)/2);matrix.addMatrix(tile)
def record(item):
 m=item.tileMatrixSet();return dict(valid=item.isValid(),method=str(m.scaleToTileZoomMethod()),matrix12_scale=m.tileMatrix(12).scale())
clone=layer.clone();project=QgsProject();project.addMapLayer(layer);assert project.write(str(args.project))
reloaded=QgsProject();assert reloaded.read(str(args.project));restored=next(iter(reloaded.mapLayers().values()))
print(json.dumps(dict(qgis=Qgis.QGIS_VERSION,qgis_revision=Qgis.QGIS_DEV_VERSION,has_tile_matrix_setter=hasattr(layer,'setTileMatrixSet'),initial_method=str(before),mutated=record(layer),clone=record(clone),project_restored=record(restored))))
