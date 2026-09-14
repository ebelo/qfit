"""Offline QGIS scale decomposition; no network or secret access."""
import json, math, os, sys
from dataclasses import replace
from pathlib import Path
for parent in Path(__file__).resolve().parents:
 if (parent/'validation/mapbox_outdoors_comparison.py').is_file():
  sys.path.insert(0,str(parent.parent)); break
from qfit.validation.mapbox_outdoors_comparison import LIGHT_CAMERAS, camera_extent_web_mercator, WEB_MERCATOR_HALF_WORLD
from qgis.core import QgsApplication, QgsCoordinateReferenceSystem, QgsMapSettings, QgsRectangle, QgsVectorTileMatrixSet, Qgis, QgsExpression, QgsExpressionContext, QgsExpressionContextUtils
from qgis.PyQt.QtCore import QSize, QT_VERSION_STR
app=QgsApplication([],False); app.initQgis()
matrix=QgsVectorTileMatrixSet.fromWebMercator(0,14)
cameras=dict(LIGHT_CAMERAS)
for city,key in [('geneva','geneva-urban-z14-light'),('bern','bern-urban-z12-light')]:
 for z in (12.9,13.,13.1,13.9,14.,14.1):
  name=f'{city}-z{z:g}-light';cameras[name]=replace(LIGHT_CAMERAS[key],name=name,zoom=z)
rows=[]
expression=QgsExpression('ln(40075016.685578488 / (512 * (0.0254 / 96) * @map_scale)) / ln(2)')
assert not expression.hasParserError()
for camera in cameras.values():
 for dpi in (90,96,100,144,192,300):
  s=QgsMapSettings();s.setDestinationCrs(QgsCoordinateReferenceSystem('EPSG:3857'));s.setExtent(QgsRectangle(*camera_extent_web_mercator(camera)));s.setOutputSize(QSize(camera.width,camera.height));s.setOutputDpi(dpi)
  mpp=s.mapUnitsPerPixel();geometric=math.log2(WEB_MERCATOR_HALF_WORLD*2/512/mpp)
  native=matrix.scaleToZoom(s.scale())
  tile_scale=matrix.calculateTileScaleForMap(s.scale(),s.destinationCrs(),s.visibleExtent(),s.outputSize(),s.outputDpi())
  actual_native=matrix.scaleToZoom(tile_scale)
  scale_logarithmic=math.log2(matrix.tileMatrix(0).scale()/2/s.scale())
  nominal_pixel_m=(matrix.tileMatrix(0).extent().width()/256)/matrix.tileMatrix(0).scale()
  physical_factor=dpi*nominal_pixel_m/.0254
  predicted_scale=s.mapUnitsPerPixel()*dpi/.0254
  reconstructed=scale_logarithmic+math.log2(physical_factor)
  context=QgsExpressionContext();context.appendScope(QgsExpressionContextUtils.mapSettingsScope(s))
  physical_zoom=expression.evaluate(context);assert not expression.hasEvalError()
  rows.append(dict(canonical96_style_zoom=physical_zoom,camera=camera.name,requested_zoom=camera.zoom,dpi=s.outputDpi(),mpp=mpp,geometric_zoom=geometric,map_scale=s.scale(),raw_map_scale_matrix_zoom_not_renderer=native,tile_render_scale=tile_scale,renderer_native_zoom=actual_native,renderer_integer_render_zoom=matrix.scaleToZoomLevel(tile_scale,False),renderer_integer_fetch_zoom=matrix.scaleToZoomLevel(tile_scale,True),logarithmic_matrix_zoom=scale_logarithmic,physical_factor=physical_factor,linear_interpolation_residual=native-scale_logarithmic,reconstructed_geometric_zoom=reconstructed,scale_formula_error=s.scale()-predicted_scale))
result=dict(expression_scope='Explicit constructed QgsExpressionContextUtils.mapSettingsScope, not a renderer-variable trace',canonical96_expression=expression.expression(),qgis_version=Qgis.QGIS_VERSION,qgis_dev_version=getattr(Qgis,'QGIS_DEV_VERSION',None),qt_version=QT_VERSION_STR,matrix_zero_scale=matrix.tileMatrix(0).scale(),matrix_zero_extent_width=matrix.tileMatrix(0).extent().width(),nominal_matrix_pixel_m=nominal_pixel_m,rows=rows)
Path(sys.argv[1]).write_text(json.dumps(result,indent=2)+'\n')
print(Qgis.QGIS_VERSION,len(rows),'cells','max-geometric-error',max(abs(r['geometric_zoom']-r['requested_zoom']) for r in rows),'max-reconstructed-error',max(abs(r['reconstructed_geometric_zoom']-r['requested_zoom']) for r in rows),flush=True)
os._exit(0)
