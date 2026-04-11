# qfit GeoPackage schema

This document describes the current qfit GeoPackage layout and the intended next evolution.

## Design goals

- keep a canonical local source of truth for synced activities
- separate internal sync tables from visible GIS layers
- support both lightweight line rendering and richer point-based analysis
- create atlas-friendly page extents for publish/layout workflows
- stay flexible for Strava first, with room for FIT / GPX / TCX providers later

## GeoPackage contents

### Internal tables

- `activity_registry` — canonical non-spatial activity table used for sync/upsert logic
- `sync_state` — sync metadata table

### Visible layers

- `activity_tracks` — one visible line feature per activity
- `activity_starts` — one visible point per activity start
- `activity_points` — optional sampled point layer derived from detailed stream geometry
- `activity_atlas_pages` — polygon page/index layer for QGIS atlas or print-layout workflows, now with deterministic page ordering, TOC-friendly labels, publish-friendly detail labels/summary text, repeated document-summary fields for cover/TOC layouts, Web Mercator-ready extent metadata, and route-profile summary/label fields when detailed streams are available
- `atlas_document_summary` — non-spatial single-row helper table carrying atlas-wide totals and cover/TOC-ready labels for layouts that prefer a dedicated document-summary source
- `atlas_cover_highlights` — non-spatial ordered helper table carrying cover-ready label/value highlight rows for layouts that want simple metric cards or summary lists
- `atlas_page_detail_items` — non-spatial ordered one-row-per-detail helper table carrying layout-ready per-page label/value pairs for activity detail blocks
- `atlas_toc_entries` — non-spatial one-row-per-page helper table carrying page-number labels plus TOC-ready text/summary fields for contents layouts that should not depend on atlas polygon geometry

## Table: `activity_registry`

Geometry type:
- none

Primary purpose:
- canonical local source of truth for synced activities
- stable upsert target keyed by provider activity id

Recommended unique key:
- (`source`, `source_activity_id`)

### Current fields

| Field | Type | Notes |
|---|---|---|
| `source` | TEXT | provider name, e.g. `strava` |
| `source_activity_id` | TEXT | provider-specific activity id |
| `external_id` | TEXT | optional provider external id |
| `name` | TEXT | activity title |
| `activity_type` | TEXT | run, ride, hike, etc. |
| `sport_type` | TEXT | raw or provider sport type |
| `start_date` | TEXT | ISO 8601 UTC |
| `start_date_local` | TEXT | ISO 8601 local timestamp if available |
| `timezone` | TEXT | provider timezone string |
| `distance_m` | REAL | distance in meters |
| `moving_time_s` | INTEGER | moving time in seconds |
| `elapsed_time_s` | INTEGER | elapsed time in seconds |
| `total_elevation_gain_m` | REAL | total climb |
| `average_speed_mps` | REAL | average speed |
| `max_speed_mps` | REAL | max speed |
| `average_heartrate` | REAL | nullable |
| `max_heartrate` | REAL | nullable |
| `average_watts` | REAL | nullable |
| `kilojoules` | REAL | nullable |
| `calories` | REAL | nullable |
| `suffer_score` | REAL | nullable |
| `start_lat` | REAL | nullable |
| `start_lon` | REAL | nullable |
| `end_lat` | REAL | nullable |
| `end_lon` | REAL | nullable |
| `summary_polyline` | TEXT | encoded summary polyline when provided |
| `geometry_source` | TEXT | `stream`, `summary_polyline`, or `start_end` |
| `geometry_points_json` | TEXT | JSON array of detailed geometry points when available |
| `details_json` | TEXT | provider extras as JSON, including cached stream metrics and `detailed_route_status` (`cached`, `downloaded`, `empty`, `error`, `skipped_rate_limit`) when available |
| `summary_hash` | TEXT | stable change-detection hash |
| `first_seen_at` | TEXT | first time activity entered the registry |
| `last_synced_at` | TEXT | last sync/update time |

## Table: `sync_state`

Geometry type:
- none

Primary purpose:
- remember the most recent sync window and status
- capture rate-limit snapshots and sync counters

