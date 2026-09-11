# Holistic cartographic comparison framework

This is qfit's review protocol for basemap and activity-map changes. It applies
to Light and Outdoors with **preset-specific expectations**, not one shared
appearance. The [capture harness](mapbox-outdoors-comparison-harness.md) produces
the evidence; this document defines what reviewers must examine. Use the
[Light assessment](light-cartographic-assessment.md) as a worked, deliberately
incomplete coverage ledger for [#1462](https://github.com/ebelo/qfit/issues/1462).

## 1. What “better” means

Assess four dimensions separately:

1. **Semantic correctness:** the right features, classes, names and relationships
   are represented. A prettier map with missing roads or misleading symbols fails.
2. **Cartographic usability:** readers can locate themselves, understand the
   hierarchy, and follow qfit activities at the intended viewing size.
3. **Reference fidelity:** the result reasonably expresses the source Mapbox
   style's intent. A departure can be acceptable, but needs an explicit reason.
4. **Operational consistency:** the intended map survives different supported
   runtimes, installed fonts, interactive use and exported output.

Do not collapse these into a weighted “parity percentage.” A semantic failure
cannot be offset by more matching background pixels. Nor is an improvement in
one font, crop or camera evidence that the whole basemap has been validated.

### Graphic semiology

For each point, line, area or label, state **what it represents** and **which
visual variables encode it**:

| Variable | Questions for qfit |
| --- | --- |
| Position | Is geographic position preserved? Is any label displacement unambiguous? |
| Size | Do line width, symbol area and type size express the intended rank? Are size ratios consistent across scales? |
| Lightness/value | Does visual prominence express order without erasing faint but necessary context? |
| Hue | Are categories distinguishable and semantically stable? Is hue being incorrectly read as magnitude? |
| Shape | Do different feature types remain recognizable at their actual display size? |
| Orientation | Is direction meaningful (route arrows) or merely descriptive (road text)? Is it accidentally reversed? |
| Texture/grain | Do dashes, hatching and repetition retain their meanings and density rather than becoming solid fills? |
| Opacity and edge treatment | Do transparency, casing, blur and halos support separation without suggesting a different class or extent? |

Qualitative categories need differentiation, ordered categories need a legible
order, and quantitative encodings need an honest scale. Do not invent an order
between activity types, or treat symbol radius as proportional area. Where no
quantitative encoding exists, record that sub-check as not applicable.

## 2. Evidence contract

Before interpreting a discrepancy:

- Match source/data revision, camera center/extent, zoom, bearing, pitch, CRS,
  dimensions, pixel ratio, scale/DPI, background, language, and activity data.
  Record source **and** QGIS-preprocessed fingerprints and code commits.
- Record QGIS/Qt/browser versions, font files/faces and actual `QFontInfo`
  resolution, fallback glyph coverage, and output path (interactive/PNG/PDF).
- Use the credential route supported by the capture environment; validate
  access inside containers too. Never expose credentials or disable TLS.
  **OpenClaw-managed qfit runs only:** follow that workspace's protected Gateway
  preflight and same-run lifecycle instructions. Require an authorized HTTP 200
  result before capture and keep the run alive until its captures finish; this
  service and its workspace preflight script are not repository dependencies.
  **Other contributors:** OpenClaw/Gateway is not required. Use the existing
  [harness credential setup](mapbox-outdoors-comparison-harness.md), with an
  authorized local token-file or environment-variable input, and check actual
  capture loading/errors. Do not commit credentials or record them in evidence.
- Require complete, nonblank output: an idle event, successful process, or low
  image error alone does not prove tiles, glyphs or sprites loaded correctly.
- Render unchanged controls repeatedly. Preserve fixed seeds where supported,
  but verify repeatability rather than assuming determinism from the seed.
- Retain full maps and matched, unscaled crops with coordinates. For a change,
  label panels **Mapbox reference | QGIS before | QGIS after**. For a baseline
  audit, label runtime comparisons explicitly; they are not before/after proof.
- Compare runtimes independently against their own matched controls. A QGIS 3
  image must not serve as the unchanged control for a QGIS 4 candidate.
- Reused evidence is permitted when provenance still matches the claim. Record
  its capture revision/date, source revision and coverage; do not call it a fresh
  capture or infer that current upstream tiles/styles remain unchanged.

## 3. Inspection matrix

Use the harness's **camera matrix for the preset being changed**:

- **Light:** Switzerland z5, Zurich z8, Lausanne/Lavaux z10, Bern z12, Geneva
  z14, Zurich z17, Geneva z18 (`--preset light`).
- **Outdoors:** Switzerland z5, Valais/Geneva z7–z8, Lausanne/Lavaux z9–z11,
  Geneva airport/motorway z14, Chamonix trails z13–z14, Zermatt piste z17 and
  Zermatt trails z18 (`--preset outdoors`).

Use `--list-cameras` with the selected preset for current identifiers. Give
z8–z14 priority without dropping low/high-zoom guardrails. Inspect each in both
font-enabled Docker generations; consult the current testing policy for tags.
The other preset is an isolation guardrail, never a substitute for capturing
the changed preset. Shared changes require both matrices.

These default views **do not cover all cartographic cases**. Add targeted
fixtures or real extents for:

- sparse/rural and dense urban areas, mountains, coast/islands, complex river
  junctions, bridges/tunnels, road–rail crossings and administrative borders;
- long and repeated names, near-colliding symbols, multilingual/RTL strings,
  diacritics, absent name fields and missing font/script coverage;
- source layer/filter/size transition zooms: test just below, at and above each
  relevant boundary (for example `z−0.1`, `z`, `z+0.1`), plus a short pan/zoom
  sequence. Fixed integer-zoom screenshots cannot establish continuity;
- small/wide/portrait map windows, high-DPI screens, fractional display scaling,
  PDF/atlas print sizes, and activities crossing light/dark/complex backgrounds.

Tag each fixture with the checklist IDs it actually exercises. An absent bridge
in a camera means “not observed,” not “bridges pass.” For each applicable ID,
use at least two representative extents where feasible; a single rare-feature
fixture needs an explicit scope limitation, not invented multi-camera coverage.

## 4. Comparison checklist

For **every ID**, record applicability, observation, severity, evidence, method,
runtime/scale coverage, verdict and next action. The “probe” column describes
validation to perform, not an assertion that tooling or evidence already exists.

| ID | Cartographic point | What to inspect / fail signals | Useful validation or probe |
| --- | --- | --- | --- |
| C01 | Comparable, complete evidence | Shifted cameras, stale source, missing tiles/glyphs, unmatched DPI or unloaded output invalidate comparison. | Manifest/fingerprint checks, network/load diagnostics, dimensions, nonblank content, repeated controls. |
| C02 | Feature and class semantics | Features omitted, duplicated or reclassified by filters; null/type coercion; class/rank/source-layer mismatches. | Source inventory and feature-property fixtures; compare class eligibility before styling, not just visible pixels. |
| C03 | Generalization and detail budget | Simplification removes important geometry, creates false connections or excessive detail; displacement changes meaning. | Named feature anchors, source geometry/zoom comparison, sparse and dense extents. |
| C04 | Global hierarchy and composition | Figure–ground reversal, local roads overpower cities, uniform emphasis, distracting clutter or excessive empty space. | Full maps at intended size; identify first/second/third visual priorities and reader tasks before examining crops. |
| C05 | Visual-variable semantics | Hue suggests magnitude, widths invert road rank, inconsistent icon shapes/texture imply wrong categories. | Write class-to-variable mapping; compare same-class consistency and between-class distinction across scales. |
| C06 | Palette, value and separation | Background/foreground collapse, excessive saturation or darkness, indistinguishable adjacent classes; halos wash out context. | Class-interior color/lightness samples away from edges; local contrast, grayscale and full-map visual review. |
| C07 | Landcover and landuse | Forest/park/agriculture/built-up roles conflated, opacity or layer order hides important categories, polygon holes lost. | Source class inventory and representative adjacent polygons; mask ownership before changing color globally. |
| C08 | Hydrography | Lakes/rivers/streams lose continuity or rank, islands/shorelines vanish, water mistaken for land, names disconnected from water. | Shoreline and confluence crops, width/rank checks, holes and multipart features, water-label association. |
| C09 | Relief and terrain intent | Contours/hillshade overwhelm context or expected relief is absent; elevation labeling is misleading. | First check whether the preset requests these layers. If absent, document N/A; do not import Outdoors terrain into Light by assumption. |
| C10 | Buildings and urban fabric | Wrong footprint visibility, fill/outline order, courtyards lost, footprints hide streets or misalign with them. | Dense/sparse blocks at transition zooms; footprint and road overlap crops. |
| C11 | Road/path hierarchy | Motorway through service/path classes lose ordering, widths or visibility; links/ramps appear too early or disappear. | Per-class inventory; width/rank measurements at several zooms, including major/minor junctions. |
| C12 | Stroke construction | Casing, centerline, dashes, caps, joins, miter spikes, dash phase, opacity, blur or pixel/mm conversions differ materially. | Straight and curved segments, junction/end crops, fractional zoom and output-DPI probes. |
| C13 | Network topology and vertical order | False at-grade intersections, bridges/tunnels drawn in the wrong order, broken ramps/links or casings; water crossings misleading. | Known crossing fixtures with structure/layer attributes; trace continuity and over/under relationships visually. |
| C14 | Rail, transit and specialized transport | Rail resembles roads, station/airport/ferry roles disappear, parallel infrastructure merges visually. | Source-present class/symbol fixtures, dense interchange and sparse-route crops. |
| C15 | Boundaries and geographic meaning | Admin ranks indistinguishable; coastline mistaken for boundary; solid/dashed, maritime/disputed/worldview semantics changed. | Inspect each source-present boundary class and filter, including lake/land intersections; never “fix” by dropping status filters. |
| C16 | Symbols and sprites | Wrong/missing icon, shape, color, aspect ratio, anchor, size or fallback; orphan shield backgrounds; ambiguous symbols. | Actual glyph/sprite render, icon+text collision fixtures, optional icon/text behavior and high-DPI sizes. |
| C17 | Font-role fidelity and availability | Regular/medium/bold/italic flattened, silent substitution, script fallback absent, licensed fonts assumed installed. | Inventory source stacks; actual converted `QFontInfo`, glyph shaping and font-distribution checks per runtime; follow font policy. |
| C18 | Typographic metrics and treatment | Wrong x-height, width, weight, tracking, line-height, wrapping, case, baseline or halo; unreadable labels at intended size. | Matched named-label crops with size/bounds/weight observations; compare at 100%, not only enlarged contact sheets. |
| C19 | Label content and language | `name_en`/local-name fallback ignored, wrong abbreviations/units, truncation, missing diacritics, broken RTL or missing-glyph boxes. | Compare exact source expression and resulting strings; null/empty fields, long names, mixed scripts and bidi fixtures. |
| C20 | Label placement and association | Name appears to label a neighboring feature, wrong anchor/offset/rotation, upside-down or overly curved line text. | Feature-label association crops, line orientation/angle and repeated pan/zoom checks; inspect baselines and collisions separately. |
| C21 | Collision and priority | Labels overlap, low-priority text displaces essential names, symbols survive hidden text, buffers collide unexpectedly. | Dense paired fixtures; record which labels survive and why, including text+icon/halo extents and data-driven ranks. |
| C22 | Density, repetition and clutter | Nearby duplicates, too many/few labels, isolated gaps, class-wide suppression, per-part and cross-feature repeats confused. | Named-label counts and inter-label distances by class/area, retained feature coverage and repeat controls; fewer labels is not automatically better. |
| C23 | Scale continuity | Pop-in/out, abrupt width/type jumps, overlapping or missing generated bands, unstable label hierarchy at fractional zooms. | Boundary triplets and short zoom sequences; verify QGIS inclusive bounds against source intervals and data-defined interpolation. |
| C24 | Tile edges, clipping and spatial consistency | Tile seams, duplicate edge features, truncated labels, cracks, antialias halos or world-wrap/CRS misalignment. | Pan across known seams, edge-centered geometry, adjacent-tile checks and large extents where applicable. |
| C25 | Activity semantic encoding | Run/Ride/Hike meanings, route direction, start/end/selected state or category distinctions change unexpectedly. | Same real activity data and UI/legend state; trace a route and identify each represented state without relying only on hue. |
| C26 | Activity/background interaction | Tracks disappear on roads/water/forest, overlap obscures routes, outline overwhelms map or labels, dense routes become unreadable. | Sparse/dense multi-activity views, crossings and shared segments across land/water/urban backgrounds; actual display and print sizes. |
| C27 | Accessibility and perceptual robustness | Color-vision or grayscale views lose necessary distinctions, low vision/high-DPI makes type illegible, transparency defeats contrast. | Color-vision simulations plus manual review, grayscale, target physical sizes and redundant encodings. WCAG text checks can inform UI text, not certify an entire map. |
| C28 | Runtime and output consistency | Qt 5/6, older QGIS, desktop vs Docker fonts, screen vs PNG/PDF or platform differences change meaning/legibility. | Separate exact-runtime/output cells; inspect packaged plugin installation and actual exports when claimed. Docker PNG success is not Windows/PDF proof. |
| C29 | Stability, completeness and performance | Map stays partially drawn, label flicker after settle, pan/zoom stalls, nondeterminism exceeds measured controls. | Cold/warm cache, settled repeated renders and timed interactions on representative datasets; separate network/provider failure from style behavior. |
| C30 | Map context and attribution | Legend encodings disagree, scale/north/context is missing where required, source attribution is omitted or misleading. | Check the complete user-facing canvas/export, not only the basemap crop; verify attribution and optional context requirements for that output. |

## 5. Verdicts and severity

Use these values consistently; **missing evidence is never a pass**:

| Verdict | Meaning |
| --- | --- |
| NOT ASSESSED | No adequate inspection or applicable fixture yet. |
| PARTIAL | Evidence covers only some stated scales, runtimes, features or sub-checks. List the missing cells. |
| OPEN | A repeatable defect/mismatch or failed acceptance criterion needs investigation; diagnosis may remain provisional. |
| PASS (scoped) | Declared criteria are satisfied in the explicitly named coverage cells, with linked evidence. Not a universal pass. |
| ACCEPTED LIMITATION | A remaining difference has evidence, rationale, affected scope and explicit reviewer/Emman acceptance. Not an automatic label for hard work. |
| N/A | Source preset/output genuinely excludes the feature or encoding. Cite inventory/product requirements; absence from a screenshot is insufficient. |

Track severity separately: **critical** = misleading geographic/activity meaning
or unusable output; **major** = common-task readability/hierarchy failure;
**minor** = local degradation without lost meaning; **cosmetic** = small rendering
variation. State uncertainty rather than guessing severity from pixel count.

Do not use aggregate scores to hide a critical/major defect. A local MAE/RMS
improvement cannot justify deleting features, changing language, or weakening
class distinctions. Compare affected and unaffected regions, label presence and
feature semantics. Useful auxiliary measures include class color/width ratios,
label counts/distances, glyph bounds, collision survivors, local contrast and
render latency. Choose tolerances **before** evaluating candidates, tied to
reader tasks, source intent and control variability; there is no universal MAE
threshold or fixed contrast ratio that certifies cartographic quality.

## 6. Validation record template

Copy this into an assessment/PR and fill one row **per checklist ID and coverage
cell** when results differ. A row can cover multiple cells only when all have
been inspected and share the same result. Keep immutable artifact links.

```markdown
## Assessment identity
- Preset/source fingerprint and data revision:
- Baseline/candidate commits and preprocessing fingerprints:
- Camera(s), zoom/boundary samples, dimensions, CRS, scale/DPI:
- QGIS/Qt/browser/platform, requested/resolved fonts, output path:
- Data/fixture IDs, source classes, activity states:
- Repeated-control variability and capture validity:

| ID | Scope/cells | Criterion and method | Observation | Severity | Verdict | Evidence | Next action/owner |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Cxx | camera + runtime + output | declared before probe | actual result | level | verdict | full map + crop/manifest | bounded follow-up |

## Candidate decision
- Source mechanism/hypothesis and affected checklist IDs:
- Intended improvement and measured result versus repeated control:
- Guardrails/regressions, including semantic and usability trade-offs:
- Retain/reject/defer, reason, reviewer decision and linked PR/follow-up:
- Remaining unvalidated cells (including deployment/output differences):
```

The capture harness supplies renders, snapshots, diffs and provenance; it does
**not** currently populate this whole scorecard or certify the semantic checks.
Record manual work honestly. If a needed fixture/tool is missing, create a
bounded follow-up rather than fabricating a completed check.

## 7. Review cadence and completion

1. **Baseline sweep:** classify all 30 IDs; map source-present classes to fixtures
   and mark gaps. Review full maps first, then hotspots and individual features.
2. **Prioritize:** investigate critical/major semantic and usability gaps first,
   particularly at z8–z14. Rank cosmetic fidelity work below meaningful omissions.
3. **One hypothesis:** attribute the mismatch to source/conversion/rendered owner,
   change one bounded mechanism and compare against repeated unchanged controls.
4. **Candidate sweep:** validate affected IDs plus their coupled guardrails
   (for example font width affects placement, collision, density and overlays).
   Run both Docker lanes; publish real before/after evidence for rendering PRs.
5. **Integrate:** complete tests, CI, SonarCloud and exact-head reviews; refresh
   final artifacts or prove they are unchanged. Update the issue ledger.
6. **Milestone sweep:** re-audit the complete matrix after interacting changes,
   before declaring a plateau or closing the investigation. Carry historical
   evidence as historical, not automatically current.

A narrow PR can merge with broader unrelated IDs still open when its scoped
criteria and guardrails pass. The **holistic investigation cannot close** with
unaccounted applicable IDs, pending critical/major defects, unvalidated required
coverage or unfinished PRs. Every applicable row must have scoped passing
evidence or an explicitly accepted limitation; each N/A needs a reason. If
scope is intentionally reduced, record that decision and follow-ups instead of
silently removing cells. “No more improvement found in these probes” is a local
result, not evidence of cartographic completeness.

This protocol supplements, not replaces, [testing policy](testing-policy.md),
[font policy](mapbox-font-policy.md), and the contributor rendering-proof gates.
