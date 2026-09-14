import json,sys
from pathlib import Path
from qgis.core import QgsApplication,Qgis,QgsVectorTileLayer,QgsVectorTileMatrixSet,QgsTileMatrix,QgsMapSettings,QgsRectangle,QgsCoordinateReferenceSystem
from qgis.PyQt.QtCore import QSize
app=QgsApplication([],False);app.initQgis()
layer=QgsVectorTileLayer('type=mbtiles&url='+str(Path(sys.argv[1]).resolve()),'synthetic')
matrix=layer.tileMatrixSet();before=matrix.scaleToTileZoomMethod()
matrix.setScaleToTileZoomMethod(Qgis.ScaleToTileZoomLevelMethod.Esri)
for z in range(matrix.minimumZoom(),matrix.maximumZoom()+1):
 t=matrix.tileMatrix(z);t.setScale(t.scale()*(96*0.00028/0.0254)/2);matrix.addMatrix(t)
rows=[]
for source_zoom in (11.9,12,12.1,12.25,12.9,13,13.1,13.9,14,14.1):
 for dpi in (96,150,192):
  settings=QgsMapSettings();settings.setDestinationCrs(QgsCoordinateReferenceSystem('EPSG:3857'));settings.setOutputDpi(dpi);settings.setOutputSize(QSize(round(640*dpi/96),round(480*dpi/96)))
  res=40075016.6855784/(512*2**source_zoom);settings.setExtent(QgsRectangle(829000,5930000,829000+640*res,5930000+480*res))
  m=layer.tileMatrixSet();scale=m.calculateTileScaleForMap(settings.scale(),settings.destinationCrs(),settings.visibleExtent(),settings.outputSize(),settings.outputDpi())
  rows.append(dict(source_zoom=source_zoom,dpi=dpi,native_zoom=m.scaleToZoom(scale),render_zoom=m.scaleToZoomLevel(scale,False)))
print(json.dumps(dict(qgis=Qgis.QGIS_VERSION,before=str(before),after=str(layer.tileMatrixSet().scaleToTileZoomMethod()),rows=rows),indent=2))
