# Atlas export validation harness

This document describes the supported validation harness for atlas export and rendering experiments.

## Why this exists

Recent atlas/profile debugging produced useful artifacts in `validation_artifacts/`, but many of those scripts were one-off experiments with versioned names (`v4`, `v7`, `final`, etc.).

The harness in `validation/atlas_export_harness.py` provides a small maintained entrypoint for curated, repeatable validation scenarios.

It is **validation tooling**, not production runtime code.

## Goals

The harness should make it easy to:

- run targeted real-data atlas checks
- generate artifacts in a predictable location
- compare rendering approaches when atlas/profile behavior is export-sensitive
- keep the supported scenarios discoverable instead of relying on whichever ad-hoc script was used last

## Supported scenarios

List supported scenarios with:

```bash
python3 validation/atlas_export_harness.py --list
```

Current curated scenarios:

- `native-profile-final`
  - compares atlas-driven native profile rendering with the renderer-image workaround
  - intended as the durable proof scenario for the headless native-profile/export behavior
- `native-profile-renderer`
  - validates the standalone `QgsProfilePlotRenderer.renderToImage()` workaround path

Older scripts in `validation_artifacts/` remain historical references, but only scenarios registered in the harness are considered supported validation entrypoints.

## Running a scenario

Curated real-data scenarios require explicit input paths. That is intentional: the harness should not pretend machine-local datasets are portable defaults.

Example:

```bash
python3 validation/atlas_export_harness.py native-profile-final \
  --source-gpkg /path/to/qfit_activities.gpkg \
  --reference-artifacts-dir /path/to/qfit/validation_artifacts
```

You can override the artifacts root for generated outputs if needed:

```bash
python3 validation/atlas_export_harness.py native-profile-final \
  --source-gpkg /path/to/qfit_activities.gpkg \
  --reference-artifacts-dir /path/to/qfit/validation_artifacts \
  --artifacts-root /tmp/qfit-validation
```

## Output layout

Harness runs are written under a predictable timestamped directory:

```text
validation_artifacts/atlas-harness/<scenario>/<UTC timestamp>/
```

Example:

```text
validation_artifacts/atlas-harness/native-profile-final/20260404T031500Z/
```

The harness exports this directory through `QFIT_VALIDATION_OUTPUT_DIR` so the underlying scenario script writes all generated artifacts into the run-specific folder.

## Environment expectations

The curated scenarios are designed for headless/local validation and may depend on:

- a machine with PyQGIS available
- an explicit real-data source GeoPackage passed with `--source-gpkg` (or `QFIT_VALIDATION_SOURCE_GPKG`)
- an explicit reference-artifacts directory passed with `--reference-artifacts-dir` (or `QFIT_VALIDATION_REFERENCE_ARTIFACTS_DIR`) when the scenario depends on prebuilt reference inputs such as coverage GeoPackages
- `QT_QPA_PLATFORM=offscreen` for headless export runs

The harness sets `QT_QPA_PLATFORM=offscreen` automatically if it is not already defined.

## Contributor guidance

When a PR changes atlas/profile/export-sensitive behavior, prefer referencing a harness run instead of a one-off ad-hoc script.

A good PR note should mention:

- which harness scenario was used
- where artifacts were written
- what final output was inspected (PDF/PNG)
- what was visually/functionally confirmed

## Adding a new supported scenario

When promoting an experiment into the maintained harness:

1. keep the scenario clearly validation-only
2. register it in `validation/atlas_export_harness.py`
3. make artifact paths respect `QFIT_VALIDATION_OUTPUT_DIR`
4. document the scenario purpose and expected artifacts
5. avoid adding throwaway `vN` script names for supported paths
