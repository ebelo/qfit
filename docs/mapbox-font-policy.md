# Mapbox typography: open-font substitution policy

This decision forms part of qfit's [architecture](architecture.md#81-basemap-typography-and-open-font-policy)
and [deterministic rendering principles](qgis-plugin-architecture-principles.md#8-deterministic-rendering-policy).
It follows the [Geneva font investigation in #1453](https://github.com/ebelo/qfit/issues/1453#issuecomment-5606888522).

## Decision

qfit will use **openly licensed alternatives as close as possible to each original
Mapbox font and style**, across all map labels. Do not require users to purchase
commercial fonts, and do not redistribute those fonts in the plugin, repository,
Docker images or validation assets without the appropriate rights.

This applies to every built-in basemap preset and label role, not only Geneva or
city names. Preserve regular/medium/bold/italic distinctions, numeral legibility,
diacritics and multilingual coverage. New presets, style revisions and custom
font stacks need their own inventory and licence-aware mapping; do not assume
every Mapbox style uses the Outdoors fonts listed below.

## Original Outdoors font inventory

The `mapbox/outdoors-v12` source style audited on **2026-09-09** contains these
explicit font stacks. Layer IDs are from the original source, before qfit splits
them into zoom/filter-specific QGIS styles. The second font is the source's
fallback, not an approved open alternative.

| Original primary font | Original fallback | Source label layers |
| --- | --- | --- |
| DIN Pro Medium | Arial Unicode MS Regular | `contour-label`, `golf-hole-label`, `natural-line-label`, `natural-point-label`, `poi-label`, `transit-label`, `airport-label`, `settlement-major-label`, `country-label`, `continent-label` |
| DIN Pro Regular | Arial Unicode MS Regular | `road-label`, `path-pedestrian-label`, `ferry-aerialway-label`, `settlement-subdivision-label`, `settlement-minor-label` |
| DIN Pro Italic | Arial Unicode MS Regular | `building-entrance`, `building-number-label`, `block-number-label`, `waterway-label`, `water-line-label`, `water-point-label` |
| DIN Pro Bold | Arial Unicode MS Bold | `road-intersection`, `road-number-shield`, `road-exit-shield`, `state-label` |

Geneva uses `settlement-major-label`, so its source face is **DIN Pro Medium**.
Audit fonts declared by expressions as well as literal stacks when a source
style changes; this snapshot is not a permanent upstream contract.

## Commercial and technical boundary

- **DIN Pro / FF DIN is commercially licensed.** Arial Unicode MS is also a
  licensed font, not an open replacement. Local installation rights are
  different from embedding or redistributing a font with a plugin.
- A desktop licence may allow local QGIS use and static designs under its terms;
  it does not automatically cover bundling the font for every qfit user. Review
  the applicable licence separately for redistribution, embedding and server use.
  Current options are published by [FontFont/MyFonts](https://www.myfonts.com/products/medium-ff-din-364315/licenses);
  pricing and terms are not fixed architecture assumptions.
- Mapbox's [Fonts API](https://docs.mapbox.com/api/maps/fonts/) serves encoded
  glyph ranges for map renderers. Token access is not a licence to install or
  redistribute the underlying desktop font. qfit's native QGIS text path uses
  locally resolved fonts, not those Mapbox GL glyph ranges.
- QGIS is technically capable of using a suitably licensed installed font. The
  limitation is availability, licensing and explicit mapping, not a QGIS ban on
  commercial typefaces. qfit's default distribution will follow the open-font
  decision rather than depend on such an installation.

## Current implementation and Docker fonts

The QGIS-safe JSON transformation still uses `Noto Sans` for literal stacks.
At the QGIS adapter boundary, qfit also retains the **original source style**
and restores the following distinctions for the exact `mapbox/outdoors-v12`
preset when the selected faces resolve correctly:

| Original primary face | Open face | Fallback |
|---|---|---|
| DIN Pro Regular | Barlow Regular | Noto Sans, then installed script fallbacks |
| DIN Pro Medium | Barlow Medium | Noto Sans, then installed script fallbacks |
| DIN Pro Italic | Barlow Italic | Noto Sans, then installed script fallbacks |
| DIN Pro Bold | Barlow Bold | Noto Sans, then installed script fallbacks |

This covers all 25 literal Outdoors stacks inventoried above, including source
owners whose rules are split by zoom or filter during conversion. Unknown or
expression-based stacks keep the existing conversion path. Light uses the narrower mapping documented below; custom
styles do not receive the built-in preset mappings. Missing Barlow faces retain the
existing Noto fallback; qfit never assumes the requested face was selected.
Validation label audits now include both requested and resolved family/style.

`scripts/docker/Dockerfile` builds the QGIS 3/4 test environments with four
unmodified Barlow faces, `fonts-noto-core=20201225-2` and
`fontconfig=2.15.0-2.3ubuntu1` (verified in both base images). Missing pinned
package versions fail the build rather than silently changing rendering.
Font files are
pinned by upstream commit and SHA-256 in
[`scripts/docker/fonts/barlow/provenance.json`](../scripts/docker/fonts/barlow/provenance.json),
with the complete SIL OFL 1.1 notice alongside them. Qt 5's retained family list
is explicitly replaced as well as its primary family, preventing an apparently
successful switch which actually still renders Noto Sans.

Run `bash scripts/docker_test.sh 3` and `bash scripts/docker_test.sh 4` to build
and retain `qfit/qgis:3.44.11-fonts` and `qfit/qgis:4.2.0-fonts` locally. CI builds
the identical Dockerfile. `QFIT_REQUIRE_OPEN_FONTS=1` makes missing/substituted
faces a test failure. Real Qt glyph shaping also checks accented Latin, Greek,
Cyrillic and Arabic samples. This is not a claim of universal Unicode or CJK
coverage; additional script packages require explicit validation.

This installation is **Docker-scoped**. The plugin ZIP does not install fonts
on a user's Windows/Linux desktop. A desktop needs the same licensed open faces
installed separately to activate this mapping; automatic cross-platform font
provisioning remains a separate distribution decision. No commercial font is
included or required.

### Why Barlow rather than D-DIN or DINish?

The earlier Geneva capture requested Noto Sans but resolved **DejaVu Sans Book**
because Noto was absent. Installing Noto alone did not fix the mismatch.
D-DIN and DINish were subsequently compared using actual QGIS renders with
`QFontInfo` verification, unchanged label sizes and the same Mapbox reference.

- **D-DIN**: a valid OFL alternative with DIN proportions, but the original
  Datto v1.0 distribution has Regular, Bold and Italic, **not Medium**. Regular
  was lighter and Bold heavier than the Mapbox city labels.
- **[DINish](https://github.com/playbeing/dinish)**: an OFL derivative of
  Altinn-DIN/D-DIN with real Medium, multiple widths, and expanded language
  support. Static Medium at upstream commit
  `a5f3b2a3b932336225815bf9005e3b72cc3de71c` was tested, not a synthesized weight
  or an unverified variable-font instance. It remained lighter than the
  reference in the Geneva and Lausanne captures.
- **Barlow Medium**: the strongest of these candidates on both city crops for
  combined width and weight, with real Regular/Italic/Bold companion faces.

| QGIS candidate | Geneva crop MAE | Lausanne crop MAE |
|---|---:|---:|
| Previous DejaVu Sans Book fallback | 0.09626 | 0.07902 |
| D-DIN Regular | 0.08084 | 0.05907 |
| DINish Medium | 0.09029 | 0.07118 |
| Barlow Medium | **0.06684** | **0.03689** |

These are normalized RGB errors for fixed crops, not a universal typeface
ranking. Host candidate probes changed only the settlement label face; Docker
before/after evidence separately validates the production mapping across all
seven cameras, source weights, and QGIS generations. No city-specific stretch
or letter-spacing correction is introduced.

## Selection and implementation requirements

1. Maintain a mapping from source family/style and label role to the chosen open
   family/style and ordered script fallbacks. Explicitly cover every audited
   stack, including italic water labels and bold shield numerals. Record unknown
   or unsupported stacks rather than silently treating them as regular text.
2. Compare glyph shapes, width/advance, x-height, weight, italic angle, spacing,
   numerals and language coverage. Prefer real font styles over a city-specific
   horizontal squeeze. Exact pixel parity between rendering engines is not the
   acceptance criterion; visual similarity, legibility and stable placement are.
3. Verify that each selected font's licence permits the intended distribution
   and export uses. For bundled open fonts, retain upstream attribution/licence
   notices, version/provenance and any applicable font-name restrictions. Do not
   treat a free download as evidence of an open redistribution licence.
4. Make fonts reproducibly available in the supported QGIS 3/4 and Windows/Linux
   environments. If bundling or controlled installation is needed, implement it
   explicitly with packaging checks; do not rely on one developer's font cache.
   Record requested and actually resolved family/style in validation evidence,
   and exercise the missing-font fallback path.
5. Keep mapping decisions in the basemap style-conversion boundary; keep font
   availability/resolution in the QGIS infrastructure adapter. Do not introduce
   typography decisions in UI handlers or change custom-style choices globally
   as an incidental effect of tuning a built-in preset.

## Acceptance and visual evidence

For each promoted mapping, record the original stack, chosen open face/style,
licence/provenance, resolved runtime face and representative label examples.
Include matched **Mapbox reference / QGIS before / QGIS after** screenshots in the
PR, with readable detail crops and full-map context.

Validate multiple cameras/zoom levels and the affected label roles: settlements,
roads/paths, shields, water, terrain/POIs and administrative names. Check accents,
non-Latin fallback where supported, label density, collisions, wrapping, halos
and interactive/export results. Preserve the shield collision fix and use the
other built-in presets as regression guards.

Runtime changes require relevant unit tests, both real-QGIS Docker lanes and
the normal CI/SonarCloud/review gates. A successful screenshot on a machine with
privately installed fonts is not sufficient evidence of a portable qfit fix.

## Light v11 typography follow-up

The **2026-09-11** live `mapbox/light-v11` audit contains 14 literal stacks:

| Primary face | Fallback | Source label layers |
|---|---|---|
| DIN Pro Regular | Arial Unicode MS Regular | `road-label-simple`, `settlement-subdivision-label`, `settlement-minor-label` |
| DIN Pro Medium | Arial Unicode MS Regular | `natural-line-label`, `natural-point-label`, `airport-label`, `settlement-major-label`, `country-label`, `continent-label` |
| DIN Pro Italic | Arial Unicode MS Regular | `waterway-label`, `water-line-label`, `water-point-label`, `poi-label` |
| DIN Pro Bold | Arial Unicode MS Bold | `state-label` |

The existing open-font Docker installation is reused, but **Light does not use
an unconditional copy of the Outdoors mapping**. A full Barlow substitution
increased road-label density at Bern z12 and worsened the z5 overview. Paired
controls and role-isolation probes in both QGIS generations instead support:

| Light label role | Selected open face | Validated range |
|---|---|---|
| Water lines/points and waterways | Barlow Italic | Existing visible ranges |
| Major settlements, natural features, airports | Barlow Medium | z8 and above, within each original rule's range |
| Minor settlements and subdivisions | Barlow Regular | z8 and above, within each original rule's range |
| Roads | Barlow Regular | z15 and above |
| POIs | Barlow Italic | z16 and above |
| State, country, continent; other bands | Existing Noto conversion | No new substitution retained |

These bounds reuse the regional and high-detail bands exercised by the Light
matrix and the existing road/POI conversion boundaries. The adapter splits a
label rule only when needed, preserving its original filter, inclusive zoom
limits, priority, size, color and collision settings. Lower bands keep their
original font and cannot overlap the new band. Unknown font stacks and missing
Barlow faces are left untouched. The Outdoors mapping and custom styles are
unchanged. The source font inventory is not a claim that every role has a
promotable replacement.

The seven-camera before/after matrix runs on both QGIS 3 and 4 with verified
resolved faces. It includes a small QGIS 4 Lausanne trade-off (approximately
+0.0000048 normalized whole-image MAE, +0.056% relative); the corresponding
QGIS 3 view improves. Do not describe this as pixel-perfect or a uniform
metric improvement. The chosen mapping improves regional/high-detail views
without introducing the blanket candidate's excess mid-zoom road labels.
Font-family work does not resolve existing label-language, size, color,
placement or terrain-renderer differences. Those need their own evidence and
must not be hidden by font-specific stretch or per-city compensation.
