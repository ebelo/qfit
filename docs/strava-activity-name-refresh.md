# Refresh renamed Strava activities

Normal **Sync activities** checks recent activity dates with a three-day overlap.
Renaming an older activity in Strava does not move it into that window.

To update those names without re-importing routes:

1. Select your existing qfit GeoPackage under **Settings → Data storage**.
2. Configure your Strava connection in **Settings** if needed.
3. Open **Settings → Data storage → Database actions → Refresh activity names…**.
4. Enter the numeric Strava activity IDs separated by commas, for example
   `123456789, 987654321`. An ID is the number in the activity's Strava URL.
   Leave the field empty to refresh all historical activity summaries.
5. Wait for the background task to finish, or click **Cancel name refresh**
   in the same Database actions menu to request cancellation. The status reports updated names,
   unchanged names, and activities not stored locally (ignored).

For a few renamed activities, selecting IDs uses fewer API requests. A full
historical refresh uses paginated summary requests and is subject to Strava's
rate limits. Neither option downloads detailed streams.

Only existing activity names and corresponding stored map/atlas labels change.
Tracks, recorded measurements, sampled points, compressed detail payloads,
activity identities, and the incremental-sync checkpoint remain unchanged.
Existing atlas page numbers and ordering are preserved; a title-derived sort key
is refreshed only when it does not move the page across a neighbor.
No new activities are imported and no activities are deleted. Loaded layers
from the selected GeoPackage are refreshed after success.

Names are written only after the requested fetch completes. Cancelling before
commit, an API error, or a rate-limited incomplete historical fetch leaves names
unchanged. Retry after the rate limit resets, or refresh specific IDs instead.
An inaccessible/deleted ID fails the selected refresh without applying earlier
results. Cancellation after the transaction has committed cannot undo it.

Previously exported PDFs are not rewritten; export again to use the new names.
