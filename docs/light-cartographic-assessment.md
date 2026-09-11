# Light: initial holistic cartographic assessment

Assessment date: **2026-09-11**. Tracking issue:
[#1462](https://github.com/ebelo/qfit/issues/1462).
Protocol: [cartographic comparison framework](cartographic-comparison-framework.md).

This is a baseline audit, **not a declaration that Light passes all criteria**.
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

### 3. Label language and content — C19

The recorded original `country-label` and `settlement-major-label` request
`coalesce(get(name_en), get(name))`. The inspected QGIS label snapshots instead
use the expression `"name"`. Regional images show local names where the source
requests English-first names. This is a concrete conversion divergence, distinct
from font width or weight. Test nonempty, missing and empty localized fields and
the exact output strings. Do not silently choose a new product language policy;
if localization is intentional, document that decision separately from fidelity.

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
| C19 | OPEN | Source English-first expression versus QGIS local `name` expression is confirmed. Validate content/null behavior and intended locale contract. | Major |
| C20 | PARTIAL | Some named-road crops inspected during duplicate work; systematic association, rotation and curved-line placement remain. | — |
| C21 | PARTIAL | Current dense views are available; survival/priority decisions and symbol/halo collision extents are not comprehensively audited. | — |
| C22 | PARTIAL; targeted road repeats PASS | PR #1463 validates nearby repeated road-name removal in its seven-camera/two-runtime scope. Settlement/POI density and other repetition mechanisms remain open. | — |
| C23 | NOT ASSESSED | Fixed zooms do not test interval edges or fractional zoom continuity. Add boundary triplets and zoom sequences. | — |
| C24 | NOT ASSESSED | No deliberate tile-edge, clipping, adjacent-pan or world-wrap fixtures. | — |
| C25 | NOT ASSESSED | These captures contain no current qfit activity overlays or UI state. Historical checks are not current certification. | — |
| C26 | NOT ASSESSED | No current sparse/dense activity-on-road/water/forest comparisons. | — |
| C27 | NOT ASSESSED | No grayscale, color-vision, low-vision or target physical-size assessment. | — |
| C28 | PARTIAL | Two Docker PNG runtimes checked. Windows/macOS, older supported QGIS, interactive canvas, high-DPI and PDF require separate cells. | — |
| C29 | PARTIAL | Unchanged repeat controls passed in the prior capture matrix. Cold/warm cache, interactive responsiveness and pan/zoom stability are untested. | — |
| C30 | NOT ASSESSED | Cropped basemap evidence does not validate complete user-facing attribution, legend, scale or north/context requirements. | — |

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
