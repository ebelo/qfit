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
| C01 | OPEN | Map and runtime-normalized tile-render scales are now separated below; historical QGIS4 zoom metadata is corrected. Default DPI and fractional activation differ, and source globe is not native Mercator. Density-output divergence, tile payloads and extended outputs remain open. | Major validation gap |
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
| C12 | PARTIAL | Road widths, ordinary national-boundary core width/continuous texture and ordinary-only background width/opacity pass scoped native tests below. Other caps/joins/dashes/blur, full casing construction and output-scale continuity remain unvalidated. | — |
| C13 | NOT ASSESSED | No named bridge/tunnel/at-grade crossing audit against structure attributes. | — |
| C14 | NOT ASSESSED | Source has rail and aeroway layers; no systematic transport distinction/continuity checks. | — |
| C15 | OPEN (remaining scope) | Ordinary national-boundary source width/solid texture and Lake Geneva owner/status attribution have a scoped repair below. Ordinary-only background width/opacity now has a guarded repair, with disputed fallback retained after a rejected broad candidate. Five-owner eligibility and two disputed/two subdivision extents have scoped evidence; blur, other owner paint, mixed fidelity and wider geography/output paths stay open. | Major baseline finding scoped below |
| C16 | PARTIAL | Source symbol inventory available; sprite applicability, anchors, collision lifecycle and high-DPI behavior require dedicated checks. | — |
| C17 | PARTIAL | Font-enabled Docker roles have earlier scoped validation. Desktop font distribution and multilingual fallback are not certified by these captures. | — |
| C18 | OPEN | Text width, weight, wrapping and relative hierarchy remain visibly different. Blanket size probes were rejected, not accepted as a fix. | Minor |
| C19 | OPEN (remaining scope) | All 14 source label roles now have a content audit: country/major settlements and both water-label owners pass scoped cases; ten owners lose source content. Cairo/Jerusalem corroborate local-road and airport-code mismatches. RTL shaping, long names and desktop/export remain open. | Major baseline finding scoped below; remaining severity not established |
| C20 | PARTIAL | Some named-road crops inspected during duplicate work; systematic association, rotation and curved-line placement remain. | — |
| C21 | PARTIAL | Current dense views are available; survival/priority decisions and symbol/halo collision extents are not comprehensively audited. | — |
| C22 | PARTIAL | Road duplicate removal has a scoped pass; the criterion as a whole is not passed. See the separate coverage-cell verdicts below. | — |
| C23 | OPEN | Two-city z13/z14 triplets expose native rounding and requested/native zoom mismatch; no rank repair retained. Other intervals, outer bounds, size/width changes and interactive sequences remain unassessed. | Observed city-label mismatch; broader severity unestablished |
| C24 | NOT ASSESSED | No deliberate tile-edge, clipping, adjacent-pan or world-wrap fixtures. | — |
| C25 | PARTIAL (diagnostic only) | Synthetic Run/Ride/Hike overlays now exercise unchanged production categorization on two city extents below. Real activity data, UI/selection/start/end/direction states remain NOT ASSESSED. | — |
| C26 | PARTIAL (diagnostic only) | Two-city synthetic routes remain visible with the width repair below. Real sparse/dense/shared routes and broader background/output coverage remain NOT ASSESSED. | — |
| C27 | NOT ASSESSED | No grayscale, color-vision, low-vision or target physical-size assessment. | — |
| C28 | PARTIAL; density consistency OPEN | Fresh two-city DPR2 PNGs retain native zoom, but physical-density PNGs and actual one-map PDFs change QGIS4 activation/detail. QGIS3 also changes label placement across PDF density. Production150-DPI settings are exercised, not a complete atlas or desktop installation. | Provisional major output-consistency finding |
| C29 | PARTIAL; PDF repeat cells OPEN | Prior matrices and 48 new background PNG control pairs repeat exactly. Earlier Bern/Geneva PDF150 variation is now also observed in Lausanne/Kashmir QGIS4 production150-DPI outputs; other new repeated PDF modes are raster-identical. Cold/warm performance and interactive stability remain untested. | PDF variability severity unestablished |
| C30 | NOT ASSESSED | Cropped basemap evidence does not validate complete user-facing attribution, legend, scale or north/context requirements. | — |

### C19: complete label-role audit and multilingual baselines — 2026-09-14

[Immutable source, native audits, reproducible workers and matched maps][label-roles]
use unchanged runtime `bdc741cf38caf47e25cf1809055f506bb865efb9`.
Fresh source SHA256 remains
`87413e46c074e13aef420958a3ad101961766e6645336608e399ceccaffc6d32`.
This slice adds a complete 14-owner source fixture, pinned provenance/ordered-owner/
canonical-content assertions, and native water-companion regression, **not a production language or rendering fix**.

Every source symbol owner is accounted for: 13 request English/local-name
coalesce; airport requests its distinct sizerank/ref/name expression. Both native
builds produce 39 rules. Each audit evaluates 264 applicable text cases, with
116 mismatches across ten source owners. Those are synthetic content evaluations
repeated across derived font/zoom bands, **not 116 missing labels in a map**.
Expected strings include the original uppercase transform where applicable.
The audit uses native text-requested columns and NULL for absent properties.
It selects the appropriate water name arm, but does not evaluate full source/
native class, geometry, zoom or feature eligibility.

