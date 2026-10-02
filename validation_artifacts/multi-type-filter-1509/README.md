# Multi-choice activity types: isolated widget evidence

QGIS 3.44.11/Qt5.15.17 and QGIS4.2.0/Qt6.9.2 offscreen Docker captures,
Fusion, 420x120 control fixture, identical options. DPI100/96respectively.
Baseline source2d73f5584c4ad90b2ffc108e9af6408bf45e805b declares stockQComboBox;
its isolated control is reconstructed here, not a full old plugin screenshot.
Candidatecb4b6ef5487f673022a88c9a546f8923773dde5d uses actualActivityTypeSelector.
Before selects Hike only; after checks Hike and Walk (not possible before).
Repeated unchanged controls match byte-for-byte within eachruntime/role.
Popup capture shows realQGIS checkbox states. No basemap/private data/credentials.

Functional proof is the real dock test in tests/test_qgis_smoke.py: actual mouse
clicks; Walk/Hike OR map subset excludesRun; query/subset agreement; catalog
refresh preserves visible layer filter and keepsRun available; settingsrestore;
All reset and last-unchecked unrestricted. Full native suites cover both versions.
These are UI/state proofs, not full map-style parity, Windows deployment or PDF
verification. Density resolution and renderer have not changed.
