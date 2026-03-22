# qfit local QGIS testing

This document describes a practical local testing flow for qfit inside a desktop QGIS installation.

## 0. Run the scripted headless smoke test first

Before opening desktop QGIS, you can now run a small headless PyQGIS smoke test that exercises the real qfit write/load path.

```bash
python3 -m unittest tests.test_qgis_smoke -v
```

What it checks:
- writing a sample qfit GeoPackage with tracks, starts, points, atlas pages, and the atlas document-summary table
- loading those layers back into a live `QgsProject`
- enforcing qfit's working CRS (`EPSG:3857`) on the project/canvas
- wiring temporal playback expressions onto loaded layers
- keeping the background basemap below qfit activity layers in the layer tree

If PyQGIS is not available in the current Python environment, the smoke test skips itself instead of failing the whole suite.

## 1. Install the plugin into your QGIS profile

For development, the easiest option is a symlinked install:

```bash
python3 scripts/install_plugin.py --profile default --mode symlink
```

If you prefer a copied install instead of a symlink:

```bash
python3 scripts/install_plugin.py --profile default --mode copy
```

Default Linux plugin target:
- `~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/qfit`

You can also override the plugins directory explicitly:

```bash
python3 scripts/install_plugin.py --plugins-dir /path/to/plugins --mode copy
```

To remove the installed plugin:

```bash
python3 scripts/install_plugin.py --profile default --remove
```

## 2. Start QGIS

Open QGIS normally.

Then:
1. open **Plugins → Manage and Install Plugins…**
2. look for **qfit** in the installed plugins list
3. enable it if needed

## 3. Open the plugin

After loading:
- use the **qfit** toolbar button, or
- open it from the **Plugins** menu

## 4. Connect Strava

Inside the dock:
1. in **Connect**, enter `client_id` and `client_secret`
2. use the built-in auth helper if you still need the refresh token
3. in **Fetch activities**, set the date window, paging limits, and any filters you want to preview
4. optionally enable detailed streams; qfit only reveals the detailed-track limit when that mode is on
5. click **Fetch activities**
6. review the fetched-activity preview and query summary
7. in **Store data**, choose an output `.gpkg` and optionally enable sampled `activity_points`
8. click **Store and load layers**
9. in **Visualize**, optionally configure a basemap and click **Load basemap**
10. in **Analyze**, optionally switch **Temporal timestamps** to `Local activity time` or `UTC time`
11. click **Apply current filters to loaded layers** if you want the loaded layers and tables to follow the current dock query
12. expand **Publish / atlas** only when you want to tune atlas framing controls
13. hover the contextual-help tooltips / `?` buttons if you want reminders about detailed-track limits, point sampling, basemap setup, publish framing, or store/load vs filter behavior

## 5. What to expect in QGIS

Visible layers currently include:
- `qfit Activities`
- `qfit Activity Starts`
- `qfit Activity Points` (optional)

The generated GeoPackage also contains internal sync tables:
- `activity_registry`
- `sync_state`

## 6. Recommended first live test

For the first real run with your own data:
- use a small date range
- enable detailed streams for a limited number of activities
- write to a fresh `.gpkg`
- confirm tracks and points appear in QGIS
- then expand the date window once the first pass looks correct

## 7. If the plugin does not show up

Check:
- the install target path is correct
- QGIS was restarted after installation
- the plugin is enabled in **Manage and Install Plugins**
- Python errors in the QGIS log panel

## 8. Next likely manual checks

Once qfit is loaded successfully, good manual checks are:
- fetch summary-only activities
- fetch detailed streams for a few activities
- confirm `activity_tracks` geometries look right
- confirm `activity_points` attributes contain time / distance / HR / power where available
- test filtering, preview sorting, style presets, and temporal playback wiring
- when the `By activity type` preset is active, verify that runs/rides/winter activities keep their semantic colors and that line casing/opacity adapts sensibly when you switch between Outdoor, Light, and Satellite basemaps
- open the QGIS Temporal Controller and confirm the loaded layers respond to the chosen local/UTC playback mode