### Current fields

| Field | Type | Notes |
|---|---|---|
| `provider` | TEXT | provider key, e.g. `strava` |
| `last_incremental_sync_at` | TEXT | most recent successful sync time |
| `last_full_sync_at` | TEXT | most recent broad/full sync time |
| `last_before_epoch` | INTEGER | last used upper time bound |
| `last_after_epoch` | INTEGER | last used lower time bound |
| `last_success_status` | TEXT | last sync status |
| `last_rate_limit_snapshot` | TEXT | JSON snapshot of recent API quota state |
| `last_sync_stats_json` | TEXT | JSON sync counters |
| `updated_at` | TEXT | metadata update time |

## Layer: `activity_tracks`

Geometry type:
- `LINESTRING`

Primary purpose:
- visible line layer derived from `activity_registry`
- main visualization and filtering layer in QGIS

### Current fields

Mirrors key activity attributes from the registry, including:
- identifiers and labels
- activity type and timing
- distance / speed / heart-rate summary metrics
- geometry metadata (`geometry_source`, `geometry_point_count`)
- sync metadata (`summary_hash`, `first_seen_at`, `last_synced_at`)

## Layer: `activity_starts`

Geometry type:
- `POINT`

Primary purpose:
- start-point visualization
- clustering
- density analysis

### Current fields

| Field | Type | Notes |
|---|---|---|
| `activity_fk` | INTEGER | local sequential reference in the derived layer |
| `source` | TEXT | provider name |
| `source_activity_id` | TEXT | provider activity id |
| `name` | TEXT | activity title |
| `activity_type` | TEXT | run, ride, etc. |
| `start_date` | TEXT | ISO 8601 UTC |
| `distance_m` | REAL | copied for filtering / styling |
| `last_synced_at` | TEXT | last registry sync time |

## Layer: `activity_points`

Geometry type:
- `POINT`

Primary purpose:
- point-based analysis and visualization from detailed track streams
- heatmaps using sampled detailed geometry rather than just activity starts
- temporal playback in QGIS using sampled local or UTC timestamps

### Current fields

| Field | Type | Notes |
|---|---|---|
| `activity_fk` | INTEGER | local sequential reference in the derived layer |
| `source` | TEXT | provider name |
| `source_activity_id` | TEXT | provider activity id |
| `point_index` | INTEGER | original sampled point index |
| `point_ratio` | REAL | normalized progress across the activity track |
| `stream_time_s` | INTEGER | sampled stream time offset when available |
| `point_timestamp_utc` | TEXT | derived absolute UTC timestamp when possible |
| `point_timestamp_local` | TEXT | derived absolute local activity timestamp when possible |
| `stream_distance_m` | REAL | sampled cumulative distance when available |
| `altitude_m` | REAL | sampled altitude when available |
| `heartrate_bpm` | REAL | sampled heart rate when available |
| `cadence_rpm` | REAL | sampled cadence when available |
| `watts` | REAL | sampled power when available |
| `velocity_mps` | REAL | sampled smoothed speed when available |
| `temp_c` | REAL | sampled temperature when available |
| `grade_smooth_pct` | REAL | sampled smoothed grade when available |
| `moving` | INTEGER | sampled moving-state flag when available |
| `name` | TEXT | activity title |
| `activity_type` | TEXT | run, ride, etc. |
| `start_date` | TEXT | ISO 8601 UTC |
| `distance_m` | REAL | copied for filtering / styling |
| `geometry_source` | TEXT | usually `stream` |
| `last_synced_at` | TEXT | last registry sync time |

## Layer: `activity_atlas_pages`

Geometry type:
- `POLYGON`

