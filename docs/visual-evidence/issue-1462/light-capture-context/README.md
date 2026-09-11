# Light capture-context audit — C01/C02/C23 (#1462)

Baseline `70fd68dd690035e9bdb43e8d9c87f434a0946070`; metadata-only implementation `a77845c0115eec7806d10c6870066f24a491e0c3`.
**No production renderer or style change is retained.** All three rendering
candidates were reverted before this change. This is baseline audit evidence,
not a before/after cartographic improvement.

## Verified scope

19 cameras: seven standard Light views plus Geneva/Bern at z12.9/13/13.1 and
z13.9/14/14.1. Both font-enabled Docker runtimes; 1280×900, EPSG:3857. All 38
unchanged control repeats, all 38 final metadata-head PNGs and their complete
label inventories are byte-identical to their matched baseline. New metadata
is captured from the actual map settings, image and tile matrix after successful
PNG rendering; it does not change DPI, extent, scale or any style.

**QGIS 3.44.11 uses 100 map-settings DPI here; QGIS 4.2.0 uses 96.** Both images
have device pixel ratio 1. Embedded PNG density is recorded separately and has
integer pixels-per-metre quantization. Earlier C19 manifests hardcoded 96 for
both; the immutable historical PNGs themselves encode approximately 99.9744 DPI
(QGIS3) and 95.9866 DPI (QGIS4). The manifest includes those file hashes and a
correction without rewriting historical evidence or invalidating its matched
same-runtime name-fallback results.

Requested Mapbox camera zoom, continuous QGIS `vector_tile_zoom`, rounded native
render zoom and matrix-clamped fetch zoom are separate quantities. Values for
every camera are in the manifest. Do not claim source boundary equivalence from
a native expression test with a manually injected requested camera zoom.

## Rejected hypotheses

1. **All major rank stops** (`399e93e`): source major/minor ranks are complementary,
   but qfit restricts the major owner to cities and the minor owner to towns.
   The broad repair removes source-valid Munich/Milan and other low-zoom labels.
   Lower MAE does not compensate; QGIS4 Zurich also worsens. Live tile samples
   identify Munich rank 8, Milan rank 7, type city, filterrank 1. They belong to
   the minor source owner at z5.35, whose qfit city exclusion remains open.
2. **Static z13/z14 bands** (`1fcda07`): QGIS rounds its native integer rule zoom.
   The completed QGIS3 z12.9 probe switches early and removes Geneva prematurely.
   The remaining queued integer-band captures were deliberately stopped; only
   completed artifacts are listed, never counted as a valid full matrix.
3. **Fractional native predicate** (`2113bdd`): avoids that early switch, but does
   not align native zoom to the requested source camera boundary. QGIS3 Geneva
   z13 still has native zoom about 12.8976 and the extra city label survives.
   Geneva/Bern source features are rank 9 in sampled z12–z15 tiles; source major
   labels reject them at z13, and the minor source owner ends at z13. This is
   not placement noise or an accepted renderer limitation.

