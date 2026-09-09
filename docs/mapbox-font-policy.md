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

## Current implementation versus target

`mapbox_config.py` currently substitutes literal source font stacks with the
single `QGIS_TEXT_FONT_FALLBACK` value, **Noto Sans**. That discards the source
style distinctions and does not guarantee the requested font is installed.

The Geneva capture resolved `Noto Sans` to **DejaVu Sans Book**, confirmed with
`QFontInfo`, because Noto Sans was missing on that machine. The observed mismatch
was therefore between different font families, not merely two styles of DIN.

Liberation Sans and narrower DejaVu variants improved diagnostic Geneva and
Lausanne crops. They are **candidates, not approved final mappings**. Installing
Noto Sans alone did not resolve the Geneva mismatch. No font bundle, new runtime
font mapping or font-specific width correction is introduced by this document.

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