Primary purpose:
- atlas/page index layer for QGIS print layouts and future PDF export workflows
- one padded extent polygon per activity with reusable title/subtitle fields
- extent padding/minimum size controlled by the plugin's publish settings at write time
- optional Web Mercator aspect-ratio fitting can widen/tallify the padded extent for more layout-consistent framing
- publish-friendly detail labels (`page_toc_label`, `page_average_speed_label`, `page_average_pace_label`, `page_elevation_gain_label`) plus `page_stats_summary` and `page_profile_summary` reduce per-layout expression boilerplate for per-activity stat blocks
- repeated document-summary fields (`document_activity_count`, `document_date_range_label`, `document_total_distance_label`, `document_total_duration_label`, `document_total_elevation_gain_label`, `document_activity_types_label`, `document_cover_summary`) still make it easy for per-page layout expressions to reuse atlas-wide totals
- the companion `atlas_document_summary` table now provides the same atlas-wide totals/labels as a dedicated single-row source for cover and table-of-contents layouts
- the companion `atlas_cover_highlights` table now provides ordered cover-metric label/value rows for simple cover-page cards or summary lists
- the companion `atlas_page_detail_items` table now provides ordered per-page label/value rows for activity detail sidebars or stat grids in atlas layouts
- the companion `atlas_toc_entries` table now provides one clean non-spatial row per atlas page, with page-number labels and preformatted TOC entry text for contents-page tables
- route-profile summary and label fields give layouts a cheap way to decide whether to show an elevation chart and to reuse publish-friendly text without extra QGIS expression boilerplate before full PDF automation exists

### Current fields

| Field | Type | Notes |
|---|---|---|
| `activity_fk` | INTEGER | local sequential reference in the derived layer |
| `source` | TEXT | provider name |
| `source_activity_id` | TEXT | provider activity id |
| `name` | TEXT | activity title |
| `activity_type` | TEXT | run, ride, etc. |
| `sport_type` | TEXT | raw/provider sport type when available, preserved so subset-aware cover summaries can reuse canonical labels |
| `start_date` | TEXT | ISO 8601 UTC |
| `distance_m` | REAL | copied for filtering / layout text |
| `moving_time_s` | INTEGER | copied for layout text |
| `total_elevation_gain_m` | REAL | copied numeric climb total so subset-aware cover summaries can recompute aggregate climbing from exported atlas features |
| `geometry_source` | TEXT | stream/summary/fallback source used to derive the page extent |
| `page_number` | INTEGER | stable chronological page number for layouts / table-of-contents workflows |
| `page_sort_key` | TEXT | deterministic sort key combining activity datetime, name, source, and source id |
| `page_name` | TEXT | atlas-friendly page label, usually `YYYY-MM-DD · Title` |
| `page_title` | TEXT | large-title label |
| `page_subtitle` | TEXT | compact summary such as type, distance, and moving time |
| `page_date` | TEXT | preformatted local/primary activity date for layout labels |
| `page_toc_label` | TEXT | preformatted TOC-ready line such as `2026-03-18 · Morning Gravel Ride · 42.5 km · 2h 00m` |
| `page_distance_label` | TEXT | preformatted distance label such as `42.5 km` |
| `page_duration_label` | TEXT | preformatted moving-time label such as `2h 00m` |
| `page_average_speed_label` | TEXT | preformatted speed label such as `25.2 km/h` for layouts that show average speed |
| `page_average_pace_label` | TEXT | preformatted pace label such as `4m 57s/km` for run/walk/hike layouts |
| `page_elevation_gain_label` | TEXT | preformatted total ascent label such as `640 m` for per-page detail blocks |
| `page_stats_summary` | TEXT | preformatted one-line stat summary such as `42.5 km · 2h 00m · 21.3 km/h · ↑ 640 m` for simple atlas detail text |
| `page_profile_summary` | TEXT | preformatted one-line route-profile summary such as `3.0 km · 500–560 m · relief 60 m · ↑ 75 m · ↓ 15 m` for layouts that show elevation/profile details |
| `document_activity_count` | INTEGER | repeated atlas-wide activity count so cover/TOC layouts can read it directly from the atlas layer |
| `document_date_range_label` | TEXT | repeated atlas-wide date span such as `2026-03-18 → 2026-03-20` |
| `document_total_distance_label` | TEXT | repeated atlas-wide distance total such as `82.6 km` |
| `document_total_duration_label` | TEXT | repeated atlas-wide moving-time total such as `4h 20m` |
| `document_total_elevation_gain_label` | TEXT | repeated atlas-wide climb total such as `1145 m` |
| `document_activity_types_label` | TEXT | repeated atlas-wide ordered activity-type list such as `Ride, Run` |
| `document_cover_summary` | TEXT | repeated one-line atlas summary such as `3 activities · 2026-03-18 → 2026-03-20 · 82.6 km · 4h 20m · ↑ 1145 m · Ride, Run` |
| `profile_available` | INTEGER | `1` when the activity has enough sampled distance + altitude stream data for a route profile |
| `profile_point_count` | INTEGER | number of usable sampled profile points contributing to the summary |
| `profile_distance_m` | REAL | sampled profile length in meters based on the usable distance stream |
| `profile_distance_label` | TEXT | preformatted profile length such as `3.0 km` for layout text |
| `profile_min_altitude_m` | REAL | minimum sampled elevation available to a future profile diagram |
| `profile_max_altitude_m` | REAL | maximum sampled elevation available to a future profile diagram |
| `profile_altitude_range_label` | TEXT | preformatted altitude span such as `500–560 m` |
| `profile_relief_m` | REAL | simple max-minus-min altitude relief for profile scaling or legends |
| `profile_elevation_gain_m` | REAL | cumulative sampled climbing derived from consecutive altitude deltas |
| `profile_elevation_gain_label` | TEXT | preformatted climb label such as `75 m` |
| `profile_elevation_loss_m` | REAL | cumulative sampled descent derived from consecutive altitude deltas |
| `profile_elevation_loss_label` | TEXT | preformatted descent label such as `15 m` |
| `center_x_3857` | REAL | Web Mercator page center X for EPSG:3857 layouts |
| `center_y_3857` | REAL | Web Mercator page center Y for EPSG:3857 layouts |
| `extent_width_deg` | REAL | padded page width in degrees after the configured atlas margin/minimum extent rules |
| `extent_height_deg` | REAL | padded page height in degrees after the configured atlas margin/minimum extent rules |
| `extent_width_m` | REAL | padded page width in Web Mercator meters |
| `extent_height_m` | REAL | padded page height in Web Mercator meters |

