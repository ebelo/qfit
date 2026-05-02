# Strava setup for qfit

qfit includes a built-in helper for the Strava OAuth flow.

## What you need

From your Strava API application:
- `client_id`
- `client_secret`

qfit can then help you generate and store the `refresh_token` needed for repeated imports.

## Create a Strava API app

1. Go to the Strava API settings page for your account.
2. Create an application.
3. Set an authorization callback / redirect URI.
4. Use the same redirect URI value inside qfit.

A practical default for local testing is:
- `http://localhost/exchange_token`

## Generate the refresh token inside qfit

1. Open `qfit` → `Configuration` in QGIS.
2. Enter your `client_id` and `client_secret`.
3. Enter the same redirect URI you configured in Strava.
4. Click **Open Strava authorize page**.
5. If qfit cannot launch the browser automatically, it will copy the authorization URL to your clipboard so you can open it manually.
6. Approve access in the browser.
7. After Strava redirects you, copy the `code` query parameter from the URL.
7. Paste that code into **Authorization code** in qfit.
8. Click **Exchange code**.
9. qfit will store the returned refresh token in local QGIS settings.

## Import activities

Once the refresh token is available:

1. Set the date range and paging limits.
2. Optionally enable detailed streams and choose a detailed-track fetch limit.
3. Optionally enable **Write sampled activity_points from detailed tracks** and choose how many points to keep.
4. Click **Fetch from Strava**.
5. Review the fetched-activity preview and refine filters such as name search, min/max distance, or detailed-only mode if needed.
6. Choose an output `.gpkg` path.
7. Click **Write + load layers**.
8. Use **Apply current filters** only when you want the already loaded QGIS layers to match the current dock query.

## Saved route catalog scope

qfit's Strava authorization URL now requests `read_all` in addition to activity-read access. Saved/planned routes use Strava route-list, route-detail, and GPX export endpoints through the same refresh-token flow as activity imports. Users who authorized qfit before route-catalog support may need to re-authorize if Strava reports that their token does not have route visibility.

The route-catalog implementation persists routes separately from completed activities as `route_registry`, `route_tracks`, and `route_points` GeoPackage objects. GPX exports with elevation are stored as true `LineStringZ` route tracks plus explicit ordered profile samples for future profiles and difficulty scoring.

Tip:
- Hover the most confusing controls or use the small `?` buttons in the dock for inline guidance about detailed-track limits, point sampling, basemap setup, temporal timestamps, and write/load vs filter behavior.

## Notes

- Strava access tokens expire quickly; the refresh token is the important long-lived credential.
- qfit refreshes the access token automatically before downloading activities.
- When detailed streams are enabled, qfit caches downloaded stream bundles locally to avoid re-fetching them unnecessarily.
- qfit also applies a simple rate-limit guard and may skip some detailed stream downloads if the remaining Strava quota gets too low.
- The optional `activity_points` layer is derived from detailed geometry and can include sampled stream metrics such as time, distance, elevation, heart rate, cadence, power, speed, temperature, grade, and moving-state flags when Strava provides them.
- qfit now also derives absolute sampled timestamps for `activity_points` when the stream time offsets and activity start times are available.
- Credentials are currently stored in local QGIS settings for convenience, not in an encrypted vault.
