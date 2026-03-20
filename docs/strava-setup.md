# Strava setup for QFIT

QFIT now includes a built-in helper for the Strava OAuth flow.

## What you need

From your Strava API application:
- `client_id`
- `client_secret`

QFIT can then help you generate and store the `refresh_token` needed for repeated imports.

## Create a Strava API app

1. Go to the Strava API settings page for your account.
2. Create an application.
3. Set an authorization callback / redirect URI.
4. Use the same redirect URI value inside QFIT.

A practical default for local testing is:
- `http://localhost/exchange_token`

## Generate the refresh token inside QFIT

1. Open the QFIT dock in QGIS.
2. Enter your `client_id` and `client_secret`.
3. Enter the same redirect URI you configured in Strava.
4. Click **Open Strava authorize page**.
5. Approve access in the browser.
6. After Strava redirects you, copy the `code` query parameter from the URL.
7. Paste that code into **Authorization code** in QFIT.
8. Click **Exchange code**.
9. QFIT will store the returned refresh token in local QGIS settings.

## Import activities

Once the refresh token is available:

1. Set the date range and paging limits.
2. Optionally enable detailed streams and choose a detailed-tracks limit.
3. Click **Fetch from Strava**.
4. Choose an output `.gpkg` path.
5. Click **Write + Load**.
6. Apply filters and style presets as needed.

## Notes

- Strava access tokens expire quickly; the refresh token is the important long-lived credential.
- QFIT refreshes the access token automatically before downloading activities.
- When detailed streams are enabled, QFIT caches downloaded stream geometries locally to avoid re-fetching them unnecessarily.
- QFIT also applies a simple rate-limit guard and may skip some detailed stream downloads if the remaining Strava quota gets too low.
- Credentials are currently stored in local QGIS settings for convenience, not in an encrypted vault.
not in an encrypted vault.
