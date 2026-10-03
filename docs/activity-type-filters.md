# Select multiple activity types

In **Map → Filters → Activity types**, open the selector and check the types
wanted—for example **Walk** and **Hike**. You do not need Ctrl/Shift or an OR
expression. Click **Apply filters** to update the loaded map layers.

Checked types match with **OR** (Walk **or** Hike). Date, distance and Name contains
filters still combine with **AND**. The text field remains
one case-insensitive contains phrase; it is not a multi-term OR search.

Choose **All**, or uncheck every type, to remove the type restriction. Choices
are saved when filters/settings are saved and restored next time qfit opens.
Refreshing available types preserves checked labels—even labels missing from
the new dataset—to avoid silently showing all activities. Choose All explicitly
to reset those restrictions. Selecting a broad type still matches either its
activity-type or sport-type field, as the previous single-type selector did.

The shared selection drives previews, map subsets and analysis queries. After
changing filters, **Analysis → Heatmap → Run analysis** regenerates the static
heatmap for that selection. Pan/zoom or hiding tracks does not change it.

The obsolete route-detail availability selector has been removed. Old saved
“Detailed routes only” or “Missing detailed routes” choices are ignored, so they
cannot hide activities after upgrading. Route ingestion and stored geometry are
unchanged; the lower-level query API retains its route-detail compatibility.
