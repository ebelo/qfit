# QGIS 4 light mode on Windows

If Windows uses dark mode, QGIS 4's **Default** UI theme can inherit the dark
system palette. Selecting **Fusion** alone does not force light colours:
**style** controls widget appearance, while the **UI theme** controls colours.
This can make the current qfit dock difficult to read.

The following workaround was verified by a qfit user with **QGIS 4.2.3 on
Windows**. That setup has no in-app force-light switch; the Qt Windows platform
option below lets Windows remain dark while QGIS uses a light interface.

## Create a light-mode shortcut

1. Close QGIS, saving any work first.
2. Copy your existing QGIS 4 shortcut so the original remains available.
3. Right-click the copy and open **Properties → Shortcut**.
4. Append a space followed by this option to the existing **Target**, outside
   the executable path's closing quote. Preserve the existing command and any
   other arguments:

   ```text
   -platform windows:darkmode=0
   ```

   For example, a shortcut pointing directly to the QGIS executable could read:

   ```text
   "C:\Program Files\QGIS 4.2.3\bin\qgis-bin.exe" -platform windows:darkmode=0
   ```

   This installation path is only an example. Use your shortcut's actual target;
   do not replace an existing launcher with this example executable path.

5. Save the shortcut and start QGIS through that modified copy.
6. In **Settings → Options → General → Application**, select:

   - **Style:** `Fusion`
   - **UI theme:** `Default`

7. Restart QGIS through the modified shortcut to apply the settings fully.

QGIS and the qfit dock should now use a readable light interface while Windows
remains in dark mode. Use this shortcut for subsequent launches; the command-line
option does not apply when starting QGIS through another shortcut or a file
association.

## Undo the workaround

Close QGIS and use the original shortcut, or remove
`-platform windows:darkmode=0` from the copy's Target. With the Default theme,
QGIS can inherit the Windows palette again. The Fusion style selection remains
until you change it in Options.

This is an application-launch workaround, not a fix for qfit's dark-theme
contrast. It does not change Windows settings or map-layer styling.
