"""Final validation for line-based atlas native profile behavior."""

from __future__ import annotations

import os
import sqlite3

from validation.scenario_env import (  # pragma: no cover
    ensure_repo_import_path,
    resolve_artifacts_dir,
    resolve_reference_artifact,
    resolve_source_gpkg,
)


def _max_distance_for_activity(source_gpkg, activity_id: str) -> float:  # pragma: no cover
    connection = sqlite3.connect(f"file:{source_gpkg}?mode=ro", uri=True)
    try:
        row = connection.execute(
            "SELECT MAX(distance_m) FROM atlas_profile_samples WHERE source_activity_id = ?",
            (activity_id,),
        ).fetchone()
    finally:
        connection.close()
    return float(row[0])


def main() -> int:  # pragma: no cover
    ensure_repo_import_path()
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from qgis.core import QgsApplication

    app = QgsApplication([], False)
    app.initQgis()

    from qgis.core import (
        QgsCoordinateReferenceSystem,
        QgsLayoutExporter,
        QgsLayoutItemElevationProfile,
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

    activity_id = "17248394490"
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
    tracks_layer.setSubsetString(f'"source_activity_id" = \'{activity_id}\'')
    symbol = QgsLineSymbol.createSimple({"color": "0,180,200", "width": "1.5"})
    tracks_layer.setRenderer(QgsSingleSymbolRenderer(symbol))
    z_track_layer = QgsVectorLayer(str(coverage_gpkg), "z tracks", "ogr")

    project.addMapLayer(tracks_layer)
    project.addMapLayer(z_track_layer)
    project.addMapLayer(atlas_layer)

    for feature in atlas_layer.getFeatures():
        curve = feature.geometry().constGet().clone()
        cx_val = feature.attribute("center_x_3857")
        cy_val = feature.attribute("center_y_3857")
        ew_val = feature.attribute("extent_width_m")
        eh_val = feature.attribute("extent_height_m")
        break
    else:
        raise RuntimeError(f"No atlas features found in {coverage_gpkg}")

    half_width, half_height = float(ew_val) / 2.0, float(eh_val) / 2.0
    map_extent = QgsRectangle(
        float(cx_val) - half_width,
        float(cy_val) - half_height,
        float(cx_val) + half_width,
        float(cy_val) + half_height,
    )

    image_settings = QgsLayoutExporter.ImageExportSettings()
    image_settings.dpi = 150

    layout_a = QgsPrintLayout(project)
    layout_a.initializeDefaults()
    page_collection = layout_a.pageCollection()
    if page_collection.pageCount() > 0:
        page_collection.page(0).setPageSize(
            QgsLayoutSize(PAGE_WIDTH_MM, PAGE_HEIGHT_MM, QgsUnitTypes.LayoutMillimeters)
        )

    atlas_a = layout_a.atlas()
    atlas_a.setCoverageLayer(atlas_layer)
    atlas_a.setEnabled(True)

    map_a = QgsLayoutItemMap(layout_a)
    map_a.setLayers([tracks_layer])
    map_a.setKeepLayerSet(True)
    map_a.attemptMove(QgsLayoutPoint(MAP_X, MAP_Y, QgsUnitTypes.LayoutMillimeters))
    map_a.attemptResize(QgsLayoutSize(MAP_W, MAP_H, QgsUnitTypes.LayoutMillimeters))
    map_a.setCrs(crs)
    layout_a.addLayoutItem(map_a)

    profile_a = QgsLayoutItemElevationProfile(layout_a)
    profile_a.setId("qfit_profile_chart")
    profile_a.attemptMove(QgsLayoutPoint(PROFILE_X, PROFILE_CHART_Y, QgsUnitTypes.LayoutMillimeters))
    profile_a.attemptResize(QgsLayoutSize(PROFILE_W, PROFILE_CHART_H, QgsUnitTypes.LayoutMillimeters))
    profile_a.setLayers([z_track_layer])
    profile_a.setCrs(crs)
    profile_a.setTolerance(200.0)
    profile_a.setAtlasDriven(True)
    layout_a.addLayoutItem(profile_a)

    label_a = QgsLayoutItemLabel(layout_a)
    label_a.setText("A) QgsLayoutItemElevationProfile — atlas-driven=True")
    label_a.attemptMove(QgsLayoutPoint(MARGIN_MM, 4, QgsUnitTypes.LayoutMillimeters))
    label_a.attemptResize(QgsLayoutSize(180, 8, QgsUnitTypes.LayoutMillimeters))
    layout_a.addLayoutItem(label_a)

    atlas_a.beginRender()
    atlas_a.updateFeatures()
    atlas_a.first()
    map_a.setExtent(map_extent)
    map_a.refresh()
    exporter_a = QgsLayoutExporter(layout_a)
    exporter_a.exportToImage(
        str(artifacts_dir / "FINAL-A-layout-item-atlas-driven.png"),
        image_settings,
    )
    atlas_a.endRender()

    request = QgsProfileRequest(curve)
    request.setCrs(crs)
    request.setTolerance(200.0)
    renderer = QgsProfilePlotRenderer([z_track_layer], request)
    renderer.startGeneration()
    renderer.waitForFinished()
    z_range = renderer.zRange()
    max_distance = _max_distance_for_activity(source_gpkg, activity_id)
    profile_img = renderer.renderToImage(
        1200,
        300,
        0,
        max_distance,
        z_range.lower() - 5,
        z_range.upper() + 5,
    )
    profile_image_path = artifacts_dir / "FINAL-B-renderer-profile-image.png"
    profile_img.save(str(profile_image_path))

    layout_c = QgsPrintLayout(project)
    layout_c.initializeDefaults()
    page_collection_c = layout_c.pageCollection()
    if page_collection_c.pageCount() > 0:
        page_collection_c.page(0).setPageSize(
            QgsLayoutSize(PAGE_WIDTH_MM, PAGE_HEIGHT_MM, QgsUnitTypes.LayoutMillimeters)
        )

    map_c = QgsLayoutItemMap(layout_c)
    map_c.setLayers([tracks_layer])
    map_c.setKeepLayerSet(True)
    map_c.attemptMove(QgsLayoutPoint(MAP_X, MAP_Y, QgsUnitTypes.LayoutMillimeters))
    map_c.attemptResize(QgsLayoutSize(MAP_W, MAP_H, QgsUnitTypes.LayoutMillimeters))
    map_c.setCrs(crs)
    map_c.setExtent(map_extent)
    layout_c.addLayoutItem(map_c)

    picture_c = QgsLayoutItemPicture(layout_c)
    picture_c.setId("qfit_profile_chart")
    picture_c.attemptMove(QgsLayoutPoint(PROFILE_X, PROFILE_CHART_Y, QgsUnitTypes.LayoutMillimeters))
    picture_c.attemptResize(QgsLayoutSize(PROFILE_W, PROFILE_CHART_H, QgsUnitTypes.LayoutMillimeters))
    picture_c.setResizeMode(QgsLayoutItemPicture.Zoom)
    picture_c.setPicturePath(str(profile_image_path))
    layout_c.addLayoutItem(picture_c)

    label_c = QgsLayoutItemLabel(layout_c)
    label_c.setText("C) Map + QgsProfilePlotRenderer image (workaround)")
    label_c.attemptMove(QgsLayoutPoint(MARGIN_MM, 4, QgsUnitTypes.LayoutMillimeters))
    label_c.attemptResize(QgsLayoutSize(180, 8, QgsUnitTypes.LayoutMillimeters))
    layout_c.addLayoutItem(label_c)

    exporter_c = QgsLayoutExporter(layout_c)
    exporter_c.exportToImage(
        str(artifacts_dir / "FINAL-C-composite-renderer-profile.png"),
        image_settings,
    )
    pdf_settings = QgsLayoutExporter.PdfExportSettings()
    pdf_settings.dpi = 150
    exporter_c.exportToPdf(
        str(artifacts_dir / "FINAL-C-composite-renderer-profile.pdf"),
        pdf_settings,
    )

    app.exitQgis()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
