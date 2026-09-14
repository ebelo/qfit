# Light ordinary national boundary — C12/C15 (#1462)

Captured 2026-09-14. Baseline `2985c8247eb05490dd4d26936c3b003a17a1de4d`; retained implementation `5ebb6ead8740c63971b273f278726aad9b399021`.
Panels are **Mapbox reference | QGIS before | QGIS after** unless explicitly labelled
as owner-removal diagnostics. All detail crops are unscaled; links below provide
complete map context. Map data © OpenStreetMap contributors; reference cartography © Mapbox.

## Source-backed attribution and mechanism

Source SHA256 `87413e46c074e13aef420958a3ad101961766e6645336608e399ceccaffc6d32`. Fresh browser
`queryRenderedFeatures` snapshots and independent QGIS rule-removal renders attribute
the Lake Geneva line to `admin-0-boundary`, with its existing background. Visible
CH–FR features have admin_level=0, disputed="false", maritime="false", worldview="all".
Removing the disputed-boundary rule is byte-identical in both attribution extents
and runtimes. No status/worldview filter was removed, weakened or reassigned.
These are visible-feature facts, not a statement about international boundary policy.

The source ordinary national line is continuous (`line-dasharray: [10, 0]`) and
interpolates linearly from0.65px atz3 to2.6px atz12, clamped outside that interval.
Generic preprocessing collapses the width and converts it to millimetres; native
conversion treats the resulting number as pixels again, yielding0.182011mm.
The native zero-gap custom pattern at that width visibly breaks the lake line.
Actual native horizontal-stroke regressions reproduce the gaps in QGIS3.34,
3.44 and4.2. The adapter restores that exact owner's source width with portable
CASE arithmetic and one px/mm conversion, and renders its zero-gap texture as a
solid pen. No invented gap, political classification or color change is introduced.

Existing active native properties, custom native patterns/units/symbol types,
changed source contracts and non-Light styles retain their old conversion.
All five boundary rules retain their filters, ordering, min/max zoom, colors,
backgrounds and other paint. Disputed/subdivision widths, dashes, opacity/blur and
other broader boundary mechanisms remain OPEN, not silently normalized here.

## Independent dimensions and scope

- **Semantics:** target source width/solid texture and72 native status/worldview
  combinations pass per runtime. All five source-owner fixtures match the fresh
  source. No actual disputed/coastal/worldview-specific map fixture is certified.
- **Usability:** the ordinary national border is continuous and readable on Lake
  Geneva and the Zurich-region border network. Full maps preserve the existing
  label/road population. This is not a criterion-wide cartographic hierarchy pass.
- **Fidelity:** per-camera before/after MAE is below; small differences between
  valid source-width-only and explicit-solid probes are not control noise. Retain
  source semantics, not a pixel-score-only preference. Invalid initial width probes
  used unsupported least/greatest functions and are excluded as width evidence.
- **Operation:**24 unchanged controls, complete label inventories and actual native
  contexts are byte-identical within their matched pairs. Tests cover native3.34,
  Docker3.44/Qt5 and4.2/Qt6. Both ZIPs built and9 package checks pass; no new fonts
  bundled and no desktop deployment or PDF output claimed.

12 cameras x2 runtimes: seven Light presets, Lausanne requested11.9/12/12.1,
and two synthetic Run/Ride/Hike overlays. Camera identifiers abbreviate zoom;
use the manifest's actual values. The transition references contain the affected
boundary; they are static views, not an interactive or calibrated source/native
zoom-equivalence pass. QGIS3 map DPI100 and QGIS4 DPI96 are recorded separately.
C01 scale alignment remains OPEN. Upstream tiles are live and not archived.

Both Docker suites pass211/82; full local2668/186; native focused boundary test
passes88 subcases; adapter local statement coverage100%; both ZIPs and9 package
checks pass. These are scoped gates, not C01–C30 completion. No limitation is
accepted on Emman's behalf. Other boundaries, role-handoff/RTL/label, topology,
seam, accessibility, real activity/UI, desktop/packaged-font/PDF and map-context
coverage remain open where recorded in the repository ledger.

