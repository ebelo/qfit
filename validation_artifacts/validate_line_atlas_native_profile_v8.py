"""Validate QgsProfilePlotRenderer.renderToImage() workaround (v8).

Since QgsLayoutItemElevationProfile doesn't render in headless mode,
test whether we can use the standalone QgsProfilePlotRenderer to generate
a profile image that can be embedded via QgsLayoutItemPicture.
"""

import os
import sys

sys.path.insert(0, "/home/ebelo/.openclaw/workspace")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from qgis.core import QgsApplication
app = QgsApplication([], False)
app.initQgis()

from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsLayoutExporter,
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

ARTIFACTS_DIR = os.environ.get(
    "QFIT_VALIDATION_OUTPUT_DIR",
    "/home/ebelo/.openclaw/workspace/qfit/validation_artifacts",
)
os.makedirs(ARTIFACTS_DIR, exist_ok=True)
SOURCE_GPKG = "/home/ebelo/qfit_activities.gpkg"
OUTPUT_GPKG = os.path.join(ARTIFACTS_DIR, "line-atlas-coverage-17248394490.gpkg")

crs = QgsCoordinateReferenceSystem("EPSG:3857")
proj = QgsProject.instance()
proj.setCrs(crs)

atlas_layer = QgsVectorLayer(OUTPUT_GPKG, "line atlas pages", "ogr")
tracks_layer = QgsVectorLayer(
    f"{SOURCE_GPKG}|layername=activity_tracks", "qfit activities", "ogr",
)
tracks_layer.setSubsetString("\"source_activity_id\" = '17248394490'")
sym = QgsLineSymbol.createSimple({"color": "0,180,200", "width": "1.5"})
tracks_layer.setRenderer(QgsSingleSymbolRenderer(sym))
z_track_layer = QgsVectorLayer(OUTPUT_GPKG, "z tracks", "ogr")

proj.addMapLayer(tracks_layer)
proj.addMapLayer(z_track_layer)
proj.addMapLayer(atlas_layer)

# Get the LineStringZ curve
for f in atlas_layer.getFeatures():
    fg = f.geometry()
    curve = fg.constGet().clone()
    cx_val = f.attribute("center_x_3857")
    cy_val = f.attribute("center_y_3857")
    ew_val = f.attribute("extent_width_m")
    eh_val = f.attribute("extent_height_m")
    break

print(f"Curve: {type(curve).__name__}, {curve.numPoints()} pts, is3D={curve.is3D()}")

# --- Generate profile synchronously ---
print("\n=== Generate profile with QgsProfilePlotRenderer ===")
request = QgsProfileRequest(curve)
request.setCrs(crs)
request.setTolerance(200.0)

renderer = QgsProfilePlotRenderer([z_track_layer], request)
renderer.startGeneration()
renderer.waitForFinished()

z_range = renderer.zRange()
print(f"Z range: [{z_range.lower():.1f}, {z_range.upper():.1f}]")

# --- Render to image ---
print("\n=== Render profile to image ===")

# Check renderToImage signature
try:
    # Try with width, height, distanceMin, distanceMax, zMin, zMax
    width = 800
    height = 200

    # Need the distance range
    # The curve length in CRS units
    curve_length = curve.length()
    print(f"Curve length (CRS units): {curve_length:.1f}")

    # renderToImage expects: width, height, distMin, distMax, zMin, zMax
    profile_img = renderer.renderToImage(
        width, height,
        0, curve_length,
        z_range.lower(), z_range.upper(),
    )
    print(f"Profile image: {profile_img.width()}x{profile_img.height()}, isNull={profile_img.isNull()}")

    # Save as PNG
    profile_png_path = os.path.join(ARTIFACTS_DIR, "native-renderer-profile-17248394490.png")
    saved = profile_img.save(profile_png_path)
    print(f"Saved: {saved}, size: {os.path.getsize(profile_png_path) if os.path.exists(profile_png_path) else 0}")