## Table: `atlas_document_summary`

Geometry type:
- none

Primary purpose:
- store atlas-wide totals and cover/TOC-ready labels as a dedicated single-row helper table
- give QGIS print layouts a clean document-summary source without forcing cover pages to read repeated values from an arbitrary atlas polygon feature

### Current fields

| Field | Type | Notes |
|---|---|---|
| `activity_count` | INTEGER | number of atlas pages / usable activities included in the atlas summary |
| `activity_date_start` | TEXT | first atlas activity date such as `2026-03-18` |
| `activity_date_end` | TEXT | last atlas activity date such as `2026-03-20` |
| `date_range_label` | TEXT | preformatted date span such as `2026-03-18 → 2026-03-20` |
| `total_distance_m` | REAL | total atlas distance in meters |
| `total_distance_label` | TEXT | preformatted total distance such as `82.6 km` |
| `total_moving_time_s` | INTEGER | total atlas moving time in seconds |
| `total_duration_label` | TEXT | preformatted total duration such as `4h 20m` |
| `total_elevation_gain_m` | REAL | total atlas elevation gain in meters |
| `total_elevation_gain_label` | TEXT | preformatted total climb such as `1145 m` |
| `activity_types_label` | TEXT | ordered activity-type list such as `Ride, Run` |
| `cover_summary` | TEXT | one-line cover summary such as `3 activities · 2026-03-18 → 2026-03-20 · 82.6 km · 4h 20m · ↑ 1145 m · Ride, Run` |

## Table: `atlas_cover_highlights`

Geometry type:
- none

Primary purpose:
- store ordered cover-page highlight rows as simple label/value pairs
- let QGIS print layouts bind cover metric cards or summary lists without rebuilding those strings in expressions

### Current fields

