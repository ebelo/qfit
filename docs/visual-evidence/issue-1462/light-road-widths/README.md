# Light source-width hierarchy — C04/C11/C12 (#1462)

Captured 2026-09-14. Baseline `8b5e661e54a5b84661e3a46eab4f79eef13b96f4`; retained implementation `964710365c54f7cfaead3170fe43d505fa33d856`.
Panels are **Mapbox reference | QGIS before | QGIS after**, never cross-runtime controls.
Source SHA256 `87413e46c074e13aef420958a3ad101961766e6645336608e399ceccaffc6d32`. Map data © OpenStreetMap contributors;
reference cartography © Mapbox. All assets are sanitized; no tile credentials or payloads.

## Mechanism and decision

The four source owners `road-simple`, `tunnel-simple`, `bridge-simple` and
`bridge-case-simple` use class-dependent widths with base-1.5 zoom interpolation.
Generic simplification collapses cores to0.635 and casing to0.9525; the converter
then interprets these already-mm numbers as pixels. Result: fixed native core
width0.168010mm and casing0.252016mm across class/zoom. The adapter restores only
these audited widths using native QGIS data-defined expressions, correct endpoint
clamping and one pixel-to-mm conversion. No source filters, layer order, other
paint, source fields, labels, fonts, geometry, activity colors or generic JSON
preprocessing changes. Existing data-defined native widths are preserved.