except TypeError as e:
    print(f"renderToImage failed: {e}")
    # Try alternative signature
    try:
        profile_img = renderer.renderToImage(800, 200)
        print(f"Simple renderToImage: {profile_img.width()}x{profile_img.height()}")
        profile_png_path = os.path.join(ARTIFACTS_DIR, "native-renderer-profile-17248394490.png")
        profile_img.save(profile_png_path)
    except Exception as e2:
        print(f"Also failed: {e2}")
        profile_png_path = None

# --- Build layout with image fallback ---
if profile_png_path and os.path.exists(profile_png_path):
    print("\n=== Build layout with profile image ===")
    from qfit.atlas.export_task import (
        PAGE_WIDTH_MM, PAGE_HEIGHT_MM,
        MAP_X, MAP_Y, MAP_W, MAP_H,
        PROFILE_X, PROFILE_CHART_Y, PROFILE_W, PROFILE_CHART_H,
        MARGIN_MM,
    )

    layout = QgsPrintLayout(proj)
    layout.initializeDefaults()
    pc = layout.pageCollection()
    if pc.pageCount() > 0:
        pc.page(0).setPageSize(QgsLayoutSize(PAGE_WIDTH_MM, PAGE_HEIGHT_MM, QgsUnitTypes.LayoutMillimeters))

    map_item = QgsLayoutItemMap(layout)
    map_item.setLayers([tracks_layer])
    map_item.setKeepLayerSet(True)
    map_item.attemptMove(QgsLayoutPoint(MAP_X, MAP_Y, QgsUnitTypes.LayoutMillimeters))
    map_item.attemptResize(QgsLayoutSize(MAP_W, MAP_H, QgsUnitTypes.LayoutMillimeters))
    map_item.setCrs(crs)
    layout.addLayoutItem(map_item)

    hw, hh = float(ew_val) / 2.0, float(eh_val) / 2.0
    rect = QgsRectangle(float(cx_val) - hw, float(cy_val) - hh,
                        float(cx_val) + hw, float(cy_val) + hh)
    map_item.setExtent(rect)

    # Profile as picture
    pic_item = QgsLayoutItemPicture(layout)
    pic_item.setId("qfit_profile_chart")
    pic_item.attemptMove(QgsLayoutPoint(PROFILE_X, PROFILE_CHART_Y, QgsUnitTypes.LayoutMillimeters))
    pic_item.attemptResize(QgsLayoutSize(PROFILE_W, PROFILE_CHART_H, QgsUnitTypes.LayoutMillimeters))
    pic_item.setResizeMode(QgsLayoutItemPicture.Zoom)
    pic_item.setPicturePath(profile_png_path)
    layout.addLayoutItem(pic_item)

    # Title
    from qgis.core import QgsLayoutItemLabel
    label = QgsLayoutItemLabel(layout)
    label.setText("Morning Nordic Ski — Native QgsProfilePlotRenderer")
    label.attemptMove(QgsLayoutPoint(MARGIN_MM, MARGIN_MM, QgsUnitTypes.LayoutMillimeters))
    label.attemptResize(QgsLayoutSize(150, 10, QgsUnitTypes.LayoutMillimeters))
    layout.addLayoutItem(label)

    # Export
    exporter = QgsLayoutExporter(layout)

    out_png = os.path.join(ARTIFACTS_DIR, "line-atlas-native-renderer-page-17248394490.png")
    img_settings = QgsLayoutExporter.ImageExportSettings()
    img_settings.dpi = 150
    res = exporter.exportToImage(out_png, img_settings)
    print(f"PNG: result={res}, size={os.path.getsize(out_png) if os.path.exists(out_png) else 0}")

    out_pdf = os.path.join(ARTIFACTS_DIR, "line-atlas-native-renderer-17248394490.pdf")
    pdf_settings = QgsLayoutExporter.PdfExportSettings()
    pdf_settings.dpi = 150
    res2 = exporter.exportToPdf(out_pdf, pdf_settings)
    print(f"PDF: result={res2}, size={os.path.getsize(out_pdf) if os.path.exists(out_pdf) else 0}")

print("\nDone.")
app.exitQgis()
