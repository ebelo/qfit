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
- `activity_atlas_pages` — polygon page/index layer for QGIS atlas or print-layout workflows, now with deterministic page ordering, TOC-friendly labels, publish-friendly detail labels/summary text, Web Mercator-ready extent metadata, and route-profile summary/label fields when detailed streams are available

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
| `details_json` | TEXT | provider extras as JSON, including cached stream metrics when available |
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
- publish-friendly detail labels (`page_toc_label`, `page_average_speed_label`, `page_average_pace_label`, `page_elevation_gain_label`) plus `page_stats_summary` reduce per-layout expression boilerplate for per-activity stat blocks
- route-profile summary and label fields give layouts a cheap way to decide whether to show an elevation chart and to reuse publish-friendly text without extra QGIS expression boilerplate before full PDF automation exists

### Current fields

| Field | Type | Notes |
|---|---|---|
| `activity_fk` | INTEGER | local sequential reference in the derived layer |
| `source` | TEXT | provider name |
| `source_activity_id` | TEXT | provider activity id |
| `name` | TEXT | activity title |
| `activity_type` | TEXT | run, ride, etc. |
| `start_date` | TEXT | ISO 8601 UTC |
| `distance_m` | REAL | copied for filtering / layout text |
| `moving_time_s` | INTEGER | copied for layout text |
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

## Geometry priority

When rebuilding visible layers, qfit currently prefers geometry in this order:
1. detailed stream points from `geometry_points_json`
2. decoded `summary_polyline`
3. fallback start/end line from start and end coordinates

## Current sync flow

1. fetch Strava summaries for the selected window
2. optionally enrich activities with detailed stream geometry and extra stream metrics
3. upsert activities into `activity_registry`
4. update `sync_state`
5. rebuild `activity_tracks`, `activity_starts`, `activity_atlas_pages`, and optionally `activity_points`
6. load those layers into QGIS

## Next phase

Planned next improvements:
- PDF/layout automation on top of `activity_atlas_pages`
- richer temporal styling and playback presets on top of the new timestamp wiring
- provider adapters for FIT / GPX / TCX imports using the same registry model
- more explicit incremental sync cursors / sync policies
- better QGIS integration testing and packaging polish
