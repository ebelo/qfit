# Light C15: source status and geographic fixtures

Captured 2026-09-14 on baseline `be2d187939b01f81274e2847f011ac134c2f50e7`. **Validation/test only; no rendering fix.**
Map data © OpenStreetMap contributors; reference cartography © Mapbox.
The source's worldview/status values are reported, not independently assigned.

## Evidence and result

Six 1280×900 cameras: Kashmir requested z6.9/7/7.1, Cyprus z7, Swiss cantonal
borders z8 and US state borders z7. Both QGIS 3.44.11/Qt5 and 4.2.0/Qt6 Docker
runtimes, actual DPI100/96. Twelve browser PNGs and 24 native unchanged/repeat
PNGs; every within-cell pair is byte-identical. Sixteen further native owner-removal
PNGs identify visible disputed/background and admin-1/background paint in two
geographic extents apiece. All labels, native context and nonremoved boundary
settings are unchanged in those probes; label placements are not claimed invariant.

**PASS (scoped source eligibility):** all five source owner contracts exactly
match fresh Light source SHA256
`87413e46c074e13aef420958a3ad101961766e6645336608e399ceccaffc6d32`.
The committed native test checks 2240 owner/property combinations per runtime,
including empty/NULL fields and nonmatching/multiple-token worldview strings.
Offline replay independently checks 365 distinct observed property/owner
combinations per runtime from the browser's loaded source-tile queries. Native
filters correctly separate admin0 ordinary/disputed cores, include disputes in
the admin0 background, allow only exact all/US worldview values, exclude maritime
features, and retain both admin1 owners. Missing disputed values do not suppress
background/admin1 rules, which have no disputed predicate in this source.

Kashmir and Cyprus expose real disputed features; Swiss and US extents expose
admin1 lines. The Cyprus loaded source query also includes maritime=true/CN
fragments. Those fragments are excluded in predicate replay and absent from
rendered-feature queries. Source queries include offscreen/buffered/duplicate
fragments: **not** a second maritime geographic fixture, precise unique-feature
counts, a native decoded-feature trace or proof of all-worldview cartography.

**OPEN C12/C15/C23 paint:** the four untouched owners still have constant native
widths. Both native cores use the source's post-z7 dash pattern even at native
z6.9, rather than the source's continuous admin1 / alternate disputed texture
below7. Background opacity is fixed0.35 (source ramps to0.5); blur remains
unvalidated. The audit records actual widths, opacity, dash properties and
preprocessing. The source-native camera-zoom mismatch remains separately open.
Do not fix these paint defects by changing status/worldview filters.

Full maps show very faint disputed and subdivision lines relative to source;
owner removals confirm those classes are present, not missing by filter. This
is a bounded hierarchy/fidelity finding, not a measured universal readability
threshold. C15 overall remains OPEN; no limitation accepted.

## View maps

Panels are **Mapbox source reference | QGIS3 baseline | QGIS4 baseline**, never
Before/After proof of an improvement. Native-size 420×300 crops are selected by
maximum owner-removal pixel movement on a fixed50px grid (coordinates in audit).
Full maps preserve all surrounding context. The original source globe reference
is preserved; this run does not establish new anchor registration or resolve
C01 native CRS/zoom/DPI comparability. Do not treat MAE as an acceptance score.

- [kashmir-z6.9 full map](kashmir-z6.9-full.png)
- [kashmir-z7 full map](kashmir-z7-full.png) · [native-size detail](kashmir-z7-crop.png)
- [kashmir-z7.1 full map](kashmir-z7.1-full.png)
- [cyprus-z7 full map](cyprus-z7-full.png) · [native-size detail](cyprus-z7-crop.png)
- [swiss-admin1-z8 full map](swiss-admin1-z8-full.png) · [native-size detail](swiss-admin1-z8-crop.png)
- [us-admin1-z7 full map](us-admin1-z7-full.png) · [native-size detail](us-admin1-z7-crop.png)

`qgis3-kashmir-transition.png` and `qgis4-kashmir-transition.png` show requested
triplets; actual native zoom/rounded activation is in each runtime JSON.
`qgis*-*-owner-removal.png` is **diagnostic removal**, not a retained candidate.

## Reproduction

Run from a checkout whose package directory is named `qfit`. Extract this entire
artifact directory as `/evidence`; use explicit paths to your checkout. Install
the documented open-font Docker images and browser dependencies as needed.
Credentials follow your normal authorized harness setup; none are stored here.
OpenClaw-managed runs additionally require their protected same-run host/container
preflight. Do not use a real-token file as a substitute for that protected route.

```bash
python3 /evidence/boundary_capture.py --repo /work/qfit --evidence /evidence --mode native --qgis-major 3 --camera kashmir-z7 --variant control
python3 /evidence/boundary_capture.py --repo /work/qfit --evidence /evidence --mode browser --camera kashmir-z7
python3 /evidence/native_contract_audit.py --repo /work/qfit --evidence /evidence --output /evidence/replay.json
```

The native worker body is preserved exactly from this run. Public wrapper uses
explicit path/mode arguments; Chromium override is optional `--chromium`.
Browser mode refuses a changed live source. Native image replay requires live
provider access: source properties/hashes **do not archive tile payloads**.
Use a copy of the directory for replay so original evidence remains immutable.
Offline native-contract replay needs no credentials/network; it evaluates saved
properties, not images. Both exact native builds replayed365 combinations.

## Limits and provenance

`audit.json` records code/source hashes, cameras, actual per-cell runtime, all
repeat identities, owner-removal changed pixels and crop coordinates. Complete
label snapshots include requested/resolved fonts. `image-rootfs.json` records
runtime filesystem layer hashes. The initial QGIS3 image identifier was removed
by a cached test rebuild; dedicated retained image tags repaired the launcher.
The first valid frame remains identical to its subsequent repeat. Failed
preflight emitted no valid map and is excluded. No credential routing change. An inherited stddev>5 blank-image heuristic rejected the valid sparse US QGIS4 map (stddev4.927). Full-map inspection confirms named towns, roads, terrain/landcover and the state line; extrema123–255 and visible owner-removal movement corroborate content. The heuristic is not a cartographic acceptance threshold; no blank frame was promoted.

No production files changed; other styles/raster/activities/package payloads are
unchanged by source identity, not fresh output certification. This is not the
seven-preset final sweep, actual desktop/PDF/full atlas, real activities/UI,
accessibility, full seam/pan/temporal, worldwide boundary or C01–C30 completion.
