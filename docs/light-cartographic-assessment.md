# Light: initial holistic cartographic assessment

Assessment date: **2026-09-11**. Tracking issue:
[#1462](https://github.com/ebelo/qfit/issues/1462).
Protocol: [cartographic comparison framework](cartographic-comparison-framework.md).

This document retains the historical baseline and adds evidence-scoped updates.
It is **not a declaration that Light passes all criteria**.
The latest road-label improvement is real, but does not settle road hierarchy,
geographic semantics, typography or the untested user-facing output paths.

## Evidence and scope

This review reuses the final, validated captures from
[PR #1463](https://github.com/ebelo/qfit/pull/1463), code
`73aafa6a697e4d41b015c0994fb239df9c557991`, merged baseline
`3f4e50d9247166a755685b88f6d8f2a8df7fc5da`. No new live-source capture is claimed.

- Seven cameras: Switzerland/Alps z5, Zurich region z8, Lausanne/Lavaux z10,
  Bern z12, Geneva z14, Zurich streets z17 and Geneva streets z18.
- Two font-enabled runtimes: QGIS **3.44.11** and **4.2.0**; offscreen PNG,
  1280×900 per map. This is fourteen QGIS outputs against seven references.
- Original source and QGIS-preprocessed style fingerprints are recorded.
  Individual upstream vector-tile payloads were **not archived**; these images
  cannot certify a future provider data revision.
- The preceding PR verified unchanged repeat controls and final candidate
  artifact identity. This audit adds a broader manual review and source-layout
  inspection, not new automated semantic assertions.
- No current activity overlays, Windows desktop, PDF, multilingual edge cases,
  fractional zoom sequences or accessibility simulations are represented.

Reviewer-visible evidence:

- [Seven full-resolution runtime comparisons][gallery]
- [Capture provenance and image hashes][manifest]
- [Source layer inventory and selected original expressions][inventory]

The panels are **Mapbox reference | QGIS 3 baseline | QGIS 4 baseline**.
They are not before/after images of a new change. Contact sheets aid navigation;
judge text and thin strokes in the full-resolution maps at their intended size.

## Findings that deserve the next focused probes

### 1. Road hierarchy and figure–ground separation — C04, C11, C12

At Geneva z14, the reference's white street network delineates urban blocks much
more clearly. The QGIS street network is faint relative to its labels; similar
differences occur in the street views. This is an **open visual finding**, not
yet proof that a single width parameter is wrong. Check class eligibility,
paint ownership, line widths, casing, background contrast and scale conversion
before choosing a remedy. A wider road cannot compensate for a missing class.

Use the [Geneva z14 map][geneva] and both street cameras. Preserve buildings,
minor-road ordering and activity legibility as coupled guardrails.

### 2. Boundary treatment — C15

The [Lausanne/Lavaux view][lausanne] shows a prominent solid reference boundary
segment across Lake Geneva versus a faint dotted/dashed QGIS treatment. Regional
views also differ in boundary emphasis. Attribute the visible segment to its
exact source layer before changing it: administrative level, maritime status,
disputed status and worldview are semantic filters, not decorative options.
The screenshot establishes a discrepancy, **not which political classification
is responsible**.

### 3. Label language and content — C19 (baseline diagnosis)

The recorded original `country-label` and `settlement-major-label` request
`coalesce(get(name_en), get(name))`. Inspecting a single QGIS `"name"` rule is
**not** sufficient proof of lost fallback: qfit already has a
`_name_en_fallback_text_field_variants` helper which creates English and local
companion rules when its caller's layout matcher applies.

For this particular Light source, however, both the country-layout and
settlement-dot layout matchers return false. Reprocessing the recorded source
produces only `get(name)` for these two layer IDs, and the **complete matching
rule inventory in both Docker snapshots contains no `name_en` companion**.
The [label-content audit][content-audit] records the matcher results, source and
processed expressions, rule filters, snapshot hashes and code revision. Thus
the open finding is Light-specific helper applicability, not an assertion that
qfit never implemented name fallback. Regional local-name differences support
investigating the resulting strings but do not replace this rule-level check.

The scoped update below addresses those two source owners at the native QGIS
adapter boundary. Preprocessed JSON still contains `get(name)`; inspect the final
QGIS expression rather than treating preprocessing alone as the complete path.
This follows the original source language request, not a new product locale policy.

### 4. Typography, selection and density — C17–C22

Open-font substitution and road duplicate removal have scoped evidence, but
wrapping, relative size/weight, settlement selection and label density still
differ. Simply enlarging all street labels was already rejected: 12 px and
14 px probes worsened the tested views in both runtimes. This rejects those
candidates, **not all typographic improvement**. Inspect the responsible label
role, source expression and collision population before the next adjustment.

## Complete criterion ledger

Verdicts follow the framework. **PARTIAL** means some evidence exists, not a
pass. Severity below is provisional triage of an observed finding; a dash means
no defect severity has been established, not zero risk. “Major” here warrants a
focused investigation before broad completion, not an assertion of a root cause.

| ID | Current verdict | Observation / coverage and next validation | Finding severity |
| --- | --- | --- | --- |
| C01 | OPEN | Actual context is measured below: QGIS 3/4 use different DPI, requested camera zoom differs from native zoom, and the source overview uses globe versus native Mercator. Explicit planar overview registration is scoped below; tile payloads and extended outputs remain unvalidated. | Major validation gap |
| C02 | OPEN | Live place features and rejected rank probes expose a major/minor role-handoff defect in inherited city/town gates and fixed rank eligibility. Other classes, types and null cases still need systematic fixtures. | Major |
| C03 | NOT ASSESSED | No generalization, sparse-geometry or false-connection fixture audit. | — |
| C04 | OPEN (remaining scope) | Source-owned road widths now have a scoped two-runtime repair below; global composition, regional fidelity and other visual hierarchies remain open. | Major baseline finding scoped below |
| C05 | PARTIAL | Four road owners have source-class width tests below; other visual-variable encodings and classes remain unassessed. | — |
| C06 | PARTIAL | Broad palette can be compared; class-interior lightness/contrast measurements and adjacent-class tests remain. | — |
| C07 | PARTIAL | Urban/park/land areas appear in existing views. Agriculture, polygon holes and individual land-use class ownership are not validated. | — |
| C08 | PARTIAL | Large water footprints are visually comparable. Minor streams, islands, confluences and water-label association need fixtures. | — |
| C09 | N/A (source-scoped) | Recorded Light inventory contains no contour, hillshade or raster-dem layer. Missing Outdoors-like relief is not a Light defect; reassess if source intent changes. | — |
| C10 | PARTIAL | Buildings appear in the street views; courtyards, transition visibility and road/footprint overlap are not systematically checked. | — |
| C11 | OPEN (remaining scope) | Four source-owner class/zoom widths restored and urban networks improved below. Remaining class eligibility, road/path coverage, junctions and output scales need fixtures. | Major baseline finding scoped below |
| C12 | PARTIAL | Road widths and ordinary national-boundary source width/continuous texture pass scoped native tests below. Other caps/joins/dashes/blur, full casing construction and output-scale continuity remain unvalidated. | — |
| C13 | NOT ASSESSED | No named bridge/tunnel/at-grade crossing audit against structure attributes. | — |
| C14 | NOT ASSESSED | Source has rail and aeroway layers; no systematic transport distinction/continuity checks. | — |
| C15 | OPEN (remaining scope) | Ordinary national-boundary source width/solid texture and Lake Geneva owner/status attribution have a scoped repair below. Other owners, disputed/maritime/worldview fixtures and output paths remain open. | Major baseline finding scoped below |
| C16 | PARTIAL | Source symbol inventory available; sprite applicability, anchors, collision lifecycle and high-DPI behavior require dedicated checks. | — |
| C17 | PARTIAL | Font-enabled Docker roles have earlier scoped validation. Desktop font distribution and multilingual fallback are not certified by these captures. | — |
| C18 | OPEN | Text width, weight, wrapping and relative hierarchy remain visibly different. Blanket size probes were rejected, not accepted as a fix. | Minor |
| C19 | OPEN (remaining scope) | Country/major-settlement English/local fallback now has scoped native-expression and matched-PNG passes below. Other source roles, multilingual/RTL rendering, long names and desktop/export coverage remain open. | Major baseline finding scoped below; remaining severity not established |
| C20 | PARTIAL | Some named-road crops inspected during duplicate work; systematic association, rotation and curved-line placement remain. | — |
| C21 | PARTIAL | Current dense views are available; survival/priority decisions and symbol/halo collision extents are not comprehensively audited. | — |
| C22 | PARTIAL | Road duplicate removal has a scoped pass; the criterion as a whole is not passed. See the separate coverage-cell verdicts below. | — |
| C23 | OPEN | Two-city z13/z14 triplets expose native rounding and requested/native zoom mismatch; no rank repair retained. Other intervals, outer bounds, size/width changes and interactive sequences remain unassessed. | Observed city-label mismatch; broader severity unestablished |
| C24 | NOT ASSESSED | No deliberate tile-edge, clipping, adjacent-pan or world-wrap fixtures. | — |
| C25 | PARTIAL (diagnostic only) | Synthetic Run/Ride/Hike overlays now exercise unchanged production categorization on two city extents below. Real activity data, UI/selection/start/end/direction states remain NOT ASSESSED. | — |
| C26 | PARTIAL (diagnostic only) | Two-city synthetic routes remain visible with the width repair below. Real sparse/dense/shared routes and broader background/output coverage remain NOT ASSESSED. | — |
| C27 | NOT ASSESSED | No grayscale, color-vision, low-vision or target physical-size assessment. | — |
| C28 | PARTIAL | Two Docker PNG runtimes plus scoped native QGIS 3.34 width expressions checked below. Other older versions, Windows/macOS, interactive canvas, high-DPI and PDF still need separate cells. | — |
| C29 | PARTIAL | All 30 current width-matrix repeat controls are byte-identical. Cold/warm cache, interactive responsiveness and pan/zoom stability remain untested. | — |
| C30 | NOT ASSESSED | Cropped basemap evidence does not validate complete user-facing attribution, legend, scale or north/context requirements. | — |

### C12/C15: ordinary national-boundary stroke — 2026-09-14 scoped update

Baseline `2985c8247eb05490dd4d26936c3b003a17a1de4d`; implementation
`5ebb6ead8740c63971b273f278726aad9b399021` (source/runtime hashes in the manifest).
[Matched maps, native-size crops, complete boundary/label inventories and attribution][national-boundary].
Fresh source SHA256:
`87413e46c074e13aef420958a3ad101961766e6645336608e399ceccaffc6d32`.
The complete five-owner source fixture matches the fresh source.

**Attribution comes before styling:** fresh browser `queryRenderedFeatures`
identifies the Lake Geneva line as `admin-0-boundary`, with its background.
Its visible CH–FR features have `admin_level: 0`, `disputed: "false"`,
`maritime: "false"`, `worldview: "all"`. QGIS owner-removal probes in both
Docker runtimes remove that same line. Removing `admin-0-boundary-disputed`
is byte-identical in the Lausanne and Zurich attribution views. These are
source-feature facts, not an independent political classification.

**Mechanism and retained scope:** this source owner requests linear widths
from 0.65 px at z3 to 2.6 px at z12, clamped outside that range, with the
continuous `[10, 0]` dash pattern. Generic preprocessing collapses and converts
the width to millimetres; native conversion interprets it as pixels again,
producing a fixed approximately 0.182011 mm. At that width the native zero-gap
custom pattern visibly breaks the ordinary border into dashes. A real native
horizontal-line painting regression reproduces the gaps, rather than relying
only on symbol properties.

The exact-Light adapter restores this one owner's audited width using portable
CASE arithmetic and one px/mm conversion, and renders its zero-gap pattern as a
solid pen. Source and native status/worldview filters, rule order, zoom ranges,
color, background owners and all other boundary paint remain unchanged. Active
native overrides, custom patterns/units/symbols, changed source contracts,
Outdoors and custom styles retain their prior path. This does not normalize
other boundaries or extend the minimum QGIS version.

**Probe decisions:** solid-only improves continuity but leaves the width wrong;
valid width-only improves fidelity but retains a zero-gap custom pen. The
combined source-width/solid candidate is retained for source semantics, not tiny
aggregate pixel differences between those two valid width probes. Initial
`least`/`greatest` width probes were invalid QGIS expressions: unchanged images
are excluded as width evidence, not labelled neutral. Production outputs in the
two attribution views match the valid combined probe byte-for-byte in each runtime.

| Coverage cell | Verdict | Evidence / remaining work |
| --- | --- | --- |
| C02/C15: visible Lake Geneva CH–FR and Zurich-region national lines, browser attribution plus both Docker owner-removal probes | PASS (scoped ownership) | Exact source owners/status properties identified; removing the disputed owner changes no pixels in these extents. Not an actual disputed/coastal/worldview-specific fixture pass. |
| C12/C15: source widths at 14 values including lower/upper fractional neighborhoods, 72 native status/worldview combinations, and actual horizontal-line painting; QGIS 3.34.4, 3.44.11 and 4.2.0 | PASS (scoped native behavior) | Source interpolation/clamping and one-time units within 1e-10 mm; only eligible ordinary national features survive the preserved predicate. Baseline has painted gaps; candidate is continuous. Older versions beyond the native lanes are not newly certified. |
| C12/C15: seven Light presets plus Lausanne requested z11.9/12/12.1, both Docker PNG runtimes | PASS (scoped line repair); broader boundary fidelity OPEN | Lake and regional ordinary borders are continuous/readable. Static transition frames contain the affected border. Other owners, backgrounds, blur and actual source/native scale alignment remain unvalidated. |
| C01/C04: low-zoom source globe versus native EPSG:3857 | OPEN; projection mismatch diagnosed | The original Light source requests globe projection and overview geography visibly differs from the native planar view. Explicit Mercator reference anchors align within 1e-6 px and its overview MAE improves 3.967% / 4.328%; original globe errors increase 2.440% / 2.510%. Keep both datasets separate; neither result closes scale/DPI or product-projection scope. No product or renderer limitation is accepted here. |
| C02/C17–C22: complete labels, all five boundary filters/order/other paint and native context, all 24 matched pairs | PASS (scoped preservation) | Only ordinary national width and zero-gap representation change. Existing settlement role-handoff, typography/content and other semantic defects are not discharged. |
| C25/C26: synthetic Run/Ride/Hike overlays in Lausanne and Zurich-region extents, both Docker PNG runtimes | PASS (scoped visible overlay guardrail) | Unchanged production activity renderer; diagnostic routes remain readable. Real shared/dense activity data and UI/selection/start/end/direction states remain NOT ASSESSED. |
| C29: all 24 settled unchanged camera/runtime repeat controls | PASS (scoped repeats) | PNG repeats byte-identical. Cold/warm performance and interactive temporal stability remain unassessed. |
| C12/C15/C23/C24/C27/C28: other boundary owners, actual disputed/maritime/worldview fixtures, pan/seams, accessibility, desktop/PDF | OPEN / NOT ASSESSED as in the main ledger | A corrected ordinary national line is not a criterion-wide boundary, output or accessibility pass. |

**Projection diagnosis (not a source-style or production harness change):**
actual browser `getProjection()` reports globe for the original overview. Its
Geneva/Paris/Vienna anchors differ from measured QGIS Mercator placement by
1.77/18.44/29.73 pixels. The original-globe browser control/repeat is byte-identical
to the initial reference. With an explicit diagnostic Mercator camera override,
the same three anchors align within 1e-6 pixels, and the two browser repeats are
also byte-identical. Aligned overview reference MAE improves 3.967% / 4.328% in
QGIS 3/4, versus an increase of 2.440% / 2.510% against the original unaligned
globe image. This explains the guardrail discrepancy without changing the source
snapshot, either QGIS image, or accepting a loss of globe support on Emman's behalf.
Other cameras, native scale/DPI and interactive projection require follow-up.

**Independent dimensions:** source width/texture and tested status semantics
pass within the stated cells. Whole maps and readable crops establish the scoped
usability repair. Reference fidelity must distinguish the original globe view
from explicitly aligned planar diagnostics; regional/urban figures remain
runtime-specific. Actual map DPI is 100 in QGIS 3 and 96 in QGIS 4, and native
style zoom still differs from requested camera zoom. C01 alignment remains OPEN.
Live tile payloads were not archived, and source hashes do not certify future data.

The full local suite, both complete Docker test scripts, both ZIP builds and
package-content checks pass. Fonts remain a separate installation dependency.
C15 overall and the wider C01–C30 backlog remain open; no release, deployment,
accepted limitation or holistic completion is implied.

### C04/C11/C12: source-owned road widths — 2026-09-14 scoped update

Baseline `8b5e661e54a5b84661e3a46eab4f79eef13b96f4`; retained implementation
`964710365c54f7cfaead3170fe43d505fa33d856`.
[Matched full maps, native-size crops, source and complete label/stroke audits][road-widths].
Fresh source SHA256:
`87413e46c074e13aef420958a3ad101961766e6645336608e399ceccaffc6d32`.
All four whole source-owner fixtures match that source exactly.

**Mechanism:** generic preprocessing collapses `road-simple`, `tunnel-simple`,
`bridge-simple` and `bridge-case-simple` class/zoom width expressions to constants,
converts them to millimetres, then the native converter treats those constants as
pixels. The resulting fixed native core/casing widths are approximately
0.168010/0.252016 mm. The Light-only native adapter restores the original numeric
class groups and base-1.5 zoom interpolation, clamps both endpoints and converts
pixels to millimetres once. It changes only fixed-width, single simple-line
symbols belonging to these four unsplit owners. Existing active data-defined
widths, non-millimetre symbols, other source contracts and non-Light styles keep
their prior behavior. Generic preprocessing remains byte-identical to baseline.

The rejected native-converter-only candidate `a01f188` belongs to the earlier
interrupted run, not this fresh matrix. It improved modern captures but failed
126/448 native QGIS 3.34 cases: equal expression endpoints omit the unit multiplier.
Upstream QGIS 3.28 also uses exponent rather than Mapbox-base interpolation.
The retained expression uses basic QGIS arithmetic; no duplicate artificial stop,
version cutoff or near-equal endpoint workaround remains.

**Independent dimensions:** source width semantics pass only in the native cases
below. Whole maps show clearer urban street networks and road-width hierarchy,
without changing label settings or other paint. Most reference MAE values improve;
Zurich z8 has a repeatable small increase in both runtimes, explicitly retained as
an OPEN reference-fidelity difference rather than called noise or an accepted
renderer limitation. The source specifies much thinner secondary/tertiary roads
than motorways at regional zooms; preserving a uniform width to improve an aggregate
score would erase that distinction. This slice does not certify all feature
eligibility, junction topology, label associations or global composition.

| Coverage cell | Verdict | Evidence / remaining work |
| --- | --- | --- |
| C05/C11/C12: four source owners × eight representative classes including unknown/NULL × 14 zoom values; QGIS 3.34.4 host, 3.44.11 and 4.2.0 Docker | PASS (scoped native widths) | 448 cases per runtime verify original class values, base interpolation, endpoint clamping and one-time units to 1e-10 mm. Includes fractional stop neighborhoods; injected native zoom tests are not camera-alignment proof. QGIS 3.28 is source-inspected, not natively tested. |
| C04/C11: seven Light presets in both Docker PNG runtimes | PASS (scoped street-width repair); broader hierarchy OPEN | Full-map and unscaled-detail inspection shows restored Geneva z14 street/block separation and differentiated Bern/Zurich/Geneva streets. Not a complete road/path inventory or topology audit. |
| C01/C23: Geneva/Bern requested z12.9/13/13.1 triplets, both Docker runtimes | PARTIAL; scale alignment OPEN | Actual per-frame native zoom/DPI recorded. These static triplets exercise the candidate around requested z13, not calibrated source/native boundary equivalence or interactive continuity. Other stop/output intervals remain unassessed visually. |
| C02/C10/C17–C22: settings-preservation guardrails for all 30 pairs | PASS (scoped preservation only) | Complete labels, native camera context, four owners' filters and all their other paint settings are identical before/after. This does not discharge existing label, building or semantic defects. |
| C04/C06: Zurich regional reference fidelity, both runtimes | OPEN | Small repeatable MAE regression, with source-backed class separation retained. Full-map source/native-scale, palette, boundary and label differences still require follow-up; no limitation accepted. |
| C25/C26: synthetic Run/Ride/Hike overlays on Geneva z14 and Bern z12, both Docker PNG runtimes | PASS (scoped visible overlay guardrail) | qfit's production categorized activity renderer is unchanged; all three diagnostic routes remain visible against the changed basemap. These are not real activities or UI/selected/start/end/direction states. |
| C25–C28: real dense/shared routes, accessibility, actual desktop/packaged-font/PDF outputs | NOT ASSESSED by this slice | No broader activity or runtime/output pass follows from diagnostic PNGs or ZIP checks. |
| C29: settled unchanged repeat captures, all 30 camera/runtime pairs | PASS (scoped repeats) | All unchanged PNG pairs are byte-identical. Cold/warm cache behavior, timed interaction and pan/zoom stability remain unassessed. |
| C12/C13/C15/C24: caps/joins/dashes/blur, named crossings/structure order, boundary status/owner and tile seams | OPEN / NOT ASSESSED as in the main ledger | Restoring widths does not fix or validate these mechanisms. Follow with source-owner/status and dedicated topology fixtures. |

The fresh matrix is **15 cameras × two font-enabled Docker runtimes**: seven
presets, six two-city triplet cameras and two diagnostic overlay cameras. All
30 unchanged repeats are byte-identical. Baseline and candidate use matched
1280×900 offscreen PNG settings within each runtime; QGIS 3 uses 100 map DPI,
QGIS 4 uses 96. Requested camera zoom remains different from continuous native
style zoom. Runtime/font identities, source/preprocessed fingerprints, exact
camera extents and all metrics are in the evidence manifest. Live upstream tile
payloads are not archived; this is not a future-provider-data guarantee.

Both full Docker test lanes, the full local suite, legacy native width cases,
both plugin ZIP builds and package-content checks pass. Fonts remain a separate
installation dependency. C04/C11 overall and the broader C01–C30 scope remain
open where recorded; no release, deployment or limitation acceptance is implied.

### C01/C02/C23: capture-context audit and rejected rank repairs — 2026-09-11

The [measured context, source features, full maps and rejected probes][capture-context]
use baseline `70fd68dd690035e9bdb43e8d9c87f434a0946070`. The retained change is
**validation metadata only**: production style/adapter files and both packaged
plugin payloads are unchanged. It records actual map/image DPI, device pixel
ratio, output size, extent/CRS, scale, continuous native zoom and rounded render/
matrix-clamped fetch zoom after successful PNG creation. It does not calibrate them.

The current matrix adds Geneva and Bern at **12.9/13/13.1 and 13.9/14/14.1** to
all seven Light cameras. Both Docker generations have 38 matched unchanged
control repeats and 38 metadata-head renders byte-identical to their baseline;
complete label inventories are identical too. This is a **runtime baseline
audit**, not a before/after cartographic improvement or an interactive sequence.

**DPI correction:** current QGIS 3.44.11 map settings use **100 DPI**, while
QGIS 4.2.0 uses **96 DPI**. The earlier C19 evidence manifest's shared `dpi: 96`
was an assumption, not a captured setting. Those immutable historical PNGs encode
approximately 99.9744 and 95.9866 DPI respectively (integer pixels-per-metre
quantization); their hashes and density correction are in the new manifest.
Do not rewrite old evidence or call it freshly captured. Same-runtime controlled
C19 name-fallback results still stand; a cross-runtime matched-DPI or exact
source-zoom claim does not follow from them.

At requested Geneva z13, QGIS 3's continuous native zoom is about **12.8976**,
while its integer render zoom is **13**. The renderer rounds its integer zoom;
its continuous zoom is interpolated in scale space. Neither quantity is an
interchangeable alias for the browser's requested camera zoom. Actual values for
both cities/runtimes are recorded per capture, not inferred from camera names.

| Coverage cell | Verdict | Evidence / outstanding action |
| --- | --- | --- |
| C01: actual context recorded for 19 cameras × 2 Docker PNG runtimes | PASS (scoped measurement) | Actual settings/image/matrix values are present; unchanged images and full label inventories prove this metadata addition does not alter rendering. This is not a comparability/parity pass. |
| C01: matched physical DPI and camera/native style-zoom alignment | OPEN | The measured mismatch must be resolved or explicitly dispositioned before claiming equivalent scale-boundary coverage. No limitation is accepted here. |
| C02: major/minor settlement role handoff below z13 | OPEN | Source rank ranges are complementary; inherited qfit city/town gates are not. Live Munich rank 8 and Milan rank 7, both cities with filterrank 1, belong to the minor source owner at z5.35 but are excluded by its town-only gate. |
| C02/C23: Geneva/Bern rank eligibility at z13/z14 | OPEN | Both sampled cities have symbolrank 9 in z12–z15 anchor tiles. The source excludes them at z13; native converted rules retain a fixed upper-rank predicate. Actual zoom alignment defeats the tested naive fixes. |
| C23: other rank classes/roles, outer layer ranges, width/size transitions and interactive sequences | NOT ASSESSED by this slice | Boundary PNGs and native expression tests do not establish complete continuity or feature coverage. |

**Rejected candidates (none shipped):**

1. All-stop major-rank restoration removes useful low-zoom Munich/Milan and
   other reference labels because the complementary minor owner remains city-
   restricted. Lower whole-image error is not a semantic improvement; QGIS 4
   Zurich also worsens. A coordinated role repair is required.
2. Static z13/z14 native bands switch prematurely at requested z12.9 because
   QGIS rounds the integer activation zoom. A completed QGIS 3 capture proves
   the regression; the remaining queued probe was stopped, not counted passed.
3. A fractional `@vector_tile_zoom` predicate avoids that early switch, but
   still misses the exact requested z13 boundary. A native test that injects
   camera zoom directly would conceal this difference. No rank change is retained.

The [feature audit][capture-context] contains selected public place properties
and tile hashes, not a full renderer request trace; tile bytes were not archived.
Road hierarchy (C04/C11/C12), boundary ownership (C15), all other label roles and
the required activity/accessibility/desktop/PDF fixtures remain open. The next
slice must address measured capture-scale alignment before another transition
repair, and preserve the major/minor handoff guardrail. No product decision or
renderer limitation is accepted on Emman's behalf.

### C19: native source-name fallback — 2026-09-11 scoped update

Runtime implementation: `ef136b9956e4ad4d241f707f8fa0e2d3b90659b7`.
[Fresh maps, complete matching label inventories and source][name-fallback]
([hashes, controls, camera/runtime settings and metrics][name-fallback-metrics]).
Baseline: `75131a5a1ebb9dcfa42f5fcf8fd7ac9345d3b917`.

The fresh source reproduces the baseline matcher gap. For **exact Light v11**,
only the unsplit `country-label` and `settlement-major-label` rules using
`place_label` and the original `coalesce(get(name_en), get(name))` contract are
adapted. QGIS now receives `coalesce("name_en", "name")` before font-band
splitting. No new companion rule, feature filter or language preference is added;
Outdoors, custom styles, other source roles and changed source contracts retain
their existing behavior.

Explicit field references matter: QGIS constructs the vector-tile field schema
from requested columns and initializes absent MVT values to NULL. The rejected
`attribute(@feature, ...)` probe did not request `name_en`, was neutral in 12/14
images, and cannot establish fallback correctness. A standalone expression on a
schema without the column also fails, but is not the actual decoder path. Native
regressions use the expression's requested field schema and valid feature geometry.

| Coverage cell | Verdict | Evidence / outstanding action |
| --- | --- | --- |
| The two audited owners: English, NULL/missing English, empty English, missing local or both values; QGIS 3.34.4 host, 3.44.11 and 4.2.0 Docker native expressions | PASS (scoped) | Recorded source fixture and real-converter tests verify both requested fields and exact strings. Empty English stays empty; only NULL/missing falls back. Accented Latin, Cyrillic and Arabic strings survive expression evaluation; this is not glyph/RTL rendering proof. |
| Same two owners: seven Light cameras, both Docker generations, 1280×900 headless PNG | PASS (scoped) | Zurich/Lucerne, Munich/Milan and Geneva now follow source-requested names. All 14 controls and all 14 production-versus-probe pairs are byte-identical. Complete matching inventories preserve all settings except the three original/derived `field_name` values. |
| Other source label roles and unsupported/coalesce variants | NOT ASSESSED by this slice | Audit each remaining source expression and actual strings; do not inherit the two-owner pass. |
| Long names, actual multilingual/RTL shaping/placement, missing-script fonts, pan/zoom transitions, desktop/PDF paths | NOT ASSESSED by this slice | Retain the existing required fixture/output backlog. |

**Independent dimensions:** source-name semantics pass in the stated cells.
Reference MAE improves at z5/z8 in both runtimes; Lausanne z10, Bern z12 and both
street views remain byte-identical. Geneva z14 has a tiny MAE increase
(+0.0000003472 in QGIS3; +0.0000000318 in QGIS4) because QGIS shows a city label
absent from the reference, now spelled Geneva rather than Genève. This remaining
placement discrepancy is not dismissed as control noise. Font weight, density,
road hierarchy and the broader usability findings are not resolved by this fix.
No renderer or product limitation is being accepted on Emman's behalf.

C02/C17/C20–C22 guardrails here are **settings-preservation checks**, not new
criterion-wide passes. C01 retains the unarchived upstream tile revision caveat;
C28 remains runtime/output-scoped. C19 as a whole remains OPEN.

### C22: separate coverage-cell results

| Coverage cell | Verdict | Evidence / outstanding action |
| --- | --- | --- |
| Nearby cross-feature road-name duplicates; seven Light cameras, QGIS 3.44.11 and 4.2.0, headless PNG | PASS (scoped) | [PR #1463](https://github.com/ebelo/qfit/pull/1463): source-backed duplicate spacing, repeated unchanged controls, retained label coverage and final-artifact equivalence. |
| Settlement/POI density and other repetition mechanisms; existing baseline cameras | PARTIAL | Baseline images allow inspection, but no systematic per-class counts or inter-label-distance acceptance check. Attribute each remaining density difference and validate its population separately. |
| Repetition across deliberate tile-edge pans, fractional zoom sequences and desktop/PDF output | NOT ASSESSED | Dedicated fixtures/output captures are absent; do not inherit the road-removal PNG pass. |

## Coverage backlog and completion gate

The owner of each new #1462 slice should copy the framework's validation record,
name its affected IDs, and link the final reviewed artifacts. Current ledger
owner: **#1462 investigation**; assign a concrete PR/run as a slice starts.

- [ ] Resolve or explicitly disposition the observed road, boundary and content
  findings with source-owner probes and independent-camera guardrails.
- [ ] Inventory every source-present class and symbol; mark absent expectations
  N/A with source evidence, not by lack of a visible example.
- [ ] Add rural, crossing, coast/island/confluence and dense urban fixtures.
- [ ] Add transition triplets, pan/tile-edge and temporal stability fixtures.
- [ ] Check long/multilingual/RTL strings, missing fields and missing fonts.
- [ ] Validate current activity categories/states and dense route overlays.
- [ ] Review grayscale/color-vision and intended physical display/print sizes.
- [ ] Validate supported desktop/packaged-font and PDF paths separately from PNG.
- [ ] Re-audit all criteria after the retained slices; link any accepted
  limitations to their explicit review decision and residual scope.

**#1462 remains open.** No-improvement results from a few style probes, green CI,
or a low aggregate pixel error cannot discharge this ledger. A narrow PR need
not solve unrelated rows, but must not regress coupled criteria. Closing the
holistic investigation requires the framework's scoped completion review, or an
explicitly agreed scope reduction with follow-up ownership for excluded work.

[gallery]: https://github.com/ebelo/qfit/tree/f1b3101995ee3a4e3dbba539ca57b42d51d83302/docs/visual-evidence/issue-1462/holistic-audit
[manifest]: https://github.com/ebelo/qfit/blob/f1b3101995ee3a4e3dbba539ca57b42d51d83302/docs/visual-evidence/issue-1462/holistic-audit/manifest.json
[inventory]: https://github.com/ebelo/qfit/blob/f1b3101995ee3a4e3dbba539ca57b42d51d83302/docs/visual-evidence/issue-1462/holistic-audit/source-inventory.json
[geneva]: https://raw.githubusercontent.com/ebelo/qfit/f1b3101995ee3a4e3dbba539ca57b42d51d83302/docs/visual-evidence/issue-1462/holistic-audit/geneva-urban-z14-light.png
[lausanne]: https://raw.githubusercontent.com/ebelo/qfit/f1b3101995ee3a4e3dbba539ca57b42d51d83302/docs/visual-evidence/issue-1462/holistic-audit/lausanne-lavaux-z10-light.png
[content-audit]: https://github.com/ebelo/qfit/blob/bff40b6b35db33d74646319f119b5cb17ebab51d/docs/visual-evidence/issue-1462/holistic-audit/label-content-audit.json

[name-fallback]: https://github.com/ebelo/qfit/tree/d007ecd7fe19542d89e733cd3b701f085461de31/docs/visual-evidence/issue-1462/light-name-fallback
[name-fallback-metrics]: https://github.com/ebelo/qfit/blob/d007ecd7fe19542d89e733cd3b701f085461de31/docs/visual-evidence/issue-1462/light-name-fallback/metrics.json

[capture-context]: https://github.com/ebelo/qfit/tree/cc7ecd4ace62e3eb484dfe5dc7dedfc0195e0c3d/docs/visual-evidence/issue-1462/light-capture-context

[road-widths]: https://github.com/ebelo/qfit/tree/d894f1c7fb09176320a2a06a806ebeace19377c9/docs/visual-evidence/issue-1462/light-road-widths

[national-boundary]: https://github.com/ebelo/qfit/tree/242fbc552577c3d36550db7967044ac670e3a584/docs/visual-evidence/issue-1462/light-national-boundary
