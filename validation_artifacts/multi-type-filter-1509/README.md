# Multi-choice activity types: isolated widget evidence

QGIS 3.44.11 / Qt 5.15.17 and QGIS 4.2.0 / Qt 6.9.2 offscreen Docker
captures, Fusion, 420×120 control fixture, identical options. Measured logical
DPI: 100 / 96 respectively. Exact Qt/PyQt versions are in the manifests.

Baseline source `2d73f5584c4ad90b2ffc108e9af6408bf45e805b` declares a stock
QComboBox; its isolated control is reconstructed here, not a full old-plugin
screenshot. Initial candidate `cb4b6ef5487f673022a88c9a546f8923773dde5d` uses
the actual ActivityTypeSelector. Before selects Hike only; after checks Hike
and Walk (not possible before). Repeated unchanged controls match byte-for-byte
within each runtime/role. Popup capture shows real QGIS checkbox states.

Final-head `387afefc27c4297ce0e09efccae08cdebddb17c5` recaptures are byte-identical
to all published PNGs. The follow-up normalizes equivalent saved/catalog labels,
preserves legacy query objects and simplifies the filter conditional. Actual
QGIS 3/4 clicks also verify that saved `trail-run` and catalog `Trail Run` yield
one checked option, and unchecking it clears the restriction.

Functional proof is the real dock test in `tests/test_qgis_smoke.py`: actual
mouse clicks, Walk/Hike OR subset excluding Run, query/subset agreement, catalog
refresh preserving the visible filter while keeping Run available, settings
restore, All reset and last-item uncheck. A real GeoPackage/VRT heatmap test
selects two stored types and verifies order-independent cache reuse.

No basemap, private routes or credentials. These are UI/state proofs, not full
map-style parity, Windows deployment or PDF verification. Density resolution
and renderer have not changed. Only intended evidence is published separately
from production main.
