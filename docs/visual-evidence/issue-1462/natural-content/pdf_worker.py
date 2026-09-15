"""Actual one-map production-setting PDF export hook for natural-feature-content output guardrails."""
import json

def install(camera,folder):
    import qgis.core
    original_job=qgis.core.QgsMapRendererParallelJob
    class ExportJob:
        def __init__(self,settings):
            self.settings=settings;self.inner=original_job(settings)
        def start(self):self.inner.start()
        def waitForFinished(self):
            self.inner.waitForFinished()
            labels = self.inner.takeLabelingResults().allLabels()
            placed = [{'text':label.labelText,'provider_id':label.providerID,
                       'feature_id':label.featureId,'unplaced':label.isUnplaced,
                       'corners':[[point.x(),point.y()] for point in label.cornerPoints]}
                      for label in labels]
            (folder/'placed-labels.json').write_text(json.dumps(placed,ensure_ascii=False,indent=2)+'\n')
            from qgis.core import QgsProject,QgsPrintLayout,QgsLayoutItemMap,QgsLayoutSize,QgsLayoutExporter
            from qfit.atlas.export_task import AtlasExportTask
            project=QgsProject();layout=QgsPrintLayout(project);layout.initializeDefaults()
            width=camera.width*25.4/96;height=camera.height*25.4/96
            layout.pageCollection().pages()[0].setPageSize(QgsLayoutSize(width,height))
            item=QgsLayoutItemMap(layout);layout.addLayoutItem(item)
            item.attemptResize(QgsLayoutSize(width,height));item.setCrs(self.settings.destinationCrs())
            item.setLayers(self.settings.layers());item.setKeepLayerSet(True);item.zoomToExtent(self.settings.visibleExtent())
            exporter=QgsLayoutExporter(layout);settings=AtlasExportTask._build_pdf_export_settings();original_dpi=settings.dpi
            for dpi in (150,):
                for repeated in (False,True):
                    prefix=f'pdf{dpi}'+('-repeat' if repeated else '')
                    settings.dpi=dpi;item.invalidateCache()
                    result=exporter.exportToPdf(str(folder/(prefix+'.pdf')),settings)
                    assert result==QgsLayoutExporter.Success,'PDF export failed'
                    extent=item.extent()
                    (folder/(prefix+'-context.json')).write_text(json.dumps({'dpi':dpi,'production_default_dpi':original_dpi,'force_vector':settings.forceVectorOutput,'rasterize_whole_image':settings.rasterizeWholeImage,'page_mm':[width,height],'map_scale':item.scale(),'extent':[extent.xMinimum(),extent.yMinimum(),extent.xMaximum(),extent.yMaximum()]},indent=2)+'\n')
        def renderedImage(self):return self.inner.renderedImage()
    qgis.core.QgsMapRendererParallelJob=ExportJob