Retain the portable arithmetic implementation. The native-converter-only
candidate `a01f1886e449d4be7e730e13ba23884bb42250e0` from the earlier interrupted run is **rejected**, despite historical modern-image
improvements:126 of448 host QGIS3.34 cases failed because equal expression endpoints
omit the unit multiplier. [QGIS3.34 implementation](https://github.com/qgis/QGIS/blob/final-3_34_4/src/core/vectortile/qgsmapboxglstyleconverter.cpp#L2860).
[QGIS3.28](https://github.com/qgis/QGIS/blob/final-3_28_15/src/core/vectortile/qgsmapboxglstyleconverter.cpp#L2897)
also uses exponent interpolation instead of Mapbox's base. The retained expression
uses basic CASE/arithmetic, not a version cutoff or artificial near-equal stop.

## Scope and independent dimensions

- **Semantics:** 448 native cases per tested runtime verify source class-width
  groups, unknown/NULL fallback, exponential interpolation, low/high endpoint
  clamping and exact one-time units. Test tolerance1e-10mm. QGIS3.34.4,3.44.11,4.2.0;
  QGIS3.28 source/API inspection is not an additional native test lane.
- **Usability:** matched whole maps/detail crops show restored visible street
  networks in Geneva14 and road-width hierarchy in Bern12/Zurich17/Geneva18.
  This is not a complete network/topology/crossing or cartographic-usability pass.
- **Fidelity:** Geneva14 and the street cameras improve substantially; Zurich8
  has a small repeatable MAE regression, disclosed below. No metric can excuse
  source-semantic loss. The regional trade-off is not control noise or an accepted
  holistic renderer limitation; broader reference fidelity remains open.
- **Operation:** all30 unchanged PNG repeats are byte-identical, and full label
  inventories, actual native camera context, filters and other stroke paint are
  identical in every pair. Native expressions request the class field. Both font-
  enabled Docker runtimes use verified Noto/Barlow faces as recorded per label.
  This is headless PNG plus native-expression testing, not Windows/macOS/PDF proof.

15 cameras x2 runtimes: seven Light presets, Geneva/Bern at requested12.9/13/13.1,
plus diagnostic Run/Ride/Hike overlays on Geneva14/Bern12. See manifest for exact
preset zooms (camera names are approximate), extents, DPI, scale, native continuous/
render/fetch zoom, image size and font/runtime identities. QGIS3 uses100 map DPI;
QGIS4 uses96. Within-runtime before/after context matches; requested browser zoom
is **not** native style zoom. Triplet PNGs do not certify calibrated boundary
alignment or interactive continuity. C01/C23 remain OPEN.

The overlay fixtures use qfit's production activity renderer on synthetic routes,
not real activity data or UI state. Inspect the complete maps for each category;
real dense/shared routes, selection/start/end/direction, accessibility and actual
canvas/export paths remain unassessed. No C25/C26 criterion-wide pass is claimed.

Upstream tiles are live and not archived; these same-run controls and pinned style
are not a future-data guarantee or complete renderer request trace. C15 boundary
status/owner, topology/seams, broader label/content/RTL, other class/zoom contracts,
accessibility, desktop/packaged-font/PDF and complete user-facing map context remain
open. No limitation is accepted on Emman's behalf. One retained slice does not
complete #1462.

## Transition details

[Geneva QGIS3](geneva-qgis3-transitions.png) · [Geneva QGIS4](geneva-qgis4-transitions.png) ·
[Bern QGIS3](bern-qgis3-transitions.png) · [Bern QGIS4](bern-qgis4-transitions.png).
These are reference/retained z12.9/13/13.1 crops, not before/after or calibrated
source/native-boundary certification. Existing settlement-label eligibility
mismatch remains visible and is unchanged.

## Metrics and full maps

Negative MAE movement is closer to the reference, not a holistic pass.

| Camera | QGIS | MAE movement | Reference | Before | After |
| --- | --- | --- | --- | --- | --- |
| switzerland-alps-z5-light | 3 | -0.095% | [reference](switzerland-alps-z5-light-reference.png) | [before](qgis3-switzerland-alps-z5-light-before.png) | [after](qgis3-switzerland-alps-z5-light-after.png) |
| zurich-region-z8-light | 3 | +1.335% | [reference](zurich-region-z8-light-reference.png) | [before](qgis3-zurich-region-z8-light-before.png) | [after](qgis3-zurich-region-z8-light-after.png) |
| lausanne-lavaux-z10-light | 3 | -0.474% | [reference](lausanne-lavaux-z10-light-reference.png) | [before](qgis3-lausanne-lavaux-z10-light-before.png) | [after](qgis3-lausanne-lavaux-z10-light-after.png) |
| bern-urban-z12-light | 3 | -5.249% | [reference](bern-urban-z12-light-reference.png) | [before](qgis3-bern-urban-z12-light-before.png) | [after](qgis3-bern-urban-z12-light-after.png) |
| geneva-urban-z14-light | 3 | -12.874% | [reference](geneva-urban-z14-light-reference.png) | [before](qgis3-geneva-urban-z14-light-before.png) | [after](qgis3-geneva-urban-z14-light-after.png) |
| zurich-streets-z17-light | 3 | -20.273% | [reference](zurich-streets-z17-light-reference.png) | [before](qgis3-zurich-streets-z17-light-before.png) | [after](qgis3-zurich-streets-z17-light-after.png) |
| geneva-streets-z18-light | 3 | -12.718% | [reference](geneva-streets-z18-light-reference.png) | [before](qgis3-geneva-streets-z18-light-before.png) | [after](qgis3-geneva-streets-z18-light-after.png) |
| geneva-width-z12.9 | 3 | -7.551% | [reference](geneva-width-z12.9-reference.png) | [before](qgis3-geneva-width-z12.9-before.png) | [after](qgis3-geneva-width-z12.9-after.png) |
| geneva-width-z13.0 | 3 | -8.059% | [reference](geneva-width-z13.0-reference.png) | [before](qgis3-geneva-width-z13.0-before.png) | [after](qgis3-geneva-width-z13.0-after.png) |
| geneva-width-z13.1 | 3 | -9.100% | [reference](geneva-width-z13.1-reference.png) | [before](qgis3-geneva-width-z13.1-before.png) | [after](qgis3-geneva-width-z13.1-after.png) |
| bern-width-z12.9 | 3 | -5.358% | [reference](bern-width-z12.9-reference.png) | [before](qgis3-bern-width-z12.9-before.png) | [after](qgis3-bern-width-z12.9-after.png) |
| bern-width-z13.0 | 3 | -5.134% | [reference](bern-width-z13.0-reference.png) | [before](qgis3-bern-width-z13.0-before.png) | [after](qgis3-bern-width-z13.0-after.png) |
| bern-width-z13.1 | 3 | -5.481% | [reference](bern-width-z13.1-reference.png) | [before](qgis3-bern-width-z13.1-before.png) | [after](qgis3-bern-width-z13.1-after.png) |
| geneva-urban-z14-light-activity | 3 | -10.332% | [reference](geneva-urban-z14-light-activity-reference.png) | [before](qgis3-geneva-urban-z14-light-activity-before.png) | [after](qgis3-geneva-urban-z14-light-activity-after.png) |
| bern-urban-z12-light-activity | 3 | -3.746% | [reference](bern-urban-z12-light-activity-reference.png) | [before](qgis3-bern-urban-z12-light-activity-before.png) | [after](qgis3-bern-urban-z12-light-activity-after.png) |
| switzerland-alps-z5-light | 4 | -0.070% | [reference](switzerland-alps-z5-light-reference.png) | [before](qgis4-switzerland-alps-z5-light-before.png) | [after](qgis4-switzerland-alps-z5-light-after.png) |
| zurich-region-z8-light | 4 | +1.217% | [reference](zurich-region-z8-light-reference.png) | [before](qgis4-zurich-region-z8-light-before.png) | [after](qgis4-zurich-region-z8-light-after.png) |
| lausanne-lavaux-z10-light | 4 | -0.581% | [reference](lausanne-lavaux-z10-light-reference.png) | [before](qgis4-lausanne-lavaux-z10-light-before.png) | [after](qgis4-lausanne-lavaux-z10-light-after.png) |
| bern-urban-z12-light | 4 | -5.410% | [reference](bern-urban-z12-light-reference.png) | [before](qgis4-bern-urban-z12-light-before.png) | [after](qgis4-bern-urban-z12-light-after.png) |
| geneva-urban-z14-light | 4 | -12.862% | [reference](geneva-urban-z14-light-reference.png) | [before](qgis4-geneva-urban-z14-light-before.png) | [after](qgis4-geneva-urban-z14-light-after.png) |
| zurich-streets-z17-light | 4 | -20.142% | [reference](zurich-streets-z17-light-reference.png) | [before](qgis4-zurich-streets-z17-light-before.png) | [after](qgis4-zurich-streets-z17-light-after.png) |
| geneva-streets-z18-light | 4 | -12.544% | [reference](geneva-streets-z18-light-reference.png) | [before](qgis4-geneva-streets-z18-light-before.png) | [after](qgis4-geneva-streets-z18-light-after.png) |
| geneva-width-z12.9 | 4 | -7.974% | [reference](geneva-width-z12.9-reference.png) | [before](qgis4-geneva-width-z12.9-before.png) | [after](qgis4-geneva-width-z12.9-after.png) |
| geneva-width-z13.0 | 4 | -8.447% | [reference](geneva-width-z13.0-reference.png) | [before](qgis4-geneva-width-z13.0-before.png) | [after](qgis4-geneva-width-z13.0-after.png) |
| geneva-width-z13.1 | 4 | -9.927% | [reference](geneva-width-z13.1-reference.png) | [before](qgis4-geneva-width-z13.1-before.png) | [after](qgis4-geneva-width-z13.1-after.png) |
| bern-width-z12.9 | 4 | -5.592% | [reference](bern-width-z12.9-reference.png) | [before](qgis4-bern-width-z12.9-before.png) | [after](qgis4-bern-width-z12.9-after.png) |
| bern-width-z13.0 | 4 | -5.368% | [reference](bern-width-z13.0-reference.png) | [before](qgis4-bern-width-z13.0-before.png) | [after](qgis4-bern-width-z13.0-after.png) |
| bern-width-z13.1 | 4 | -5.479% | [reference](bern-width-z13.1-reference.png) | [before](qgis4-bern-width-z13.1-before.png) | [after](qgis4-bern-width-z13.1-after.png) |
| geneva-urban-z14-light-activity | 4 | -10.965% | [reference](geneva-urban-z14-light-activity-reference.png) | [before](qgis4-geneva-urban-z14-light-activity-before.png) | [after](qgis4-geneva-urban-z14-light-activity-after.png) |
| bern-urban-z12-light-activity | 4 | -4.271% | [reference](bern-urban-z12-light-activity-reference.png) | [before](qgis4-bern-urban-z12-light-activity-before.png) | [after](qgis4-bern-urban-z12-light-activity-after.png) |
