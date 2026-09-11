# Light place-name fallback evidence — C19 (#1462)

Baseline `75131a5a1ebb9dcfa42f5fcf8fd7ac9345d3b917`; runtime implementation `ef136b9956e4ad4d241f707f8fa0e2d3b90659b7`.

Fresh 2026-09-11 matched source, seven preset cameras, 1280×900, EPSG:3857,
96 DPI, QGIS 3.44.11/Qt5 and 4.2.0/Qt6, pinned Barlow/Noto fonts. The original
source and preprocessed hashes, camera geometry, runtime metadata and actual
requested/resolved fonts are recorded in the JSON artifacts. Tile payloads were
not archived. This is headless PNG evidence, not desktop/PDF/accessibility certification.

All 14 unchanged controls are byte-identical; all 14 unpatched production renders
are byte-identical to the field-aware probe. Full rule inventories differ only in
three `field_name` settings (country plus two settlement font bands); all filters,
fonts, sizes, priorities, spacing and zoom ranges are preserved. Complete matching
label inventories are published; full-inventory hashes are retained in metrics.

## Result and trade-offs

Source-requested English names are restored: Zürich → Zurich, Luzern → Lucerne,
München → Munich, Milano → Milan and Genève → Geneva. z5/z8 MAE improves in
both runtimes. Lausanne z10, Bern z12 and both street cameras are byte-identical
to the baseline. Geneva z14 MAE increases by 0.0000003472 (QGIS3) and
0.0000000318 (QGIS4): the QGIS-only city label remains absent from the reference,
but now uses the correct source name. The placement discrepancy is still open;
keeping an incorrect language to reduce pixel error is not a semantic fix.

## Rejected probe and native semantics

An `attribute(@feature, 'name_en')` coalesce probe failed to request that field
from the vector-tile decoder; it was neutral in 12/14 images and changed only
Geneva z14. It is not the retained implementation. QGIS's `referencedFields`
request list must explicitly include `name_en` and `name`. The decoder constructs
that schema before assigning MVT properties, leaving absent values NULL. Native
regressions cover English, missing/NULL English, intentional empty English,
missing local values, both absent, accents, Cyrillic and Arabic **strings**.
Those string assertions do not certify glyph shaping, bidi placement or all locales.

Upstream mechanism: [QGIS 3 labeling](https://github.com/qgis/QGIS/blob/final-3_44_11/src/core/vectortile/qgsvectortilebasiclabeling.cpp),
[requested field schema](https://github.com/qgis/QGIS/blob/final-3_44_11/src/core/vectortile/qgsvectortileutils.cpp),
[MVT decoder](https://github.com/qgis/QGIS/blob/final-3_44_11/src/core/vectortile/qgsvectortilemvtdecoder.cpp).
QGIS 4 uses the same explicit-field request mechanism.

## Scope

Only the original unsplit `country-label` / `settlement-major-label` rules from
exact `mapbox/light-v11`, source-layer `place_label`, with the audited coalesce
expression are adapted, before existing font bands. Other roles, modified source
contracts, Outdoors and custom styles remain untouched. C19 as a whole remains
open; no limitation has been accepted on Emman's behalf.

Map data © OpenStreetMap contributors; cartography/reference © Mapbox.

## Matched full maps

| Camera | Reference | QGIS3 before / after | QGIS4 before / after |
| --- | --- | --- | --- |
| switzerland-alps-z5-light | [reference](switzerland-alps-z5-light-reference.png) | [before](qgis3-switzerland-alps-z5-light-before.png) / [after](qgis3-switzerland-alps-z5-light-after.png) | [before](qgis4-switzerland-alps-z5-light-before.png) / [after](qgis4-switzerland-alps-z5-light-after.png) |
| zurich-region-z8-light | [reference](zurich-region-z8-light-reference.png) | [before](qgis3-zurich-region-z8-light-before.png) / [after](qgis3-zurich-region-z8-light-after.png) | [before](qgis4-zurich-region-z8-light-before.png) / [after](qgis4-zurich-region-z8-light-after.png) |
| lausanne-lavaux-z10-light | [reference](lausanne-lavaux-z10-light-reference.png) | [before](qgis3-lausanne-lavaux-z10-light-before.png) / [after](qgis3-lausanne-lavaux-z10-light-after.png) | [before](qgis4-lausanne-lavaux-z10-light-before.png) / [after](qgis4-lausanne-lavaux-z10-light-after.png) |
| bern-urban-z12-light | [reference](bern-urban-z12-light-reference.png) | [before](qgis3-bern-urban-z12-light-before.png) / [after](qgis3-bern-urban-z12-light-after.png) | [before](qgis4-bern-urban-z12-light-before.png) / [after](qgis4-bern-urban-z12-light-after.png) |
| geneva-urban-z14-light | [reference](geneva-urban-z14-light-reference.png) | [before](qgis3-geneva-urban-z14-light-before.png) / [after](qgis3-geneva-urban-z14-light-after.png) | [before](qgis4-geneva-urban-z14-light-before.png) / [after](qgis4-geneva-urban-z14-light-after.png) |
| zurich-streets-z17-light | [reference](zurich-streets-z17-light-reference.png) | [before](qgis3-zurich-streets-z17-light-before.png) / [after](qgis3-zurich-streets-z17-light-after.png) | [before](qgis4-zurich-streets-z17-light-before.png) / [after](qgis4-zurich-streets-z17-light-after.png) |
| geneva-streets-z18-light | [reference](geneva-streets-z18-light-reference.png) | [before](qgis3-geneva-streets-z18-light-before.png) / [after](qgis3-geneva-streets-z18-light-after.png) | [before](qgis4-geneva-streets-z18-light-before.png) / [after](qgis4-geneva-streets-z18-light-after.png) |
