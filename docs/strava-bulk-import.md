# Strava Bulk Data Export import

qfit can import the recorded activities from an athlete's official Strava Bulk
Data Export into the same GeoPackage used by daily Strava synchronization. The
bulk export is the recommended way to seed historical data; API synchronization
can then keep recent activities current.

For the implementation architecture, threat model, parser contract, persistence
benchmark, validation evidence, and review history, see the
[engineering and validation guide](strava-bulk-import-engineering.md).

## Get and import an export

1. Request a Bulk Data Export using Strava's
   [official export workflow](https://support.strava.com/hc/en-us/articles/216918437-Exporting-your-Data-and-Bulk-Export).
   Strava may take several days to prepare the archive.
2. Keep the ZIP in a private location. It can include account, location, and
   health data that qfit does not need.
3. In qfit, select or create the destination GeoPackage.
4. Choose **Import Strava export…**, select the ZIP, and review the preflight
   counts before confirming.
5. Leave QGIS open while the background task runs. The status area reports the
   current phase, measured progress, and estimated remaining time.

The ZIP is read in place and is not extracted. qfit allowlists
`activities.csv` and only the FIT, TCX, or GPX members referenced by that
manifest. Unreferenced photos, videos, and account files do not consume the
activity import's expanded-size limits. Saved routes in `routes.csv` are not
imported by this workflow.
The derived sampled-point and profile tables can make the destination larger
than the source ZIP. **Keep every Nth point** controls the interactive activity
point layer; the atlas profile table independently retains the aligned
distance/altitude samples needed to reopen and render profiles without the ZIP.

## Mapping and profiles

`activities.csv` supplies Strava's processed summary values. Distances are
stored in metres, durations in seconds, speed in metres per second, and
elevation in metres. Empty or unavailable values remain null. The referenced
original supplies exact coordinates and aligned time, distance, altitude,
heart-rate, cadence, power, speed, temperature, and grade arrays where those
fields exist.

The manifest's **Activity Type** is authoritative. qfit retains its display
label and maps it to the compact Strava API `sport_type` used for the canonical
route category. This keeps bulk-imported routes in the same color/style and
legend categories as activities created by daily synchronization. FIT or TCX
sport metadata is retained as provenance and is used only when the manifest
activity type is blank.

Point altitude is used for atlas profiles. The manifest's processed elevation
gain remains the canonical summary; qfit does not replace it with a gain
calculated from device samples. An activity with coordinates but no altitude is
still a detailed route, but it does not get a fabricated profile. When a track
has no distance samples, qfit deterministically calculates cumulative distance
from its coordinates.

## Re-import, cancellation, and recovery

Activities reconcile by the stable pair `(strava, Activity ID)`, not by a name
or filename. Re-importing the same archive is idempotent. A newer export updates
its matching records while retaining `first_seen_at`, unrelated local details,
and any existing geometry that is more precise than the incoming member.

The importer commits small coherent batches. Cancelling keeps those batches but
does not rebuild the visible derived layers or claim completion. Start the same
import again to resume safely; already imported activities become unchanged.
The source ZIP is no longer needed after a completed import because exact point
payloads and provenance are stored in the GeoPackage.

## Daily sync and automatic detail hydration after import

After the initial bulk import, **Sync activities** continues from the stored
checkpoint with the normal recent overlap. qfit compares those activities with
the canonical registry and updates only changed map rows. For every recent
activity returned by Strava, qfit requests its detailed route in sequence before
storing the batch. Cached details are reused. A detail request deferred by the
rate-limit guard or interrupted by a transient error remains pending and widens
a later incremental query just far enough to retry that activity.

This automatic hydration is deliberately limited to activities returned by
normal API sync. It does not turn daily sync into a historical API crawl:
historical ingestion remains the role of the user's Strava bulk export.

The QGIS task shows separate reconciliation, staging, publication, and
completion phases. An unchanged overlap skips derived publication entirely.
Safety cases that can renumber atlas pages—such as a deletion or backdated
activity—use a bounded full rebuild instead. If QGIS closes or publication
fails after storing canonical data, qfit retains a repair marker and retries
the affected activities on the next sync.

## Storage design and benchmark

The canonical summary remains in `activity_registry`. Detailed geometry and
point metrics are encoded once as canonical JSON, compressed with zlib, and
stored in `activity_detail_payloads`. Readers transparently hydrate legacy JSON
rows and compressed rows, allowing existing GeoPackages to migrate during
normal updates.

Run the reproducible synthetic benchmark with:

```bash
python3 scripts/benchmark_strava_bulk_storage.py \
  --activities 3000 --points 500 --batch-size 25
```

The benchmark reports write time, Python peak memory, database size, and full
reopen time for both layouts. It deliberately uses batches so the measured
working set represents the importer rather than a list of every decoded
activity. QGIS layer rebuild time is measured separately by the two real-QGIS
integration runs because those layers require the target QGIS/GDAL runtime.

The reference run on 2026-09-21 used 3,000 synthetic activities with 500 points
each (1.5 million aligned samples) and 25-activity batches:

| Layout | Write | Peak Python memory | Database | Full reopen |
|---|---:|---:|---:|---:|
| Registry JSON | 29.523 s | 4.49 MiB | 70.79 MiB | 1.375 s |
| `json+zlib-v1` payload | 36.331 s | 4.47 MiB | 15.56 MiB | 1.225 s |

Compression reduced the database by about 78% with the same bounded Python
working set and a slightly faster full reopen, at the cost of about 23% more
write time. That trade-off selects the compressed payload table for bulk
imports. Values are comparative rather than universal; hardware, SQLite, and
sample entropy affect absolute timings.

A recent private, 3,000-class export containing a mix of FIT, TCX, and GPX
originals was also validated end to end. Every manifest row reached a defined
result category, aligned point metrics remained intact, no referenced member
failed, and the completed GeoPackage passed SQLite integrity and derived-layer
reopen checks. The source archive and all identifying values stayed outside the
repository and public diagnostics.

## Privacy and troubleshooting

- Treat both the export and the resulting GeoPackage as sensitive personal
  data. qfit does not upload them or apply automatic expiry.
- A missing original is valid and imports as summary-only. A corrupt original
  is isolated and reported without aborting other activities.
- To bound QGIS memory use, `activities.csv` is limited to 32 MiB and a single
  expanded FIT, GPX, or TCX original is limited to 16 MiB. An oversized
  original is isolated like any other member failure; its manifest summary can
  still be imported.
- Duplicate IDs, duplicate referenced filenames, or missing referenced members
  are reported as conflicts rather than guessed.
- Unsupported members remain in the final counts but unrelated account files
  are never parsed.
- FIT support uses the pure-Python, MIT-licensed `fitdecode` 0.11.0 package,
  bundled with its license in packaged qfit builds. A source checkout needs the
  package available in its QGIS Python environment.
- The completion dialog's detailed text is a copyable private diagnostic report
  containing row numbers, activity IDs, status categories, and safe reason
  codes. It excludes activity names, coordinates, archive paths, and raw parser
  exceptions.