| Coverage cell | Verdict | Evidence / outstanding action |
| --- | --- | --- |
| C19: all 14 original symbol owners and all 39 native rules, QGIS 3.44.11/Qt 5.15.17 and QGIS 4.2.0/Qt 6.9.2 | PASS (scoped inventory) | Every native rule maps to one source owner; original text/transform, processed expression, native field requests, complete settings and explicit case results are public. Inventory completeness is not content correctness. |
| C19: country and major settlements; water-line and water-point companion populations | PASS (scoped content) | Four owner families preserve tested English, NULL/missing, empty, accented, mixed-script and English-only values. The existing two-owner native repair remains intact; water uses 16 complementary English/local rules, not a missing fallback. |
| C19/C02: native water companion selection, five classes × two geometry populations × eight name cases | PASS (scoped regression) | 80 cases in QGIS 3.34.4, 3.44.11 and 4.2.0 assert the ordered 16-rule population before lookup, include predicate/text field requests, and require exactly one matching arm with the expected string. This is not a new scale/worldview/geographic coverage pass. |
| C19: road, waterway, natural line/point, POI, subdivision, minor settlement, state and continent | OPEN | All nine owner families retain local-name-only expressions, sometimes uppercased; English-present/empty/English-only cases differ from source. Exact owner/derived-rule and existing-override guards are needed before repair. Other eligibility defects remain independent. |
| C19: airport code/name contract | OPEN | At sizerank 15 the source requires ref, not name. Cairo's observed feature has `ref: CAI` and renders CAI in the reference; both native maps show the local airport name. Lower-rank ref/name composition also differs in native evaluation. A generic coalesce-only repair is insufficient. |
| C19: Cairo/Jerusalem region z8 and urban z14, both Docker PNG runtimes | OPEN (geographic corroboration) | Matched native-size crops show local Arabic/Hebrew roads versus source-requested English/transliterated names. Major settlement names retain the earlier repair. These extents are new; they are not a fresh seven-preset sweep. |
| C17/C19/C20/C21: actual RTL glyph shaping, bidi/curved-line association, fallback fonts and collisions | PARTIAL observation; correctness NOT ASSESSED | Arabic/Hebrew glyphs appear in the native PNGs. Neither exact string evaluation nor visible glyph presence establishes contextual joining, ordering, per-glyph font resolution or correct placement. No forced-local browser or RTL-plugin diagnostic is claimed. |
| C01/C29: four cameras, source and separate Mercator references, two native builds | PASS (scoped controls/registration) | All eight browser and eight native PNG repeat pairs are byte-identical. Native settings/context repeat too; each runtime's four label inventories equal its offline audit. Forty actual Mercator anchor comparisons are within 1e-6px. |
| C01/C23/C28 and remaining C19 output/edge cases | OPEN / NOT ASSESSED | QGIS 3 uses 100 DPI, QGIS 4 uses 96 DPI; requested/native style zoom remains different. No long-name, missing-font, actual desktop, PDF, pan/zoom or source-globe equivalence pass. |

The fresh inventory contains **16 browser PNGs and 16 native PNGs**. Browser
source properties are from queryRenderedFeatures, not a native decoder trace;
live tile bytes remain unarchived. Full maps, unscaled 380×300 crops, original
source-projection references, primary requested/resolved font settings and
per-frame runtime metadata are retained. Source-language fidelity and common
road/airport reader tasks remain OPEN; no aggregate error score or extra local
labels compensates for the missing source content.

Full local tests pass 2676 / 190 skips with 299 subtests; both complete Docker suites
pass 215 / 82 skips. The legacy native companion test passes 80 cases. All runtime,
activity, font and packaging inputs are unchanged, so no new ZIP or output
behavior is asserted. Next: repair a bounded audited content owner population,
keeping water companions, source transforms and role/zoom gates intact; audit
actual RTL shaping separately. All wider C01–C30 gaps remain required. No
limitation, release, deployment or holistic completion is accepted here.

### C12/C15: ordinary national-background paint and disputed guard — 2026-09-14

The [national-background evidence][national-background] tests one bounded
source-backed correction. Before is `c11b77ee2c5b6e99f807690d29f688721aa81f2e`;
guarded runtime After is `58df4e72b88da58e9b3bab5d1fd34f219b7fd241`.
The fresh source SHA256 remains
`87413e46c074e13aef420958a3ad101961766e6645336608e399ceccaffc6d32`;
all five complete boundary source owners match the fixture.

A broad shared-background correction was **rejected**: its wider continuous
halo dominates the still-thin disputed core in actual Kashmir/Cyprus detail.
Twenty completed QGIS3 broad maps and explicit Before/rejected/retained crops
are preserved. Interrupted frames are excluded. The retained correction applies
only to the already-repaired ordinary core's `disputed IS 'false'` population,
without changing source-owner eligibility or political classification.

Exact Light `admin-0-boundary-bg` gets source-linear width 5.2px at z3 to 10.4px
at z12, clamped and converted once by 25.4/96, and source opacity 0 at z3 to 0.5
at z4, clamped. Native data-defined opacity is a percentage, not a multiplier.
True/NULL/empty/other disputed values retain the actual converted width and
35% opacity. The unchanged static opacity getter therefore remains 0.35 even
when ordinary-feature effective opacity is 0.5. Unique source owners, exact
source predicates and paint, and the already-repaired native ordinary core
are required. Existing native overrides/custom symbols are preserved. Blur,
color, order, filters, zoom gates and all other boundary paint stay unchanged.

