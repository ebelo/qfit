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
  the fixed-grid pixel edges.
- Run again after changing filters or importing/changing tracks. Computation runs
  in a cancellable background task; the button becomes **Cancel heatmap**.
  The previous result remains until a successful replacement. Changed selections
  or database revisions discard stale completions.
- Identical selected identities/geometries reuse the disk cache. Renaming an
  activity alone does not change its density cache key (a name search may change
  the matching selection). A cache hit still reads selected tracks and verifies
  cached file hashes; it is not a zero-I/O operation.

## Performance and limits

qfit uses origin-aligned 256×256 tiles and bounded per-activity cell sets rather
than one dense array covering empty space between distant regions. The single
QGIS layer is a VRT over compressed GeoTIFFs; peak-preserving overviews keep
narrow corridors visible when zoomed out. NumPy and GDAL come with supported
QGIS runtimes; qfit does not bundle its own copies.

Regional selections use a local UTM grid. Wide/global selections use EPSG:3857,
whose map metres distort ground distances at high latitudes. This version is
not a geodesic/global heatmap and does not unwrap antimeridian-crossing tracks.
Very large selections are bounded at 4,096 tiles (including smoothing neighbours)
and two million cells per activity; narrow filters if a budget error is shown.
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