| Field | Type | Notes |
|---|---|---|
| `highlight_order` | INTEGER | stable display order for a cover layout table or repeated card frame |
| `highlight_key` | TEXT | stable metric key such as `activity_count` or `total_distance` |
| `highlight_label` | TEXT | layout-ready label such as `Activities` or `Distance` |
| `highlight_value` | TEXT | formatted value such as `12 activities` or `420.7 km` |

## Table: `atlas_page_detail_items`

Geometry type:
- none

Primary purpose:
- store ordered per-page detail rows as simple label/value pairs
- let QGIS print layouts bind activity stat sidebars or repeated cards without rebuilding those strings in expressions

### Current fields

| Field | Type | Notes |
|---|---|---|
| `page_number` | INTEGER | stable chronological page number matching `activity_atlas_pages.page_number` |
| `page_sort_key` | TEXT | deterministic sort key matching the atlas-page layer |
| `page_name` | TEXT | atlas-friendly page label such as `2026-03-18 · Morning Ride` |
| `page_title` | TEXT | activity title copied from the atlas page |
| `detail_order` | INTEGER | stable display order for a page-detail table or repeated card frame |
| `detail_key` | TEXT | stable metric key such as `distance`, `moving_time`, or `profile_summary` |
| `detail_label` | TEXT | layout-ready label such as `Distance` or `Climbing` |
| `detail_value` | TEXT | formatted value such as `42.5 km` or `3.0 km · 500–560 m · relief 60 m · ↑ 75 m · ↓ 15 m` |

## Table: `atlas_toc_entries`

Geometry type:
- none

Primary purpose:
- store one row per atlas page for TOC/layout tables without depending on atlas polygon geometry
- give QGIS print layouts page-number labels plus preformatted TOC entry text and per-page summary fields

### Current fields

| Field | Type | Notes |
|---|---|---|
| `page_number` | INTEGER | stable chronological page number matching `activity_atlas_pages.page_number` |
| `page_number_label` | TEXT | preformatted page number label such as `1` |
| `page_sort_key` | TEXT | deterministic sort key matching the atlas-page layer |
| `page_name` | TEXT | atlas-friendly page label such as `2026-03-18 · Morning Ride` |
| `page_title` | TEXT | large-title label copied from the atlas page |
| `page_subtitle` | TEXT | compact detail line copied from the atlas page |
| `page_date` | TEXT | preformatted page date for contents layouts |
| `page_toc_label` | TEXT | preformatted TOC-ready line such as `2026-03-18 · Morning Ride · 42.5 km · 2h 00m` |
| `toc_entry_label` | TEXT | page-number-prefixed TOC line such as `1. 2026-03-18 · Morning Ride · 42.5 km · 2h 00m` |
| `page_distance_label` | TEXT | preformatted page distance label |
| `page_duration_label` | TEXT | preformatted page duration label |
| `page_stats_summary` | TEXT | one-line page stats summary for compact contents layouts |
| `profile_available` | INTEGER | `1` when route-profile metadata is available for the page |
| `page_profile_summary` | TEXT | one-line route-profile summary for richer contents/detail tables |

## Geometry priority

When rebuilding visible layers and derived `activity_points`, qfit currently prefers geometry in this order:
1. detailed stream points from `geometry_points_json`
2. decoded `summary_polyline`
3. fallback start/end line from start and end coordinates

## Current sync flow

1. fetch Strava summaries for the selected window
2. optionally enrich activities with detailed stream geometry and extra stream metrics
3. upsert activities into `activity_registry`
4. update `sync_state`
5. rebuild `activity_tracks`, `activity_starts`, `activity_points`, `activity_atlas_pages`, `atlas_document_summary`, `atlas_cover_highlights`, `atlas_page_detail_items`, and `atlas_toc_entries` as part of the normal write pipeline
6. load those layers into QGIS

## Next phase

Planned next improvements:
- PDF/layout automation on top of `activity_atlas_pages`
- richer temporal styling and playback presets on top of the new timestamp wiring
- provider adapters for FIT / GPX / TCX imports using the same registry model
- more explicit incremental sync cursors / sync policies
- better QGIS integration testing and packaging polish
