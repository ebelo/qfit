# Light typography evidence (#1453)

Baseline `0e79b0e8b034a29edf3cb53f08998cdb213b04d9`; candidate `a60b7466f75d2b41a26fbea746d9d02923488b24`.

Matched 1280×900 Light cameras at z5, z8, z10, z12, z14, z17 and z18. QGIS 3.44.11/Qt5 and QGIS 4.2.0/Qt6, Barlow/Noto-enabled images, verified TLS and resolved font faces, fixed Python hash seed 0. Headless PNG export only; interactive Windows and PDF export are not separately validated.

Each panel: **Mapbox reference | QGIS before | QGIS after**. Crops are unscaled, matched coordinates; full images retain context. Metrics include all retained and rejected candidates. Camera/source content is identical within each pair. No production claim of pixel parity: QGIS 4 Lausanne increases slightly in whole-image MAE; density regressions from the blanket mapping were rejected.

The Liberation Sans alternative was verified through temporary application-font registration, not added to the Docker images or plugin. The production images are byte-identical to the corresponding diagnostic candidate in all 14 cases.