The new matrix has 24 cameras: seven Light presets, Kashmir z6.9/7/7.1,
Cyprus z7, Swiss/US subdivisions, opacity z2.9/3/3.1/3.9/4/4.1, Lausanne width
z11.9/12/12.1 and two synthetic activity overlays. Both Docker runtimes use
1280×900, EPSG:3857 and their unchanged default DPI 100/96. All 48 native Before
repeat pairs and 48 browser repeat pairs are byte-identical. All 48 guarded-head
native recaptures match the initial narrowed candidate `93fcf48` in PNG bytes,
complete labels, contexts and all boundary properties. The published audit
records 240 actual browser/native Mercator anchor comparisons within 1e-6 pixel.
Original source-globe references remain separate; native/source style-zoom,
physical density and globe mismatch are **not resolved** by this registration.

**Semantic paint correctness is not universal fidelity improvement.** Planar
MAE relative change is +0.628007%/+0.261680% for the overview and
+0.560810%/+0.380376% for Zurich region (QGIS3/4; positive is worse), while
Lausanne improves −0.159515%/−0.204019%. Source-globe overview also worsens
(QGIS3 +1.68648%). Larger source-intended ordinary backgrounds are retained;
blur/compositing/style-zoom fidelity remains OPEN, not noise or an accepted
limitation. Maps and native-size detail crops were inspected independently of
these aggregate metrics. Four urban cameras and the US admin1-only camera
are byte-identical Before/After. Disputed detail `(450,180,870,480)` in all
three Kashmir zooms is unchanged in both runtimes; this is not a whole-Kashmir
or mixed-status Cyprus identity claim.

| Coverage cell | Verdict | Observation / remaining work |
| --- | --- | --- |
| C12/C15: ordinary-only background source width/opacity | PASS (scoped mechanism) | 14 zooms × four disputed states × expression/96DPI/192DPI paint = 168 native cases per runtime, including clamps, requested field and opacity override. Core/source coupling and native-override guards are tested. |
| C15: disputed fallback and other boundary owners | PASS (scoped preservation); broader paint OPEN | Only target background width/opacity properties change; status fallbacks and Kashmir disputed crops are preserved. Broad shared correction rejected; disputed/admin1 texture and blur remain unresolved. |
| C01/C23: 24-camera matrix and static stop triplets | PARTIAL | Fixed cameras and registered Mercator anchors, unchanged labels/native contexts and 48 final-code recaptures. Source/native zoom and density still differ; no interactive transition or seam pass. |
| C15/C04: ordinary-border visual fidelity | OPEN (mixed) | Lausanne improves modestly; overview/Zurich metrics worsen. Source-intended width/opacity is restored, not complete boundary fidelity. No limitation accepted. |
| C25/C26: two synthetic overlay extents | PARTIAL (diagnostic) | Categorized Run/Ride/Hike lines remain visible in both runtimes. Real sparse/dense/shared routes and UI/accessibility coverage remain required. |
| C28: actual one-map PDF96/150/192, Lausanne/Kashmir | PARTIAL | 48 primary PDFs use production settings, locked page/extents and matched viewing scale. Eight supporting native PNGs match the matrix; this is not a complete atlas task or desktop path. Density-dependent detail remains open. |
| C29: 48 native control pairs and stable PDF modes | PASS (scoped repeats) | All native pairs repeat exactly. 20 of 24 new Before-or-After PDF repeat modes are raster-identical; PDF byte identity is not claimed. Public-generator replay reproduces 20 predeclared stable raster cells and four supporting native frames exactly. |
| C29: QGIS4 PDF150, Lausanne/Kashmir | OPEN (cause/severity unestablished) | Before/After repeats differ 423/164 pixels in Lausanne and 189/45 in Kashmir. Public replay initial outputs differ 81/260 pixels from primary candidate initial outputs. Extends the earlier Bern/Geneva finding; not classified as harmless. |
| Other required criteria/output/geography/accessibility cells | Unchanged | No absent fixture promoted to PASS; C01–C30 completion remains blocked by the recorded open/partial/unassessed cells. |

The immutable package contains 242 native PNGs, 96 browser PNGs and 72 actual
PDFs, including retained controls, diagnostic probes, rejected completed maps
and 24 public-generator replay PDFs. Counts exclude derived crops/rasterizations.
Named PDF operands, hashes and a metric verifier remove pairing ambiguity.
Public capture workers verify the source and all 233 runtime Python file hashes.
Live tile payloads are not archived. The initial mutable-source 30-frame matrix
was invalidated in full and replaced using fixed checkouts; obsolete-image
preflight failure generated no valid frame. Protected Gateway and per-container
access passed for the replacements. No failed, blank or aborted capture is
counted as valid. Historical sections below retain their original scope.

### C12/C15/C23: remaining boundary owners and real status fixtures — 2026-09-14

The [fresh source-status audit][boundary-status] adds six cameras and native
contract tests, **without changing production rendering**. Baseline
`be2d187939b01f81274e2847f011ac134c2f50e7`; source SHA256 remains
`87413e46c074e13aef420958a3ad101961766e6645336608e399ceccaffc6d32`,
with all five complete boundary-owner fixtures matching the fresh source.