## Projection diagnostic: overview guardrail

The source explicitly requests globe. Actual Mapbox `getProjection()` confirms
this, and repeated original-globe references are byte-identical to the initial
source reference. The Geneva/Paris/Vienna anchors differ from QGIS's measured
Mercator placement by1.77/18.44/29.73 pixels. Thus the original overview errors
(+2.440%/+2.510%) do not constitute a projection-matched fidelity comparison.

An explicit **diagnostic-only Mapbox Mercator camera override** leaves the
original source snapshot and both QGIS outputs unchanged. Two repeated browser
Mercator controls are byte-identical; all three independently transformed native
anchors align within1e-6 pixels. The aligned overview MAE improves **3.967%/4.328%**
in QGIS3/4. [Measured anchors, actual camera/projection, hashes and metrics](projection-diagnostic.json).
[QGIS3 aligned full comparison](projection-matched-mercator-qgis3-full.png) ·
[QGIS4 aligned full comparison](projection-matched-mercator-qgis4-full.png).

Retain the original globe and aligned Mercator evidence separately. This is
geometric registration for one diagnostic camera, not automatic acceptance of
losing a requested globe projection, a production harness fix, or a fullC01 pass.
Native style zoom/DPI and other output/interactive scopes remain OPEN.

## Matched native maps and original-source reference metrics

Negative movement means closer aggregate RGB error, not a holistic pass.
The overview source reference is globe/unaligned; use the planar diagnostic above
for its projection-aligned comparison. All native before/after contexts match.

