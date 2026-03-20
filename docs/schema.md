# QFIT GeoPackage schema

This document defines the first-pass internal data model and GeoPackage layout for QFIT.

## Design goals

- Keep the first version simple enough to implement quickly
- Preserve source identifiers for re-import and deduplication
- Support both line geometry and point-based visualizations
- Stay flexible for Strava first, other providers later

## GeoPackage file

Suggested output name:
- `qfit_activities.gpkg`

Suggested layers:
- `activities` — one feature per activity, line geometry when available
- `activity_starts` — one point per activity start
- `activity_bounds` — optional extent/bounding box derived later

## Layer: `activities`

Geometry type:
- `LINESTRING`

Primary purpose:
- main visualization and filtering layer

### Fields

| Field | Type | Notes |
|---|---|---|
| `id` | INTEGER | local row id |
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
| `calories` | REAL | nullable, source dependent |
| `suffer_score` | REAL | nullable |
| `start_lat` | REAL | nullable if no coordinates |
| `start_lon` | REAL | nullable if no coordinates |
| `end_lat` | REAL | nullable |
| `end_lon` | REAL | nullable |
| `summary_polyline` | TEXT | encoded polyline when provided |
| `details_json` | TEXT | raw extra provider attributes as JSON |
| `imported_at` | TEXT | ISO 8601 import timestamp |
| `updated_at` | TEXT | ISO 8601 last sync timestamp |

### Uniqueness

Recommended unique key:
- (`source`, `source_activity_id`)

## Layer: `activity_starts`

Geometry type:
- `POINT`

Primary purpose:
- start point visualization
- cluster styling
- density analysis

### Fields

| Field | Type | Notes |
|---|---|---|
| `id` | INTEGER | local row id |
| `activity_fk` | INTEGER | link to local activities row when available |
| `source` | TEXT | provider name |
| `source_activity_id` | TEXT | provider activity id |
| `name` | TEXT | activity title |
| `activity_type` | TEXT | run, ride, etc. |
| `start_date` | TEXT | ISO 8601 UTC |
| `distance_m` | REAL | copied for easy styling/filtering |
| `imported_at` | TEXT | ISO 8601 import timestamp |

## Internal Python model

First-pass canonical activity object:

```python
activity = {
    "source": "strava",
    "source_activity_id": "123456",
    "external_id": None,
    "name": "Evening Run",
    "activity_type": "Run",
    "sport_type": "Run",
    "start_date": "2026-03-20T18:00:00Z",
    "start_date_local": "2026-03-20T19:00:00",
    "timezone": "Europe/Zurich",
    "distance_m": 10000.0,
    "moving_time_s": 3200,
    "elapsed_time_s": 3500,
    "total_elevation_gain_m": 120.0,
    "average_speed_mps": 3.12,
    "max_speed_mps": 5.2,
    "average_heartrate": None,
    "max_heartrate": None,
    "average_watts": None,
    "kilojoules": None,
    "calories": None,
    "suffer_score": None,
    "start_lat": 47.3769,
    "start_lon": 8.5417,
    "end_lat": 47.39,
    "end_lon": 8.55,
    "summary_polyline": "...",
    "details_json": {},
}
```

## Import strategy

### Phase 1
- store the Strava summary polyline if available
- decode to `LINESTRING`
- create one activity feature
- create one start point feature when start coordinates exist

### Phase 2
- support detailed streams for richer geometries
- support activity updates/upserts
- add optional raw JSON cache table
- add more provider adapters

## Filtering support

The chosen fields support the initial UI filters:
- activity type
- date range
- distance range
- duration range

## Notes

- Timestamps are stored as ISO 8601 text for portability
- Distances are stored in meters; UI can display kilometers
- Provider-specific extras should go into `details_json` instead of schema bloat in the MVP
