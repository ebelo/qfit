# Atlas export debugging status — 2026-03-22

## Problem being debugged

Real qfit atlas PDF exports still show route framing/clipping problems on Emman's live data even after rebuilding atlas pages and regenerating the PDF.

## What was ruled out

- **Not just stale export/cache**
  - `/home/ebelo/qfit_activities.gpkg` was newer than the earlier broken PDF.
  - A newer `/home/ebelo/qfit_atlas.pdf` was later generated and still showed the issue.
- **Not undersized atlas page polygons in the GeoPackage**
  - Checked the current `activity_atlas_pages` layer against `activity_tracks` extents.
  - All atlas page polygons contained their corresponding track extents.
  - Example checked directly: page 537 (`2026-02-01 · Morning Nordic Ski`, `source_activity_id=17248394490`) had healthy margins around the track in EPSG:3857.
- **Not purely a target-aspect-ratio setting issue**
  - Setting target page aspect ratio to ~`1.731` changed generated extents but did not eliminate the live export problem.

## What changed today

### 1. Reverted temporary atlas filter toggling

Commit:
- `ba0fd1a` — `revert atlas export subset filter toggling`

Reason:
- clearing/restoring a temporary subset filter around atlas export did not help and was confusing.

### 2. Made built-in atlas export default to the real map-frame aspect ratio

Commit:
- `559acc4` — `fix atlas export default aspect ratio`

Reason:
- the built-in PDF export map frame is fixed-size, so the plugin should default atlas page planning to that actual ratio instead of leaving it unset.

Outcome:
- improves default atlas page generation logic, but did **not** fully solve Emman's live export issue.

### 3. Added raster basemap zoom snapping helpers

Commit:
- `f1ff6d8` — `fix raster basemap zoom snapping`

Reason:
- separate visual-quality work from the roadmap heartbeat flow; not the core cause of the atlas clipping issue.

### 4. Removed atlas extent overlay from the exported map

Commit:
- `b458821` — `exclude atlas extent overlay from export`

Reason:
- the atlas coverage polygon layer (`qfit atlas pages`) was being rendered into the exported map itself, which made the output harder to interpret and introduced overlay confusion.

Outcome:
- Emman reported the output changed, confirming live code changes were affecting the real export path.
- However, the core framing bug remained.

## Local reproduction / findings

### Controlled synthetic export

A controlled headless PyQGIS export using synthetic data produced a page where the route was fully visible inside the map frame.

Artifacts created during debugging:
- `/home/ebelo/.openclaw/workspace/qfit/debug/atlas_test2/output_1.png`
- `/home/ebelo/.openclaw/workspace/qfit/debug/problem_page_537/output_1.png`

Interpretation:
- the exporter can produce a correct-looking page in a controlled case.
- the live bug is likely data/project/export-path specific, not a total failure of atlas generation.

### Live data inspection

Current data files observed:
- GeoPackage: `/home/ebelo/qfit_activities.gpkg`
- PDF: `/home/ebelo/qfit_atlas.pdf`

Key direct checks:
- `activity_atlas_pages` count matched `activity_tracks` count.
- no atlas page rectangle was smaller than its matching track extent.
- problematic Nordic Ski page data looked geometrically valid in the GeoPackage.

## Current working theory

The remaining bug is likely in the **live export/render behavior**, not in stored atlas page geometry.

Most likely next step:
- stop relying on QGIS atlas **Auto** scaling behavior for the export map item
- instead, set the export map extent **explicitly and deterministically** from stored atlas-page fields:
  - `center_x_3857`
  - `center_y_3857`
  - `extent_width_m`
  - `extent_height_m`

This should bypass QGIS atlas auto-fit quirks and make each exported page use the exact precomputed rectangle from `activity_atlas_pages`.

## User-facing state at handoff

Emman knows:
- this is a real exporter bug on live data, not just cache
- live exports are being affected by code changes now
- the next intended fix is deterministic per-page extent control during export

## Constraints / session state

- Weekly model budget is critically low (~4% at the latest check-in).
- Emman explicitly asked for the current state to be documented because Codex/OpenAI credits are running low.
- Best next resume point: implement/test deterministic atlas extent application during export, starting from `atlas_export_task.py`.
