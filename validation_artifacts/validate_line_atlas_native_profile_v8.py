"""Validate QgsProfilePlotRenderer.renderToImage() workaround (v8)."""

from __future__ import annotations

import os

from validation.scenario_env import (  # pragma: no cover
    ensure_repo_import_path,
    resolve_artifacts_dir,
    resolve_reference_artifact,
    resolve_source_gpkg,
)


def main() -> int:  # pragma: no cover
    ensure_repo_import_path()
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from qgis.core import QgsApplication

    app = QgsApplication([], False)
    app.initQgis()

    from qgis.core import (
        QgsCoordinateReferenceSystem,
        QgsLayoutExporter,
        QgsLayoutItemLabel,
        QgsLayoutItemMap,
        QgsLayoutItemPicture,
        QgsLayoutPoint,
        QgsLayoutSize,
        QgsLineSymbol,
        QgsPrintLayout,
        QgsProfilePlotRenderer,
        QgsProfileRequest,
        QgsProject,
        QgsRectangle,
        QgsSingleSymbolRenderer,
        QgsUnitTypes,
        QgsVectorLayer,
    )
    from qfit.atlas.export_task import (
        MAP_H,
        MAP_W,
        MAP_X,
        MAP_Y,
        MARGIN_MM,
        PAGE_HEIGHT_MM,
        PAGE_WIDTH_MM,
        PROFILE_CHART_H,
        PROFILE_CHART_Y,
        PROFILE_W,
        PROFILE_X,
    )

    artifacts_dir = resolve_artifacts_dir()
    source_gpkg = resolve_source_gpkg()
    coverage_gpkg = resolve_reference_artifact("line-atlas-coverage-17248394490.gpkg")

    crs = QgsCoordinateReferenceSystem("EPSG:3857")
    project = QgsProject.instance()
    project.setCrs(crs)

    atlas_layer = QgsVectorLayer(str(coverage_gpkg), "line atlas pages", "ogr")
    tracks_layer = QgsVectorLayer(
        f"{source_gpkg}|layername=activity_tracks", "qfit activities", "ogr"
    )
    tracks_layer.setSubsetString('"source_activity_id" = \'17248394490\'')
    symbol = QgsLineSymbol.createSimple({"color": "0,180,200", "width": "1.5"})
    tracks_layer.setRenderer(QgsSingleSymbolRenderer(symbol))
    z_track_layer = QgsVectorLayer(str(coverage_gpkg), "z tracks", "ogr")

    project.addMapLayer(tracks_layer)
    project.addMapLayer(z_track_layer)
    project.addMapLayer(atlas_layer)

    for feature in atlas_layer.getFeatures():
        geometry = feature.geometry()
        curve = geometry.constGet().clone()
        cx_val = feature.attribute("center_x_3857")
        cy_val = feature.attribute("center_y_3857")
        ew_val = feature.attribute("extent_width_m")
        eh_val = feature.attribute("extent_height_m")
        break
    else:
        raise RuntimeError(f"No atlas features found in {coverage_gpkg}")

    request = QgsProfileRequest(curve)
    request.setCrs(crs)
    request.setTolerance(200.0)

    renderer = QgsProfilePlotRenderer([z_track_layer], request)
    renderer.startGeneration()
    renderer.waitForFinished()
    z_range = renderer.zRange()
    curve_length = curve.length()
    profile_img = renderer.renderToImage(
        800,
        200,
        0,
        curve_length,
        z_range.lower(),
        z_range.upper(),
    )

    profile_png_path = artifacts_dir / "native-renderer-profile-17248394490.png"
    profile_img.save(str(profile_png_path))

    layout = QgsPrintLayout(project)
    layout.initializeDefaults()
    page_collection = layout.pageCollection()
    if page_collection.pageCount() > 0:
        page_collection.page(0).setPageSize(
            QgsLayoutSize(PAGE_WIDTH_MM, PAGE_HEIGHT_MM, QgsUnitTypes.LayoutMillimeters)
        )

    map_item = QgsLayoutItemMap(layout)
    map_item.setLayers([tracks_layer])
    map_item.setKeepLayerSet(True)
    map_item.attemptMove(QgsLayoutPoint(MAP_X, MAP_Y, QgsUnitTypes.LayoutMillimeters))
    map_item.attemptResize(QgsLayoutSize(MAP_W, MAP_H, QgsUnitTypes.LayoutMillimeters))
    map_item.setCrs(crs)
    layout.addLayoutItem(map_item)

    half_width, half_height = float(ew_val) / 2.0, float(eh_val) / 2.0
    map_item.setExtent(
        QgsRectangle(
            float(cx_val) - half_width,
            float(cy_val) - half_height,
            float(cx_val) + half_width,
            float(cy_val) + half_height,
        )
    )

    picture_item = QgsLayoutItemPicture(layout)
    picture_item.setId("qfit_profile_chart")
    picture_item.attemptMove(
        QgsLayoutPoint(PROFILE_X, PROFILE_CHART_Y, QgsUnitTypes.LayoutMillimeters)
    )
    picture_item.attemptResize(
        QgsLayoutSize(PROFILE_W, PROFILE_CHART_H, QgsUnitTypes.LayoutMillimeters)
    )
    picture_item.setResizeMode(QgsLayoutItemPicture.Zoom)
    picture_item.setPicturePath(str(profile_png_path))
    layout.addLayoutItem(picture_item)

    label = QgsLayoutItemLabel(layout)
    label.setText("Morning Nordic Ski — Native QgsProfilePlotRenderer")
    label.attemptMove(QgsLayoutPoint(MARGIN_MM, MARGIN_MM, QgsUnitTypes.LayoutMillimeters))
    label.attemptResize(QgsLayoutSize(150, 10, QgsUnitTypes.LayoutMillimeters))
    layout.addLayoutItem(label)

    exporter = QgsLayoutExporter(layout)
    image_settings = QgsLayoutExporter.ImageExportSettings()
    image_settings.dpi = 150
    exporter.exportToImage(
        str(artifacts_dir / "line-atlas-native-renderer-page-17248394490.png"),
        image_settings,
    )
    pdf_settings = QgsLayoutExporter.PdfExportSettings()
    pdf_settings.dpi = 150
    exporter.exportToPdf(
        str(artifacts_dir / "line-atlas-native-renderer-17248394490.pdf"),
        pdf_settings,
    )

    app.exitQgis()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
