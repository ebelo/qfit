# Light duplicate road-label evidence (#1462)

Baseline `ce5e5fc8669106d1f4ecaca3084e1e554ff72bfa`; candidate `73aafa6a697e4d41b015c0994fb239df9c557991`.

Matched 1280×900 Light cameras at z5, z8, z10, z12, z14, z17 and z18. QGIS 3.44.11/Qt5 and QGIS 4.2.0/Qt6, Barlow/Noto-enabled images, verified TLS, unchanged source definition, fixed Python hash seed 0. Headless PNG exports; interactive Windows and PDF export are not separately validated.

Each panel: **Mapbox reference | QGIS before | QGIS after**. Crops are unscaled, matched coordinates; full images retain context. Unchanged repeat controls are pixel-identical in all 14 cases. Production images are byte-identical to the 250px duplicate-suppression probe in all 14 cases.

The retained change applies source symbol spacing to cross-feature duplicate names. It does not change text size, fonts, colors or road geometry. Per-line repeat distance alone or combined with line merging worsened street-level comparisons. Merging alone reduced but did not eliminate repetition. 150/250/400px duplicate thresholds were compared: 250px follows the source default; 400px has lower whole-image error at the two street cameras but suppresses more labels than source spacing warrants and was not promoted.

The source and preprocessed fingerprints and runtime metadata are supplied with the summary; the PNG panels retain exact crops and full-map context. Larger 12px/14px street-label sizes were subsequently rejected in both street cameras and both Docker versions; see street-size-rejections.json. Remaining font-size, geometry and placement differences are outside this slice.