| Camera | QGIS | MAE movement | Reference | Before | After |
| --- | --- | --- | --- | --- | --- |
| switzerland-alps-z5-light | 3 | +2.440% | [reference](switzerland-alps-z5-light-reference.png) | [before](qgis3-switzerland-alps-z5-light-before.png) | [after](qgis3-switzerland-alps-z5-light-after.png) |
| zurich-region-z8-light | 3 | -3.862% | [reference](zurich-region-z8-light-reference.png) | [before](qgis3-zurich-region-z8-light-before.png) | [after](qgis3-zurich-region-z8-light-after.png) |
| lausanne-lavaux-z10-light | 3 | -4.113% | [reference](lausanne-lavaux-z10-light-reference.png) | [before](qgis3-lausanne-lavaux-z10-light-before.png) | [after](qgis3-lausanne-lavaux-z10-light-after.png) |
| bern-urban-z12-light | 3 | +0.000% | [reference](bern-urban-z12-light-reference.png) | [before](qgis3-bern-urban-z12-light-before.png) | [after](qgis3-bern-urban-z12-light-after.png) |
| geneva-urban-z14-light | 3 | +0.000% | [reference](geneva-urban-z14-light-reference.png) | [before](qgis3-geneva-urban-z14-light-before.png) | [after](qgis3-geneva-urban-z14-light-after.png) |
| zurich-streets-z17-light | 3 | +0.000% | [reference](zurich-streets-z17-light-reference.png) | [before](qgis3-zurich-streets-z17-light-before.png) | [after](qgis3-zurich-streets-z17-light-after.png) |
| geneva-streets-z18-light | 3 | +0.000% | [reference](geneva-streets-z18-light-reference.png) | [before](qgis3-geneva-streets-z18-light-before.png) | [after](qgis3-geneva-streets-z18-light-after.png) |
| lausanne-boundary-z11.9 | 3 | -6.572% | [reference](lausanne-boundary-z11.9-reference.png) | [before](qgis3-lausanne-boundary-z11.9-before.png) | [after](qgis3-lausanne-boundary-z11.9-after.png) |
| lausanne-boundary-z12.0 | 3 | -5.426% | [reference](lausanne-boundary-z12.0-reference.png) | [before](qgis3-lausanne-boundary-z12.0-before.png) | [after](qgis3-lausanne-boundary-z12.0-after.png) |
| lausanne-boundary-z12.1 | 3 | -4.984% | [reference](lausanne-boundary-z12.1-reference.png) | [before](qgis3-lausanne-boundary-z12.1-before.png) | [after](qgis3-lausanne-boundary-z12.1-after.png) |
| lausanne-lavaux-z10-light-activity | 3 | -3.180% | [reference](lausanne-lavaux-z10-light-activity-reference.png) | [before](qgis3-lausanne-lavaux-z10-light-activity-before.png) | [after](qgis3-lausanne-lavaux-z10-light-activity-after.png) |
| zurich-region-z8-light-activity | 3 | -3.354% | [reference](zurich-region-z8-light-activity-reference.png) | [before](qgis3-zurich-region-z8-light-activity-before.png) | [after](qgis3-zurich-region-z8-light-activity-after.png) |
| switzerland-alps-z5-light | 4 | +2.510% | [reference](switzerland-alps-z5-light-reference.png) | [before](qgis4-switzerland-alps-z5-light-before.png) | [after](qgis4-switzerland-alps-z5-light-after.png) |
| zurich-region-z8-light | 4 | -3.880% | [reference](zurich-region-z8-light-reference.png) | [before](qgis4-zurich-region-z8-light-before.png) | [after](qgis4-zurich-region-z8-light-after.png) |
| lausanne-lavaux-z10-light | 4 | -3.923% | [reference](lausanne-lavaux-z10-light-reference.png) | [before](qgis4-lausanne-lavaux-z10-light-before.png) | [after](qgis4-lausanne-lavaux-z10-light-after.png) |
| bern-urban-z12-light | 4 | +0.000% | [reference](bern-urban-z12-light-reference.png) | [before](qgis4-bern-urban-z12-light-before.png) | [after](qgis4-bern-urban-z12-light-after.png) |
| geneva-urban-z14-light | 4 | +0.000% | [reference](geneva-urban-z14-light-reference.png) | [before](qgis4-geneva-urban-z14-light-before.png) | [after](qgis4-geneva-urban-z14-light-after.png) |
| zurich-streets-z17-light | 4 | +0.000% | [reference](zurich-streets-z17-light-reference.png) | [before](qgis4-zurich-streets-z17-light-before.png) | [after](qgis4-zurich-streets-z17-light-after.png) |
| geneva-streets-z18-light | 4 | +0.000% | [reference](geneva-streets-z18-light-reference.png) | [before](qgis4-geneva-streets-z18-light-before.png) | [after](qgis4-geneva-streets-z18-light-after.png) |
| lausanne-boundary-z11.9 | 4 | -5.774% | [reference](lausanne-boundary-z11.9-reference.png) | [before](qgis4-lausanne-boundary-z11.9-before.png) | [after](qgis4-lausanne-boundary-z11.9-after.png) |
| lausanne-boundary-z12.0 | 4 | -5.783% | [reference](lausanne-boundary-z12.0-reference.png) | [before](qgis4-lausanne-boundary-z12.0-before.png) | [after](qgis4-lausanne-boundary-z12.0-after.png) |
| lausanne-boundary-z12.1 | 4 | -5.306% | [reference](lausanne-boundary-z12.1-reference.png) | [before](qgis4-lausanne-boundary-z12.1-before.png) | [after](qgis4-lausanne-boundary-z12.1-after.png) |
| lausanne-lavaux-z10-light-activity | 4 | -3.379% | [reference](lausanne-lavaux-z10-light-activity-reference.png) | [before](qgis4-lausanne-lavaux-z10-light-activity-before.png) | [after](qgis4-lausanne-lavaux-z10-light-activity-after.png) |
| zurich-region-z8-light-activity | 4 | -3.561% | [reference](zurich-region-z8-light-activity-reference.png) | [before](qgis4-zurich-region-z8-light-activity-before.png) | [after](qgis4-zurich-region-z8-light-activity-after.png) |
