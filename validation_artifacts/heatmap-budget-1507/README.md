# Occupied heatmap budget regression evidence

Synthetic routes only; no private activity data, basemap or credentials.

Baseline: `fc7ff368eebafc01ae2e407c5cf256156e47dc21`.
Candidate captures: `6efc9685835052018a259a972c55c30eed64e8bf`.
Final reviewed head: `04a7e87ab3d9ae0e1886965aa3cb6b9f1e550b7f` (only additional rollback test; production and capture code identical).

## Matched visual controls

QGIS 3.44.11 / QGIS 4.2.0, same 30 generated routes, EPSG:32632,
1000 x 650 pixels, measured runtime defaults: QGIS 3 at 100 DPI, QGIS 4 at 96 DPI, neutral background. Regional/town/detail
cameras with two repeated captures per role. All before/after/repeat PNG hashes
match within each runtime/camera. Inspect the manifests for exact extents and
non-background pixel counts. This is preserved appearance, not a styling change.

`python3 scripts/validate_route_heatmap.py --baseline /evidence/baseline.py
--baseline-commit fc7ff368eebafc01ae2e407c5cf256156e47dc21 --output ...
--commit ... --runtime qgis3` (or qgis4). The baseline facade loads the baseline
raster module from `git show` under the infrastructure package and uses its
original builder with a separate cache; projection and renderer are unchanged.

## Large sparse regression

457 separated cell-centred routes, 10 m cells, 20 m sigma, **32-cell test tiles**
(cheap integration fixture; production still uses 256). The original algorithm
creates 4,113 candidates and throws its unchanged error; the candidate produces
457 non-empty tiles. Real-QGIS tests also build the complete GeoPackage/cache/
VRT/layer, verify the source is unchanged and exercise cache reuse.

The timing control in each `*-sparse-benchmark.json` **bypasses only the old
candidate limit** to compare output against the baseline smoothing algorithm.
This is a diagnostic control, not an offered workaround or successful original
build. All 457 physical tile pixel arrays and global maxima match. Timings are
single synthetic observations under simultaneous container load, not a general
performance guarantee. Normal cold/warm build timings are in the render manifests.

Remaining limit: 4,096 occupied input tiles and 4,096 non-empty output tiles.
No view-dependent coarsening, changed colour fit, cache invalidation or source
GeoPackage mutation. Antimeridian handling, projection distortion and cache
quota remain unchanged limitations. PNG/headless Docker evidence is not a claim
of a new Windows deployment or PDF verification.
