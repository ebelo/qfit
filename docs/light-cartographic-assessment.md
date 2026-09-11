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
| C01 | PARTIAL | Matched dimensions, style/code hashes and repeated controls are available for these PNGs. Tile payloads are not archived; extended outputs and load completeness need their own evidence. | — |
| C02 | PARTIAL | Source-layer inventory exists; feature-by-feature filter/type/null equivalence is not audited. Build class eligibility fixtures before paint changes. | — |
| C03 | NOT ASSESSED | No generalization, sparse-geometry or false-connection fixture audit. | — |
| C04 | OPEN | Full-map review shows weak QGIS road figure–ground separation and different text prominence, especially Geneva z14. | Major |
| C05 | PARTIAL | Road hierarchy has visible differences; class-to-visual-variable semantics have not been checked systematically. | — |
| C06 | PARTIAL | Broad palette can be compared; class-interior lightness/contrast measurements and adjacent-class tests remain. | — |
| C07 | PARTIAL | Urban/park/land areas appear in existing views. Agriculture, polygon holes and individual land-use class ownership are not validated. | — |
| C08 | PARTIAL | Large water footprints are visually comparable. Minor streams, islands, confluences and water-label association need fixtures. | — |
| C09 | N/A (source-scoped) | Recorded Light inventory contains no contour, hillshade or raster-dem layer. Missing Outdoors-like relief is not a Light defect; reassess if source intent changes. | — |
| C10 | PARTIAL | Buildings appear in the street views; courtyards, transition visibility and road/footprint overlap are not systematically checked. | — |
| C11 | OPEN | Street-network prominence differs in Geneva and Zurich. Inspect class filters, width/rank and actual visible road coverage. | Major |
| C12 | PARTIAL | Stroke differences are visible, but cap/join/dash/casing and fractional-scale ownership are not isolated. | — |
| C13 | NOT ASSESSED | No named bridge/tunnel/at-grade crossing audit against structure attributes. | — |
| C14 | NOT ASSESSED | Source has rail and aeroway layers; no systematic transport distinction/continuity checks. | — |
| C15 | OPEN | Boundary appearance differs around Lake Geneva and regionally. Exact owner and status-filter attribution remain open. | Major |
| C16 | PARTIAL | Source symbol inventory available; sprite applicability, anchors, collision lifecycle and high-DPI behavior require dedicated checks. | — |
| C17 | PARTIAL | Font-enabled Docker roles have earlier scoped validation. Desktop font distribution and multilingual fallback are not certified by these captures. | — |
| C18 | OPEN | Text width, weight, wrapping and relative hierarchy remain visibly different. Blanket size probes were rejected, not accepted as a fix. | Minor |
| C19 | OPEN (remaining scope) | Country/major-settlement English/local fallback now has scoped native-expression and matched-PNG passes below. Other source roles, multilingual/RTL rendering, long names and desktop/export coverage remain open. | Major baseline finding scoped below; remaining severity not established |
| C20 | PARTIAL | Some named-road crops inspected during duplicate work; systematic association, rotation and curved-line placement remain. | — |
| C21 | PARTIAL | Current dense views are available; survival/priority decisions and symbol/halo collision extents are not comprehensively audited. | — |
| C22 | PARTIAL | Road duplicate removal has a scoped pass; the criterion as a whole is not passed. See the separate coverage-cell verdicts below. | — |
| C23 | NOT ASSESSED | Fixed zooms do not test interval edges or fractional zoom continuity. Add boundary triplets and zoom sequences. | — |
| C24 | NOT ASSESSED | No deliberate tile-edge, clipping, adjacent-pan or world-wrap fixtures. | — |
| C25 | NOT ASSESSED | These captures contain no current qfit activity overlays or UI state. Historical checks are not current certification. | — |
| C26 | NOT ASSESSED | No current sparse/dense activity-on-road/water/forest comparisons. | — |
| C27 | NOT ASSESSED | No grayscale, color-vision, low-vision or target physical-size assessment. | — |
| C28 | PARTIAL | Two Docker PNG runtimes checked. Windows/macOS, older supported QGIS, interactive canvas, high-DPI and PDF require separate cells. | — |
| C29 | PARTIAL | Unchanged repeat controls passed in the prior capture matrix. Cold/warm cache, interactive responsiveness and pan/zoom stability are untested. | — |
| C30 | NOT ASSESSED | Cropped basemap evidence does not validate complete user-facing attribution, legend, scale or north/context requirements. | — |

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