Kashmir requested z6.9/7/7.1 and Cyprus z7 expose disputed features and worldview
variants. Swiss cantonal borders z8 and US state borders z7 provide two admin-1
extents. Both QGIS 3.44.11/Qt5 and 4.2.0/Qt6 use their unchanged native DPI 100/96.
Twelve browser PNGs and 24 native control/repeat PNGs are byte-identical within
every camera/runtime pair. Sixteen additional owner-removal PNGs attribute
visible disputed/national-background and subdivision/background paint, with
complete labels/settings, native context and nonremoved boundary rules unchanged.

**Status semantics are not the paint defect.** The new native regression covers
2,240 combinations per runtime across all five owners: admin levels 0/1/2/NULL,
true/false/empty/NULL status strings and seven worldview values including
nonmatching and comma-separated values. Ordinary/disputed national cores remain
separate; their background intentionally includes both. Admin-1 owners do not
require a disputed value. All five exclude maritime features and require the
source's exact `all` or `US` worldview value. Native minimum zooms and owner order
are asserted. The same test passes host QGIS 3.34.4 and both Docker generations.

Offline replay of 365 distinct observed source-property/owner combinations per
runtime also matches the source contracts. Public browser queries retain loaded
source-tile properties and rendered-feature geometry. They include duplicated,
buffered and offscreen fragments, **not** unique-feature counts or a QGIS decoder
trace. Cyprus's loaded source query includes maritime=true/CN fragments; they
are excluded in predicate replay and absent from rendered queries. This is not
a second maritime geographic fixture or an all-worldview rendering pass.

| Coverage cell | Verdict | Observation / remaining work |
| --- | --- | --- |
| C02/C15: all five native owner/status/worldview contracts, three native builds | PASS (scoped eligibility) | 2,240 synthetic combinations per runtime; source and actual native predicates agree. Missing disputed values are intentionally eligible for background/admin-1 owners. No status filter repair is warranted by these cases. |
| C02/C15: observed properties from six browser cameras, both Docker converters | PASS (scoped replay) | 365 property/owner combinations per runtime. Saved source-property replay, not native decoded-feature/request tracing. |
| C15: actual disputed/worldview and subdivision geographic fixtures | PARTIAL | Kashmir/Cyprus and Swiss/US extents plus both-runtime owner-removal maps identify visible paint. Maritime samples are loaded-tile exclusion evidence only; broader geography/worldviews, seams and outputs remain required. |
| C12/C15/C23: remaining owner paint and z7 texture | OPEN | All four untouched widths remain constant; admin-1/disputed cores use post-z7 dashes even below 7. Background opacity stays 0.35 rather than source ramps to 0.5. Blur remains unvalidated. Full maps show much fainter lines despite source-valid eligibility. |
| C01/C29: unchanged repeats and comparability | PASS (scoped repeats); C01 OPEN | Twelve browser and 24 native controls repeat identically. Source globe is preserved; no new anchor registration or source/native zoom/DPI equivalence is claimed. Six added cameras are not a fresh seven-preset sweep. |
| C28 and other required output/activity/accessibility cells | NOT ASSESSED by this slice | No new desktop/PDF/atlas/real-activity/UI or accessibility result. Production/runtime/package files are unchanged, not freshly certified in all paths. |

Native paint inventories isolate the next hypothesis: admin-1 core width is fixed
0.10500651 mm, disputed core 0.18201128 mm; backgrounds 0.42002604/0.72804514 mm.
Only the already-repaired ordinary national core retains source zoom-dependent
width. Native admin-1 custom dash is 0.210013/0.210013/0.630039/0.210013 mm;
disputed is 0.364023/0.273017 mm at every probed zoom. Source below 7 instead asks
continuous admin-1 `[2,0]` and disputed `[3,2,5]`, switching at 7. This is a
source-backed paint/transition lead, **not a promoted correction** or permission
to discard worldview/maritime/disputed semantics. Coordinate eventual dash/width
repair with the still-open native/source zoom and density lifecycle.

All actual maps and native-size owner/transition crops are public with exact
worker reproduction, source/runtime/font snapshots and named artifact hashes.
An inherited contrast heuristic rejected the sparse US QGIS 4 map at stddev 4.927;
manual full-map inspection confirms towns/roads/landcover and the state line,
with pixel extrema 123–255 and owner-removal movement. This was a false validity
heuristic, not a blank capture or a relaxed cartographic acceptance gate.

Full local: 2672 passed / 188 skipped. Complete Docker suites: 213 passed /
82 skipped each; diff-check pass. No package inputs changed, so no new ZIP behavior/build claim. Live tile bytes remain
unarchived. C15 and all other outstanding C01–C30 cells stay open as recorded;
no limitation, release, deployment or holistic completion is implied.

### C01/C28: offline native mechanism and rejected matrix calibration — 2026-09-14

