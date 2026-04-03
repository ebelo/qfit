# Issue #239 spike — pure line-based atlas + native QGIS elevation profile

Date: 2026-04-03
Branch: `spike/line-atlas-native-profile`

## Goal

Evaluate whether qfit can support a **pure line-based atlas pipeline** where:

- atlas coverage layer is a `LineStringZ`
- the atlas uses QGIS-computed extent / line-driven coverage
- the profile chart is a native `QgsLayoutItemElevationProfile`
- no SVG/picture-backed fallback is used in the happy path

## Real-data validation target

- GeoPackage: `/home/ebelo/.openclaw/workspace/tmp_qfit_activities.gpkg`
- Activity: `14862170002` (`Evening Walk`)
- Runtime: QGIS `3.34.4` headless export path

## What was validated

A single-feature line atlas coverage layer was generated from the real activity track:

- source geometry: `activity_tracks.geom`
- Z values: `atlas_profile_samples.altitude_m`
- result geometry: `LineStringZ`
- layout input: line coverage layer + native `QgsLayoutItemElevationProfile`

Observed during layout construction:

- `native_profile_item_available = True`
- `atlas_layer_supports_native_profile_atlas = True`
- qfit created `QgsLayoutItemElevationProfile`
- `atlasDriven = True`
- export to PNG/PDF completed successfully

## Artifacts

Generated in `validation_artifacts/`:

- `line-atlas-coverage-14862170002.gpkg`
- `line-atlas-native-profile-14862170002.pdf`
- `line-atlas-native-profile-14862170002-page.png`
- `line-atlas-native-profile-14862170002-mapextent.pdf`
- `line-atlas-native-profile-14862170002-page-mapextent.png`

## Result

### Native profile result

**Failed for the target use case.**

The exported atlas page shows the native profile frame, but the chart renders as:

- blank plot area
- default-looking axes/grid
- no visible elevation curve
- no meaningful distance/elevation scaling from the underlying activity

In the inspected export, the visible axes remained effectively at the default range:

- Y axis: `0–10 m`
- X axis: `0–10 km`

This means the native layout item still did **not** bind/render the real profile data in exported output, even when the atlas coverage geometry itself is a valid `LineStringZ`.

### Map result

The validation export also did not produce a useful visible route map in the page output, even after forcing the stored extent manually in the validation script. That makes the line-atlas path weaker than the current production polygon-page export path from a cartographic perspective too.

## Interpretation

This spike answers the main question from issue #239:

> If the atlas coverage itself were line-based, could QGIS handle both the map extent and the elevation profile natively, without qfit's SVG fallback path?

**Answer on QGIS 3.34.4 / headless export: no, not reliably enough.**

Changing the atlas coverage geometry from polygon to line is **not sufficient** to make the native layout elevation-profile path work for exported output.

The evidence indicates that the blocker is deeper than just the polygon/line mismatch. The native layout item still fails to render the actual profile in exported output under this runtime.

## Conclusion

### Outcome

**Reject** as a production replacement path for now.

### Why

It fails the spike acceptance criteria:

- atlas can run with a line coverage layer ✅
- exported PDF exists ✅
- native profile shows a visible elevation curve ❌
- map framing/rendering is acceptable ❌
- real-data validation performed on `14862170002` ✅

### Recommended direction

Keep the current production architecture on `main`:

- polygon-driven atlas pages
- qfit-rendered SVG/picture-backed profile for polygon atlas export
- optional geometry/native fallback only where it is actually reliable

A future revisit would likely need:

- newer QGIS runtime behavior, or
- a different native rendering/export mechanism than `QgsLayoutItemElevationProfile` in headless export