Upstream mechanics: [QGIS tile zoom conversion](https://github.com/qgis/QGIS/blob/final-3_44_11/src/core/qgstiles.cpp)
rounds MapBox integer zooms and interpolates continuous zoom in scale space;
[renderer variables](https://github.com/qgis/QGIS/blob/final-3_44_11/src/core/vectortile/qgsvectortilelayerrenderer.cpp)
use that matrix calculation. The fractional variable also exists in 3.34.4 and
4.2.0. No source-rank correction is ready until camera/native-scale alignment and
major/minor handoff are handled together in their appropriate scopes.

## Remaining work

C01 comparability is OPEN: this patch measures mismatches, not normalizes them.
C02 source-role eligibility and C23 actual transition behavior remain OPEN.
Source layer outer min/max zooms, other role/filter/size transitions, pan/zoom,
seams, activity/accessibility, desktop and PDF coverage remain unvalidated.
The seven-camera road-hierarchy and boundary-owner findings are unchanged.
No limitation is accepted on Emman's behalf. Tile payloads were not archived;
selected anchor samples are not a full geometry/renderer-request trace.

Map data © OpenStreetMap contributors; reference cartography © Mapbox.

## Full maps (runtime comparison, not Before/After)

| Camera | Reference | QGIS 3 baseline | QGIS 4 baseline |
| --- | --- | --- | --- |
| switzerland-alps-z5-light | [reference](switzerland-alps-z5-light-reference.png) | [QGIS3](qgis3-switzerland-alps-z5-light.png) | [QGIS4](qgis4-switzerland-alps-z5-light.png) |
| zurich-region-z8-light | [reference](zurich-region-z8-light-reference.png) | [QGIS3](qgis3-zurich-region-z8-light.png) | [QGIS4](qgis4-zurich-region-z8-light.png) |
| lausanne-lavaux-z10-light | [reference](lausanne-lavaux-z10-light-reference.png) | [QGIS3](qgis3-lausanne-lavaux-z10-light.png) | [QGIS4](qgis4-lausanne-lavaux-z10-light.png) |
| bern-urban-z12-light | [reference](bern-urban-z12-light-reference.png) | [QGIS3](qgis3-bern-urban-z12-light.png) | [QGIS4](qgis4-bern-urban-z12-light.png) |
| geneva-urban-z14-light | [reference](geneva-urban-z14-light-reference.png) | [QGIS3](qgis3-geneva-urban-z14-light.png) | [QGIS4](qgis4-geneva-urban-z14-light.png) |
| zurich-streets-z17-light | [reference](zurich-streets-z17-light-reference.png) | [QGIS3](qgis3-zurich-streets-z17-light.png) | [QGIS4](qgis4-zurich-streets-z17-light.png) |
| geneva-streets-z18-light | [reference](geneva-streets-z18-light-reference.png) | [QGIS3](qgis3-geneva-streets-z18-light.png) | [QGIS4](qgis4-geneva-streets-z18-light.png) |
| geneva-rank-z12.9 | [reference](geneva-rank-z12.9-reference.png) | [QGIS3](qgis3-geneva-rank-z12.9.png) | [QGIS4](qgis4-geneva-rank-z12.9.png) |
| geneva-rank-z13.0 | [reference](geneva-rank-z13.0-reference.png) | [QGIS3](qgis3-geneva-rank-z13.0.png) | [QGIS4](qgis4-geneva-rank-z13.0.png) |
| geneva-rank-z13.1 | [reference](geneva-rank-z13.1-reference.png) | [QGIS3](qgis3-geneva-rank-z13.1.png) | [QGIS4](qgis4-geneva-rank-z13.1.png) |
| geneva-rank-z13.9 | [reference](geneva-rank-z13.9-reference.png) | [QGIS3](qgis3-geneva-rank-z13.9.png) | [QGIS4](qgis4-geneva-rank-z13.9.png) |
| geneva-rank-z14.0 | [reference](geneva-rank-z14.0-reference.png) | [QGIS3](qgis3-geneva-rank-z14.0.png) | [QGIS4](qgis4-geneva-rank-z14.0.png) |
| geneva-rank-z14.1 | [reference](geneva-rank-z14.1-reference.png) | [QGIS3](qgis3-geneva-rank-z14.1.png) | [QGIS4](qgis4-geneva-rank-z14.1.png) |
| bern-rank-z12.9 | [reference](bern-rank-z12.9-reference.png) | [QGIS3](qgis3-bern-rank-z12.9.png) | [QGIS4](qgis4-bern-rank-z12.9.png) |
| bern-rank-z13.0 | [reference](bern-rank-z13.0-reference.png) | [QGIS3](qgis3-bern-rank-z13.0.png) | [QGIS4](qgis4-bern-rank-z13.0.png) |
| bern-rank-z13.1 | [reference](bern-rank-z13.1-reference.png) | [QGIS3](qgis3-bern-rank-z13.1.png) | [QGIS4](qgis4-bern-rank-z13.1.png) |
| bern-rank-z13.9 | [reference](bern-rank-z13.9-reference.png) | [QGIS3](qgis3-bern-rank-z13.9.png) | [QGIS4](qgis4-bern-rank-z13.9.png) |
| bern-rank-z14.0 | [reference](bern-rank-z14.0-reference.png) | [QGIS3](qgis3-bern-rank-z14.0.png) | [QGIS4](qgis4-bern-rank-z14.0.png) |
| bern-rank-z14.1 | [reference](bern-rank-z14.1-reference.png) | [QGIS3](qgis3-bern-rank-z14.1.png) | [QGIS4](qgis4-bern-rank-z14.1.png) |