The [credential-free native reproduction](https://github.com/ebelo/qfit/tree/59b1de40f4297a776f535c3ce6687fedf8d7e6cc/docs/visual-evidence/issue-1462/offline-density) removes live Mapbox data,
fonts, labels, qfit conversion and browser registration from the density diagnosis.
Both exact Docker builds run with **network disabled**, using the same archived
synthetic MBTiles SHA256
`331aae17f15dabad61a63a32cacea8047f799ca1b5ae09599de5b2ba1a0dedf4`.
Baseline is `75c6fdfad279d0eda11c5faad2c91e61753787c3`; this update changes only
documentation. No fresh real-Light reference or product rendering fix is claimed.

Three synthetic bent lines have independent roles: persistent red, native
minimum-zoom13 blue, and native zoom-dependent green width. At fixed EPSG:3857
extent,169.3333×127mm page and scale60732.872199, QGIS4 PNG and PDF zoom changes
**12.318207 →12.923653 →13.318207** at96/150/192DPI; blue is absent at96 and
present at150/192. QGIS3 stays12.220213/integer12. These actual untraced outputs
establish that native activation changes without qfit or live-provider inputs.
They do not certify Light geometry, labels, full atlas, desktop or accessibility.

The final baseline has24 native PNGs and24 actual PDFs. All72 explicitly named
plain/traced/repeated RGB comparisons are identical; PDFs are viewed at96DPI.
No PDF-file identity claim is made. Synthetic repeat stability does **not** explain
or close the two real-label QGIS4/PDF150 variation cells from#1471. PDF scopes
again supply `@map_scale`, while parallel PNG scopes lack it.

**Candidate rejected as-is:** switch the fixture layer's matrix to Esri mode and
scale denominators by `96 ×0.00028 /0.0254 /2`. This makes native zoom
DPI-invariant over12.25/12.9/13/13.1 in both runtimes, but:

- At nominal13, floating-point extent/scale produces12.999999999999988; flooring
  activates12 and hides the minimum-zoom13 feature in actual PNG/PDF output.
  It returns at13.1. No epsilon or logarithmic-zoom correction is validated.
- `layer.tileMatrixSet()` is **mutable** in these builds despite no layer setter.
  Native `layer.clone()` loses the calibrated method/scales; project save/reload
  preserves them. This is an independently probed native lifecycle limitation,
  not a claim that the current qfit atlas clones the basemap.

The candidate has96 native PNGs and96 PDFs, with288 named within-cell pairs
pixel-identical. Four zooms, three densities and both output paths/runtimes are
covered, not other CRSs or older native builds. The public evidence contains
exact generators, the shared tile fixture, original PDFs, fixed-DPI rasters,
mode/triplet panels, actual scope traces and clone/save/reload probes. Initial
blank/invalid fixture attempts are excluded. All final processes completed.

| Coverage cell | Verdict | Next action / boundary |
| --- | --- | --- |
| C01/C28: native density mechanism independent of provider/conversion | PASS (scoped reproduction); product defect OPEN | QGIS4 source normalizes scale before fetch/render zoom and style scope; a label-expression-only patch cannot coordinate them. |
| C01/C23/C28: simple layer-local matrix calibration | OPEN (candidate rejected) | Resolve exact-boundary handling, source fractional zoom, native clone lifecycle and actual product scopes before promotion. |
| C29: synthetic repeat controls | PASS (scoped synthetic repeats only) | Does not close real-Light PDF150 variation, labels or interactive stability. |
| Remaining C01–C30 real-map/output cells | Unchanged | No additional real geographic, language, topology, activity, UI, atlas or desktop coverage is inferred. |

The lack of a setter is **not** an established API blocker. No workaround or
limitation is accepted; future robust matrix calibration remains investigable.
Continue source-role/handoff and the remaining major semantic/fixture gaps.

### C01/C28/C29: logical-density versus actual PDF output — 2026-09-14

The [fresh two-city output audit][density-output] extends the density finding to
**real one-map PDF files**, while separating QGIS's device-pixel-ratio API from
physical export density. Production/source baseline is
`3ff79a9dbced1dd57cf9763963d5758b5a5a1af7`; this slice changes documentation only.
Light SHA256 remains `87413e46c074e13aef420958a3ad101961766e6645336608e399ceccaffc6d32`.
No production styling, source/filter eligibility, font, capture default or PDF
setting is changed; no workaround or limitation is accepted.

Both Bern (actual requested camera12.25) and Geneva (14.25) use the same extent,
source and openly licensed resolved Docker fonts, in QGIS3.44.11/Qt5.15.17 and
4.2.0/Qt6.9.2. Original-globe and explicitly requested Mercator references are
retained separately: their PNGs happen to match at these two urban cameras,
with five planar anchors each within1e-6px. This is not an overview/projection
pass or a new seven-preset sweep.

**Device-pixel ratio is not print DPI.** At96DPI and1280×900 logical pixels,
`setDevicePixelRatio(2)` produces2560×1800 device pixels without changing native
tile zoom in either runtime. Four pass-through renderer traces preserve PNG
bytes and confirm actual activation. All12 initial native mode/repeat cells
(24 PNGs) are byte-identical, with complete label/style settings preserved.
DPR2 previews are explicitly reduced2×; neither label-placement identity nor a
real high-DPI desktop is certified. Saved PNG metadata remains96DPI, so these
files must not be advertised as standalone same-physical-size print exports.

**Actual PDF path.** A standalone one-map `QgsPrintLayout` uses the captured
Light layer, locked layer set, same CRS/extent, and338.6667×238.125mm page/map
size (960×675 PDF points). It calls the real
`AtlasExportTask._build_pdf_export_settings()`:150DPI,
`forceVectorOutput=True`, `rasterizeWholeImage=False`; only DPI varies for96/192
diagnostics. Each of12 camera/runtime/DPI cells has unwrapped and traced exports,
each repeated:48 actual PDFs, rasterized by Poppler at a fixed96DPI for inspection.
This exercises production PDF settings, **not the complete atlas builder/task,
cover/TOC/activities, packaged installation, map-context UI or another platform**.

The [executable generator][density-generator] retains the original rendering/PDF
worker byte-for-byte and exposes the production helper invocation; only private
paths/bootstrap are replaced by explicit arguments. Its [same-run replay][density-replay]
in both runtimes and both cities produces four identical supporting PNGs and24
additional PDFs with matching contexts. The20 predeclared stable rasterizations
match; the QGIS4/150DPI category retains the disclosed variability. Commands,
prerequisites and worker hashes accompany the generator, not just settings claims.

| Output / same physical map scale | QGIS3 Bern / Geneva native zoom | QGIS4 Bern / Geneva native zoom |
| --- | --- | --- |
| PDF96DPI | 12.220213 /14.220213 | 12.318207 /14.318207 |
| PDF150DPI (production setting) | 12.219896 /14.219896 | 12.923461 /14.923461 |
| PDF192DPI | 12.220213 /14.220213 | 13.318207 /15.318207 |

QGIS4 integer activation changes12→13→13 and14→15→15. Unwrapped PDF maps show
additional road/POI/building detail, including Felsenauviadukt/Universität Bern
and central Geneva. This confirms the **OPEN/provisional-major print-density
finding** independently of the earlier PNG diagnosis. QGIS3 retains integer12/14
but still changes label placement (Bern Länggassstrasse and Geneva Boulevard
Georges-Favon); its tiny150DPI continuous residual is about0.000316. Stable native
zoom alone does not establish output consistency in either runtime.

**Measured repeats, not presumed noise.** Ten of12 PDF cells (all QGIS3 and
QGIS4 at96/192DPI) have identical decoded raster output across all four exports,
including trace isolation. At QGIS4/150DPI, the unwrapped Bern and Geneva repeats
change280 and145 pixels; traced-initial versus traced-repeat changes240 and246.
The [named-pair audit][density-pairs] identifies both operand filenames and hashes
for every comparison. The older `pdf-trace-isolation.json` uses **unwrapped initial
as the reference for every row**: its `trace-repeat` row therefore reports280/145
for unwrapped-initial versus traced-repeat, not for the within-trace repeat pair.
No metric values were corrected; the new audit makes the differing pairs explicit.
Traced/unwrapped comparisons also vary. These low-amplitude changes are retained and quantified,
not classified as established noise or a C29 pass. PDF timestamps also differ:
no PDF-file byte-identity claim is made. Native trace values repeat exactly,
but strict pixel-isolation at150DPI is **not** certified; the96/192PDF and DPR2
PNG traces are independently pixel-identical to their controls. The visible
print-density finding occurs in unwrapped PDFs, not just traced probes.

**Expression scope is output-specific.** PDF traces have actual `@map_scale`
values60732.872199 and15183.218050; the parallel PNG trace still lacks that
variable. The earlier headless-scope observation is not a universal QGIS/API
limitation or proof about the desktop. A future source-zoom correction must
coordinate the actual output scopes and major/minor handoff, not inject requested
zoom or compensate geographic extent.

| Coverage cell | Verdict | Remaining scope / next action |
| --- | --- | --- |
| C01/C28: two-city96DPI DPR1/DPR2 native PNG activation, both runtimes | PASS (scoped measurement); output parity PARTIAL | Actual traces and repeated real maps; not desktop scaling or standalone PNG physical-size certification. |
| C28: two-city one-map PDF at96/150/192DPI, both runtimes | OPEN | QGIS4 print activation/detail changes; both runtimes show density-sensitive label placement. Investigate coherent render-context/label behavior; do not change production DPI to hide it. |
| C29: repeated settled PNGs and10 PDF cells | PASS (scoped repeats) | All24 initial PNGs repeat exactly; four DPR2 trace PNGs and eight PDF-worker supporting PNGs match controls. Ten PDF cells have identical fixed-DPI rasterizations, not identical PDF bytes. |
| C29: QGIS4 PDF150DPI, Bern/Geneva | OPEN (cause/severity unestablished) | Quantified variability in traced and unwrapped repeated outputs. Not a cold/warm cache or interactive-performance assessment. |
| C01/C02/C23: actual expression scope/source zoom and role handoff | OPEN | Map-scale availability differs between parallel PNG and layout PDF; no deployable rank/zoom repair retained. |
| C28/C30: complete atlas, packaged desktop, activities and output context | NOT ASSESSED for those cells | One-map PDFs do not validate the full product path, legends, attribution UI, accessible physical sizes or font distribution. |

DPR2 is rejected as a substitute for a print-density fix. No change to geographic
extent, source projection or production PDF defaults is retained. Full maps,
readable mode-labelled crops, original PDFs, repeats, expression traces, exact
runtime/source/Python hashes and resolved font inventories are public in the
audit. Live tile payloads remain unarchived. All other C01–C30 gaps remain as
recorded; this bounded validation slice does not complete #1462.

### C01/C28: corrected renderer scale and physical-density diagnosis — 2026-09-14

The [fresh scale audit][scale-calibration] corrects **QGIS4 capture metadata** and
adds native geometry/density fixtures. Baseline
`6d8935571d83ba21f6024e27b06de88860374252`; metadata implementation `1a5fd9a`.
No production style, renderer, font, activity or capture-default change is retained.
The Light source SHA256 remains
`87413e46c074e13aef420958a3ad101961766e6645336608e399ceccaffc6d32`.
Original globe and explicit planar reference modes remain separate.

**Historical metadata erratum:** the snapshot introduced in #1466 passed raw
`map_scale` directly to tile-matrix zoom methods. QGIS3's Mapbox renderer does
that, but QGIS4 first normalizes scale by reference DPI / output DPI. Historical
QGIS4 zoom fields without `tile_render_scale` are therefore raw-matrix evaluations,
**not actual renderer activation**. Original PNGs, recorded map DPI/extents,
source/label inventories and controlled image comparisons remain valid; immutable
artifacts are not rewritten or called fresh. Their QGIS4 zoom interpretation is
superseded by this correction, including earlier sections below.

The corrected snapshot calls native `calculateTileScaleForMap()` with actual map
scale, CRS, extent, size and output DPI. It records `map_scale` and
`tile_render_scale` separately, deriving continuous/render/fetch zoom from the
latter. Native regressions independently compare against `scaleForRenderContext()`
with a real painter; mock tests force different raw/render scales. An eight-map
pass-through road-width expression trace records the renderer's actual
`@vector_tile_zoom` and `@zoom_level`; every traced PNG is byte-identical to its
unwrapped control and the variables match corrected metadata.

| Requested camera / DPI | Actual QGIS3 zoom | Actual QGIS4 zoom |
| --- | --- | --- |
| Geneva z13 /96 | 12.941732 | 13.000000 (within floating precision) |
| Geneva z13 /100 | 12.897638 | 13.000000 (within floating precision) |
| Geneva z13.1 /96 | 13.025203 | 13.133934 |

Both builds still interpolate fractional zoom linearly in scale; source camera
zoom is logarithmic. The native tile matrix uses 0.28 mm standard pixels and a
Mapbox 512/256 factor. Equalizing96DPI does not make both runtimes' fractional
activation source-equivalent. The registered Geneva z13 crop still retains the
QGIS-only city name at both default and diagnostic96DPI. **DPI-only calibration
is not retained as a production/harness fix.** Geographic extent compensation
would destroy the independently verified planar registration.

**New output-consistency finding:** at identical geographic extent and physical
map size, QGIS4's doubled-density PNG changes visible detail and label selection.
Bern requested CSS z12.25 is actual12.318207 at1280×900/96DPI, but13.318207 at
2560×1800/192DPI; Geneva14.25 similarly changes14.318207→15.318207. QGIS3 stays
at12.220213 /14.220213. Map scale is unchanged in both. Real maps, corrected
metadata and pass-through renderer traces establish this difference; no output
limitation is accepted. C28's density-consistency cell remains **OPEN**.

| Coverage cell | Verdict | Evidence / remaining scope |
| --- | --- | --- |
| C01: planar geometry, 19 cameras × five browser anchors, both native runtimes | PASS (scoped registration) | Seven presets plus Geneva/Bern z13/z14 triplets; browser anchors compared with actual native extent/pixel transforms within1e-6px. Original globe is separately recorded, not declared equivalent. |
| C01: corrected renderer-scale measurement | PASS (scoped metadata) | 38 default-camera recaptures preserve PNG/labels/style bytes; only context metadata changes. Eight pass-through renderer traces verify actual variables; both complete native suites and legacy3.34.4 pass. Historical QGIS4 raw-matrix zoom claims are corrected, not silently reused. |
| C01/C29: default and96DPI repeated controls | PASS (scoped repeats/isolation) | 38 default pairs plus38 DPI96 pairs, all152 PNG/label/style/runtime repeats byte-identical. All19 QGIS3 DPI96 probes change pixels; QGIS4 is already96 and unchanged. No semantic/usability pass follows from metric movement. |
| C28: Bern/Geneva physical-density outputs, both runtimes | OPEN (actual QGIS4 output divergence) | Four192DPI PNG cells plus repeats and corrected-context recaptures. Same extent/physical scale and label/style settings; actual QGIS4 activation increases by1 and visible detail/labels change. Downsampled previews are labelled; no desktop/PDF or pixel-identity assertion. |
| C01/C28: native geometry at three viewport shapes × five proportional pixel/DPI factors ×19 cameras | PASS (numerical geometry only) | 285 native cases per runtime verify extent, physical map scale and transformed center. They do not assert renderer-zoom invariance or newly rendered portrait/small/UI coverage. |
| C01/C02/C23: fractional source zoom, expression scope and major/minor handoff | OPEN | Actual renderer traces find no `@map_scale` in this harness's existing expression scope. A logarithmic formula evaluated in an explicitly constructed map-settings scope is diagnostic, not a deployable label fix or proof of availability in the live job. Coordinate source-role eligibility, scope and integer activation before another rank repair. |

The six-DPI offline audit records114 settings cells per runtime and explicitly
separates raw-matrix zoom from runtime-specific renderer zoom. Its logarithmic
96-DPI expression has sub3e-13 reconstruction error in the constructed scope;
this does not fix the observed live-scope gap. An initial trace wrapper propagated
that missing variable as NULL and changed widths; it is **invalid evidence** and
excluded. The retained pass-through trace handles the missing value explicitly
without changing original width results.

Shared-metadata isolation also covers all seven Outdoors cameras:14 fresh
source-preserving browser PNGs and42 native Before/Repeat/After PNGs across both
runtimes. Native image, complete label and preprocessed-style bytes are unchanged;
only metadata is corrected. This is a shared-harness guardrail, not Outdoors
product work or a projection/parity pass. Both278-entry plugin ZIP payloads equal
main; both package builds and nine package checks pass.

Full local tests pass2672/187; both complete Docker suites pass212/82. Source
runtime behavior and capture defaults remain unchanged. The numerical geometry
fixture also passes285 cases on native QGIS3.34.4. Live tile payloads remain
unarchived; actual desktop/PDF, activity/UI, accessibility and all other C01–C30
coverage gaps remain open where recorded. No release, deployment or accepted
limitation is implied.

### C01: source-preserving browser projection evidence — 2026-09-14 scoped update

The [fresh browser-context evidence][browser-projection] adds actual browser
measurement and an **explicit diagnostic**, not a production renderer change.
Baseline `1418e8ec1497c0865453a64a9eca0ae59a07fe53`; implementation
`d95175b`. Both source snapshots still declare globe: Light SHA256
`87413e46c074e13aef420958a3ad101961766e6645336608e399ceccaffc6d32`,
Outdoors `da68d8ece0bb90c6d45fb36085b1e64f9d9e966175f1abf31fcddbf28bc1504c`.
Outdoors is a shared-harness isolation guardrail, not new Outdoors styling work.

The default browser constructor preserves source projection. Optional
`--reference-projection mercator` changes only that constructor, not the source
snapshot, fingerprint, preprocessing, native layer or plugin. The manifest and
`browser-runtime.json` identify source-declared, requested and actual configured
projection, actual camera/bounds/canvas/DPR, browser/Mapbox versions and load state.
Map errors or unloaded maps/tiles reject capture before PNG; metadata follows a
successful screenshot. Error payloads/URLs are not retained in that snapshot.

| Coverage cell | Verdict | Evidence and remaining scope |
| --- | --- | --- |
| C01: browser context, both seven-camera presets, source and explicit planar modes | PASS (scoped measurement) | 70 fresh browser captures: all 14 default Before/After/Repeat PNGs and all 14 Mercator repeat pairs are byte-identical. Actual context and zero map errors recorded; nonblank maps inspected. This is not class-completeness or matched-scale certification. |
| C01: source intent versus planar diagnostic | PASS (scoped separation); geographic/product scope OPEN | Original globe reference remains separate. Only the two overview PNGs change between modes; the other 12 views are byte-identical. `getProjection()` still reports configured globe at high zoom, not its per-pixel planar blend. Earlier overview anchor registration remains the explicitly dated diagnostic above, not a new all-camera registration claim. |
| C28/C29: native isolation and repeated settled PNGs | PASS (scoped unchanged output) | 28 camera/runtime cells × Before/Repeat/After = 84 PNGs in QGIS 3.44.11/Qt 5.15.17 and 4.2.0/Qt 6.9.2. Every cell's PNG, full labels, preprocessed style and actual native context is byte-identical. Both 278-entry plugin ZIP payloads equal baseline. No desktop/PDF, activity UI, performance or temporal-pan pass. |
| C01/C02/C23: physical DPI, native style-zoom and role handoff | OPEN | Mercator reference selection does not resolve native100/96-DPI differences or continuous/integer source-rule activation. No new rank/filter candidate is promoted. |

Both complete Docker suites pass 211/82; full pytest 2672/186 with 299 subtests;
additional isolated unittest 2854/186; nine package tests pass. Generated browser
JavaScript is exercised by Node regressions (actual-context recording, projection
preservation, incomplete-map rejection and artifact ordering); manifest/CLI
propagation is tested through the normal configuration path. All 16 changed Python
statements are covered. These gates do not close C01 or the holistic ledger.
Source/planar metrics are recorded separately, not called native rendering gains.
Live tile payloads remain unarchived; no limitation is accepted on Emman's behalf.

Next: establish coherent source/native geometry and style-zoom calibration before
another C02 settlement-role repair. Keep all other coverage cells below open where
recorded; browser projection metadata is not new RTL/topology/activity/accessibility,
packaged-font/desktop/PDF or map-attribution validation.

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

[browser-projection]: https://github.com/ebelo/qfit/tree/9270b210cd624ddf0eaaa5ddbffe6c8dd29d374b/docs/visual-evidence/issue-1462/browser-projection

[scale-calibration]: https://github.com/ebelo/qfit/tree/82482c430e71b6cc78b4d58cac003d1f669675c7/docs/visual-evidence/issue-1462/scale-calibration

[density-output]: https://github.com/ebelo/qfit/tree/d52b956d51819039bc8fdd0ab9535a9776ba9354/docs/visual-evidence/issue-1462/density-output

[density-generator]: https://github.com/ebelo/qfit/blob/d52b956d51819039bc8fdd0ab9535a9776ba9354/docs/visual-evidence/issue-1462/density-output/density_capture.py
[density-replay]: https://github.com/ebelo/qfit/blob/d52b956d51819039bc8fdd0ab9535a9776ba9354/docs/visual-evidence/issue-1462/density-output/generator-replay.json
[density-pairs]: https://github.com/ebelo/qfit/blob/d52b956d51819039bc8fdd0ab9535a9776ba9354/docs/visual-evidence/issue-1462/density-output/pdf-pair-metrics.json

[boundary-status]: https://github.com/ebelo/qfit/tree/0162c5b445a82da1a33df569f5aa3c2dbe620019/docs/visual-evidence/issue-1462/boundary-status

[national-background]: https://github.com/ebelo/qfit/blob/c6393ee1ae6923b5b5482d1bbbc956f0e0a069ed/docs/visual-evidence/issue-1462/national-background/README.md

[label-roles]: https://github.com/ebelo/qfit/blob/ca29374c534bf280f965e3ed74e81d411e573a9f/docs/visual-evidence/issue-1462/label-roles/README.md
