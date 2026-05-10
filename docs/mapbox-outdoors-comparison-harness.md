# Mapbox Outdoors visual comparison harness

qfit includes a dev-only harness for comparing Mapbox Outdoors rendered by Mapbox GL JS in a browser with qfit's native QGIS vector-tile rendering.

The harness is a **manual visual QA aid**, not a CI gate. Pixel-perfect parity is not expected because Mapbox GL JS and QGIS differ in expression support, label placement, sprites, fonts, antialiasing, and zoom interpolation.

## What it captures

Run outputs are written under the ignored debug tree:

```text
debug/mapbox-outdoors-comparison/<camera>/<UTC timestamp>/
```

A complete run writes:

- `mapbox-gl-reference.png` — browser/Mapbox GL JS reference image
- `qgis-vector-render.png` — qfit/QGIS native vector-tile render for the same camera
- `mapbox-gl-vs-qgis-diff.png` — pixel diff for quick drift inspection
- `manifest.json` — camera, output paths, and capture status without any token values

## Cameras

List supported cameras:

```bash
python3 validation/mapbox_outdoors_comparison.py --list-cameras
```

Current camera:

- `valais-geneva-outdoors` — representative Geneva/Valais corridor view using `mapbox/outdoors-v12`

## Required local tools

For a complete browser + QGIS + diff run, install or run from an environment with:

- a Mapbox access token in `MAPBOX_ACCESS_TOKEN` or `QFIT_MAPBOX_ACCESS_TOKEN`
- Playwright and Chromium for the Mapbox GL JS screenshot
  - `python3 -m pip install playwright`
  - `python3 -m playwright install chromium`
- PyQGIS available to the Python runtime for the QGIS vector render
  - for example, run from a QGIS Python shell, OSGeo/QGIS environment, or another shell where `import qgis` works
- Pillow for the diff image
  - `python3 -m pip install pillow`
- `QT_QPA_PLATFORM=offscreen` when running headlessly, if your QGIS environment requires it
- `xvfb-run` or another virtual display when your local Chromium/QGIS build cannot render headlessly without an X server

Keep tokens out of shell history where practical by exporting an environment variable instead of passing `--mapbox-token` directly.

## Run a complete comparison

```bash
export MAPBOX_ACCESS_TOKEN="pk..."
python3 validation/mapbox_outdoors_comparison.py valais-geneva-outdoors
```

The command prints only artifact paths. It does not print the token, and `manifest.json` intentionally excludes token values.

## Partial captures

When developing on a machine that only has one rendering stack available, run a partial capture:

```bash
# Browser reference only
python3 validation/mapbox_outdoors_comparison.py valais-geneva-outdoors --skip-qgis --skip-diff

# QGIS vector render only
python3 validation/mapbox_outdoors_comparison.py valais-geneva-outdoors --skip-browser --skip-diff
```

Diff generation requires both the browser and QGIS images in the same run.

## Interpreting output

Use the browser image as the Mapbox GL reference. Inspect the QGIS image for high-signal gaps such as:

- missing terrain/outdoor features
- over- or under-emphasized roads/trails
- noisy settlement or POI labels
- label size/priority mismatches
- broad color/width drift caused by expression simplification

Use the diff image as a navigation aid, not as a pass/fail metric. Label placement and antialiasing differences will create expected diff noise.

## PR notes

For rendering-sensitive Mapbox vector-style changes, include a concise validation note such as:

```markdown
## Visual comparison
- Harness: `python3 validation/mapbox_outdoors_comparison.py valais-geneva-outdoors`
- Artifacts: `debug/mapbox-outdoors-comparison/valais-geneva-outdoors/<timestamp>/`
- Checked: browser reference, QGIS vector render, and diff image
- Result: summarize visible improvements and any accepted QGIS/Mapbox GL limitations
```
