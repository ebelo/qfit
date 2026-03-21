# qfit local QGIS testing

This document describes a practical local testing flow for qfit inside a desktop QGIS installation.

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
1. enter `client_id` and `client_secret`
2. use the built-in auth helper if you still need the refresh token
3. set the date window and paging limits
4. optionally enable detailed streams
5. optionally enable the `activity_points` layer
6. fetch activities
7. review the fetched-activity preview and query summary
8. write and load the output GeoPackage

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
- test filtering, preview sorting, and style presets
