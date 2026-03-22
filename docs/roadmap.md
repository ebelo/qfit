# qfit roadmap

This roadmap organizes qfit into the three product lanes Emman defined:

1. **Import** — database population and sync
2. **Visualize** — map styling, data filtering, activity querying
3. **Publish** — PDF atlas generation with cover page, table of contents, per-page map/details, and route profile diagrams when relevant

It also tracks the cross-cutting background-map / Mapbox configuration work.

## Status legend

- **Done** — merged and usable
- **In progress** — actively being implemented
- **Planned** — agreed direction, not implemented yet

---

## Snapshot

### Done / strong progress

- Core Strava-based import flow
- GeoPackage sync/store model
- Styling + filtering basics
- Background map selector with Mapbox configuration
- Activity query preview and richer filtering
- QGIS temporal playback wiring
- Test suite / CI / SonarCloud quality gates

### In progress

- Publish / atlas generation foundations

### Still weak / not started enough

- Full atlas-generation workflow
- Rich import-source expansion beyond Strava
- Deeper separation of the plugin into explicit Import / Visualize / Publish workflows

---

## 1) Import

Goal: handle database population and sync.

### Done

- Strava authentication and token refresh flow
- Strava activity download
- Date-bounded fetches
- Optional detailed stream enrichment
- Local stream caching
- Basic rate-limit guard
- Canonical GeoPackage registry / upsert sync flow
- Derived track / start / point layers built from synced data
- Time-aware sampled points with UTC/local timestamps

### Planned

- Clearer dedicated **Import** UX in the plugin
- Incremental sync controls / sync-status visibility
- Source-management UX (provider selection / source settings)
- Additional import adapters:
  - FIT
  - GPX
  - TCX
- Better sync diagnostics and recovery UX

### Notes

Import is already functional, but still mostly **Strava-first** rather than a generalized import framework.

---

## 2) Visualize

Goal: map styling, data filtering, and activity querying.

### Done

- Activity filtering by:
  - type
  - date range
  - minimum distance
- Style presets and layer styling basics
- Start points / tracks / heatmap-style views
- Auto-zoom to loaded data extents
- Working QGIS map/project projection choice aligned to Web Mercator (`EPSG:3857`)
- Background-map support via Mapbox
- Background presets:
  - Outdoor
  - Light
  - Satellite
  - Winter (custom style slot)
  - Custom
- Saved plugin settings for Mapbox/token/style selection
- Richer activity querying:
  - name search
  - max distance
  - detailed-stream-only filter
  - preview sorting
  - fetched-activity preview/summary panel
- QGIS temporal playback wiring:
  - disabled / local activity time / UTC time
  - temporal layer configuration for points, tracks, and starts

### Planned

- Better activity details panel / inspection workflow
- More polished symbology and map presets
- Smarter visualization presets per activity type
- Query saving / reusable view presets
- More explicit basemap and map-style configuration UX
- Better separation between preview/query controls and post-load QGIS layer subsetting
- Route/profile-linked inspection in the visualization flow

### Notes

Visualize is currently the **most advanced** roadmap lane.

---

## 3) Publish

Goal: configure and generate a PDF atlas with:

- cover page
- table of contents
- one page per activity
- map + activity details
- route profile diagram when relevant

### Done

- Nothing substantial merged yet in the publish flow itself

### In progress

- Early atlas-generation groundwork is being explored in feature work
- Atlas output now carries route-profile summary metadata when detailed stream metrics are available, plus layout-friendly profile labels/relief for future profile panels and print layouts
- Atlas planning helpers now also compute cover-ready document summary totals (activity count, date span, totals, activity types, one-line summary text) and the GeoPackage now exposes them through a dedicated `atlas_document_summary` helper table for cover/TOC layouts
- The GeoPackage now also includes an `atlas_toc_entries` helper table with one non-spatial row per atlas page so QGIS contents-page tables can bind to clean TOC data without depending on atlas polygons
- The GeoPackage now also includes an `atlas_profile_samples` helper table with ordered distance/elevation sample rows per page so future QGIS route-profile diagrams can bind to atlas-ready chart data

### Planned

- Publish configuration model
- Atlas document structure
- Cover-page generation
- Table-of-contents generation
- Per-activity page templating
- Route-profile rendering
- Export pipeline to PDF
- Styling/layout presets for publish output

### Notes

Publish is currently the **largest remaining roadmap block**.

---

## Cross-cutting engineering progress

These are not roadmap lanes by themselves, but they materially improve delivery speed and reliability:

- Standard unit test suite for core non-QGIS modules
- GitHub Actions CI
- SonarCloud integration
- Lowercase `qfit` naming cleanup for consistent packaging/imports

---

## Suggested near-term order

1. Keep strengthening **Publish** until the first end-to-end atlas export exists
2. Continue smaller **Visualize** improvements that directly support atlas quality
3. Revisit **Import** generalization once the first publish flow is real

That ordering keeps momentum on the biggest unfinished roadmap promise while reusing the strong visualization base already in place.
