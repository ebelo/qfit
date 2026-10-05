# Static red route heatmap

In **Analysis → Heatmap**, run analysis after choosing your activity filters.
qfit produces **one raster layer** for all matching stored `activity_tracks`.
“Selected” means the Data-page activity query (dates, type, distance, search and
route availability), not selected QGIS features or the visible map extent.

## Appearance and behaviour

- Transparent-to-red/crimson route corridors; darker overlap means more activities
  used that corridor. This is **route usage**, not time spent or GPS sample density.
- One activity contributes once per crossed cell, including repeated/reversed
  segments and multipart overlaps. Sampled `activity_points` are not required.
- Fixed 10 m grid and 20 m Gaussian smoothing. Counts and the globally fitted
  colour range are computed once for the complete selection.
- Pan, zoom, source-layer visibility and canvas clipping never rebuild the density
  or refit its colour range. Pixel resampling still changes with scale; bilinear zoom-in resampling softens
  the fixed-grid pixel edges. Global non-nodata raster statistics are recorded
  during the background tile build, avoiding a default UI-thread statistics scan
  over the sparse mosaic and keeping VRT checksums stable on layer closure.
- Run again after changing filters or importing/changing tracks. Computation runs
  in a cancellable background task; the button becomes **Cancel heatmap**.
  The previous result remains until a successful replacement. Changed selections
  or database revisions discard stale completions.
- Identical selected identities/geometries reuse the disk cache. Renaming an
  activity alone does not change its density cache key (a name search may change
  the matching selection). A cache hit still reads selected tracks and verifies
  cached file hashes and a separate manifest checksum; it is not a zero-I/O
  operation. Publication/repair is serialized per cache key across QGIS sessions.
  Repairs publish a new generation without removing files held by an existing
  QGIS layer or saved project. Cancelling a worker keeps its task reservation
  until completion, so rapid analysis changes cannot overlap heatmap workers.
  Tiny lock files remain in the cache; the operating system releases locks when
  a worker/process exits. Waiting for publication is cancellable and time-limited.

## Performance and limits

qfit uses origin-aligned 256×256 tiles and bounded per-activity cell sets rather
than one dense array covering empty space between distant regions. The single
QGIS layer is a VRT over compressed GeoTIFFs; peak-preserving overviews keep
narrow corridors visible when zoomed out. NumPy and GDAL come with supported
QGIS runtimes; qfit does not bundle its own copies.

Smoothing visits only neighbours reached by occupied edge/corner cells. It reads
the required neighbour strips into a tile-plus-halo buffer, not nine full tiles.
Large sparse selections therefore avoid smoothing and writing empty surrounding
tiles. This optimization does not coarsen the grid or change density values.

Regional selections use a local UTM grid. Wide/global selections use EPSG:3857,
whose map metres distort ground distances at high latitudes. This version is
not a geodesic/global heatmap and does not unwrap antimeridian-crossing tracks.
Very large selections are bounded at 4,096 occupied count tiles and 4,096
**non-empty density output tiles**, plus two million cells per activity. Empty
potential smoothing neighbours do not consume the output budget. A selection
whose actual density exceeds that limit still requires narrower filters; qfit
never silently reduces resolution based on selection size or the map view.
Single-vertex/no-line tracks cannot contribute. Bad geometry fails the build
without modifying the stored tracks or replacing the previous heatmap.

Cached rasters live in qfit's application cache (`route-heatmaps`), **not inside
or alongside your GeoPackage**. Each selection/geometry/parameter revision has
an immutable cache directory. There is currently no automatic quota/eviction;
old selections use disk space until the cache is cleared. Do not remove a cache
in use by an open QGIS project. Saved projects reference those cache files and
are not portable without them; regenerate the heatmap after moving machines.

## Architecture and verification

- `analysis/domain/route_density.py`: grid traversal and once-per-activity visits.
- `analysis/application/route_heatmap.py`: immutable query/artifact contracts and
  geometry fingerprints; no QGIS dependencies.
- `analysis/infrastructure/route_heatmap_source.py`: read-only WAL-aware snapshot
  and projection. The database read transaction ends before raster computation.
- `route_heatmap_raster.py`, `route_heatmap_task.py`, `route_heatmap_layer.py`:
  disk tiles/cache, cancellable QGIS worker and fixed raster renderer.

Pure tests cover counts, filters, cancellation, storage/cache and adapter failure
paths. Required real-QGIS lanes exercise GeoPackage/GDAL output, tile seams,
sparse separated regions, immutable rendering and live dock task callbacks.
`scripts/validate_route_heatmap.py` captures matched synthetic baseline/candidate
renders and cold/warm timings; no personal routes or Mapbox credentials are used.
