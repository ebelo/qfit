from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable


@dataclass(frozen=True)
class HelpEntry:
    anchor_name: str
    label_name: str | None = None
    label_text: str | None = None
    target_text: str | None = None
    tooltip: str | None = None
    helper_text: str | None = None
    help_button: bool = False


DOCK_HELP_ENTRIES: tuple[HelpEntry, ...] = (
    HelpEntry(
        anchor_name="detailedStreamsCheckBox",
        target_text="Fetch detailed routes when available",
        tooltip=(
            "Downloads higher-fidelity Strava route data for some activities so qfit can write richer "
            "geometry, timestamps, sampled points, and publish/profile metadata."
        ),
        helper_text=(
            "Turn this on when you want more than start/end points. qfit caches downloaded routes locally, "
            "and already detailed or cached routes do not consume the per-run download budget."
        ),
    ),
    HelpEntry(
        anchor_name="maxDetailedActivitiesSpinBox",
        label_name="maxDetailedActivitiesLabel",
        label_text="Max new detailed routes this run",
        tooltip=(
            "Maximum number of still-missing activities that qfit will newly enrich with detailed Strava "
            "routes during this fetch. Lower values keep imports faster and burn less Strava quota."
        ),
        helper_text=(
            "This limit only applies when detailed routes are enabled. Example: with 100 fetched activities and a "
            "limit of 25, qfit still writes all 100 activities but only downloads up to 25 new detailed routes. "
            "Already detailed or cached routes do not count against that limit."
        ),
        help_button=True,
    ),
    HelpEntry(
        anchor_name="detailedRouteStrategyComboBox",
        label_name="detailedRouteStrategyLabel",
        label_text="Detailed route strategy",
        tooltip=(
            "Choose whether qfit spends the detailed-route budget on the first fetched activities or on "
            "activities still missing detailed routes."
        ),
        helper_text=(
            "Missing routes only is the recommended default for archive backfill because repeated runs keep "
            "making forward progress. Recent fetch only behaves more like the older recent-sync workflow."
        ),
        help_button=True,
    ),
    HelpEntry(
        anchor_name="backgroundMapCheckBox",
        target_text="Load a Mapbox basemap in QGIS",
        tooltip=(
            "Adds a background basemap underneath qfit layers. Use the separate load button when you want to add "
            "or refresh it explicitly."
        ),
    ),
    HelpEntry(
        anchor_name="backgroundPresetComboBox",
        label_name="backgroundPresetLabel",
        label_text="Basemap preset",
        tooltip=(
            "Choose a built-in Mapbox style or a custom style slot. Outdoor, Light, and Satellite work with the "
            "default Mapbox owner/style fields; Winter and Custom expect your own Mapbox Studio style."
        ),
        helper_text=(
            "Built-in presets are the quickest path. Use Winter or Custom when you want your own Mapbox Studio "
            "style instead of qfit's default examples."
        ),
        help_button=True,
    ),
    HelpEntry(
        anchor_name="mapboxStyleOwnerLineEdit",
        label_name="mapboxStyleOwnerLabel",
        label_text="Custom style owner",
        tooltip=(
            "Mapbox username or organization that owns the selected custom style. Usually left as 'mapbox' for "
            "built-in presets."
        ),
    ),
    HelpEntry(
        anchor_name="mapboxStyleIdLineEdit",
        label_name="mapboxStyleIdLabel",
        label_text="Custom style ID",
        tooltip=(
            "Mapbox Studio style ID such as outdoors-v12 or your own published style identifier."
        ),
        help_button=True,
    ),
    HelpEntry(
        anchor_name="loadBackgroundButton",
        target_text="Load basemap",
        tooltip=(
            "Adds the selected basemap or refreshes the existing one. qfit keeps it below the activity layers so "
            "tracks and points stay visible on top."
        ),
    ),
    HelpEntry(
        anchor_name="writeActivityPointsCheckBox",
        target_text="Write sampled activity_points from detailed tracks",
        tooltip=(
            "Creates an optional point layer along each detailed activity so you can style, analyze, or animate "
            "sampled stream data in QGIS."
        ),
        helper_text=(
            "Best when detailed tracks are enabled. The point layer can include sampled distance, time, elevation, "
            "speed, heart rate, cadence, power, temperature, and moving-state values when Strava provides them."
        ),
    ),
    HelpEntry(
        anchor_name="pointSamplingStrideSpinBox",
        label_name="pointSamplingStrideLabel",
        label_text="Keep every Nth point",
        tooltip=(
            "Controls how densely qfit samples the detailed geometry into the activity_points layer. 1 keeps every "
            "point, 5 keeps every fifth point, and higher values make lighter but less detailed point layers."
        ),
        helper_text=(
            "Use 1-2 for dense analysis or smoother temporal playback. Use larger values when you want smaller files "
            "or faster redraws."
        ),
        help_button=True,
    ),
    HelpEntry(
        anchor_name="atlasTitleLineEdit",
        label_name="atlasTitleLabel",
        label_text="Atlas title",
        tooltip=(
            "Sets the title shown on the exported atlas cover page."
        ),
    ),
    HelpEntry(
        anchor_name="atlasSubtitleLineEdit",
        label_name="atlasSubtitleLabel",
        label_text="Atlas subtitle",
        tooltip=(
            "Overrides the cover-page subtitle. Leave it blank to keep qfit's generated activity/date summary."
        ),
        helper_text=(
            "Atlas layout framing stays on qfit's internal defaults. These fields only affect the exported PDF cover text."
        ),
        help_button=True,
    ),
    HelpEntry(
        anchor_name="detailedRouteStatusComboBox",
        target_text="Only activities with detailed tracks",
        tooltip=(
            "Filters the preview and loaded layers to activities that already have detailed stream geometry available."
        ),
    ),
    HelpEntry(
        anchor_name="refreshButton",
        target_text="Fetch activities",
        tooltip=(
            "Pulls all activities from Strava using the current paging and detailed-track settings without "
            "writing anything to QGIS yet.  Date filters apply only to the preview and loaded layers."
        ),
    ),
    HelpEntry(
        anchor_name="loadButton",
        target_text="Store activities",
        tooltip=(
            "Writes the full fetched result to the GeoPackage only. Use Load activity layers in Visualize when you want to "
            "bring the stored qfit layers into QGIS."
        ),
    ),
    HelpEntry(
        anchor_name="loadLayersButton",
        target_text="Load activity layers",
        tooltip=(
            "Loads the stored qfit layers from the GeoPackage into QGIS. Use this after storing activities or when "
            "reopening an existing qfit database."
        ),
    ),
    HelpEntry(
        anchor_name="applyFiltersButton",
        target_text="Apply current filters to loaded layers",
        tooltip=(
            "Turns the current dock query into real QGIS layer subset filters and reapplies styling/background logic "
            "to the already loaded layers."
        ),
    ),
    HelpEntry(
        anchor_name="buttonLayout",
        helper_text=(
            "Use Store activities to update the GeoPackage database. Then use Load activity layers in Visualize when you want "
            "the stored dataset in QGIS. Apply current filters only when you want loaded layers and tables to match "
            "the current dock query."
        ),
    ),
)


def build_dock_help_entries() -> tuple[HelpEntry, ...]:
    return DOCK_HELP_ENTRIES


class ContextualHelpBinder:
    def __init__(self, root: Any):
        self.root = root

    def apply(self, entries: Iterable[HelpEntry]) -> None:
        for entry in entries:
            self._apply_entry(entry)

    def _apply_entry(self, entry: HelpEntry) -> None:
        anchor = self._resolve_object(entry.anchor_name)
        if anchor is None:
            return

        label = self._resolve_object(entry.label_name) if entry.label_name else None
        if entry.label_text and label is not None and hasattr(label, "setText"):
            label.setText(entry.label_text)
        if entry.target_text and hasattr(anchor, "setText"):
            anchor.setText(entry.target_text)

        if entry.tooltip:
            self._apply_tooltip(anchor, entry.tooltip)
            if label is not None:
                self._apply_tooltip(label, entry.tooltip)

        if entry.helper_text:
            self._ensure_helper_label(anchor, entry.helper_text)

        if entry.help_button:
            self._ensure_help_button(anchor, entry.tooltip or entry.helper_text or "")

    def _resolve_object(self, name: str | None) -> Any:
        if not name:
            return None
        return getattr(self.root, name, None)

    def _apply_tooltip(self, obj: Any, text: str) -> None:
        if hasattr(obj, "setToolTip"):
            obj.setToolTip(text)
        if hasattr(obj, "setWhatsThis"):
            obj.setWhatsThis(text)
        if hasattr(obj, "setStatusTip"):
            obj.setStatusTip(text)

    def _ensure_helper_label(self, anchor: Any, text: str) -> None:
        helper_name = f"{self._object_name(anchor)}ContextHelpLabel"
        existing = getattr(self.root, helper_name, None)
        if existing is not None:
            existing.setText(text)
            existing.show()
            return

        qtwidgets = self._qtwidgets()
        helper_parent = self._helper_parent(anchor)
        helper = qtwidgets.QLabel(text, helper_parent)
        helper.setObjectName(helper_name)
        helper.setWordWrap(True)
        helper.setTextInteractionFlags(self._qtcore().Qt.TextSelectableByMouse)
        helper.setStyleSheet("color: palette(mid); margin-top: 2px; margin-bottom: 4px;")
        self._insert_after_anchor(anchor, helper)
        setattr(self.root, helper_name, helper)

    def _ensure_help_button(self, anchor: Any, text: str) -> None:
        if not text or not hasattr(anchor, "parentWidget"):
            return
        parent = anchor.parentWidget()
        if parent is not None and parent.objectName() == f"{self._object_name(anchor)}HelpField":
            return

        qtwidgets = self._qtwidgets()
        wrapper = qtwidgets.QWidget(parent)
        wrapper.setObjectName(f"{self._object_name(anchor)}HelpField")
        layout = qtwidgets.QHBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self._replace_widget(anchor, wrapper)
        anchor.setParent(wrapper)
        layout.addWidget(anchor)

        button = qtwidgets.QToolButton(wrapper)
        button.setObjectName(f"{self._object_name(anchor)}HelpButton")
        button.setText("?")
        button.setAutoRaise(True)
        button.setToolTip(text)
        button.setWhatsThis(text)
        button.setStatusTip(text)
        button.setCursor(self._qtcore().Qt.WhatsThisCursor)
        button.setFocusPolicy(self._qtcore().Qt.NoFocus)
        button.setStyleSheet("font-weight: bold; padding: 0 4px;")
        layout.addWidget(button)
        layout.setStretch(0, 1)

    def _insert_after_anchor(self, anchor: Any, helper: Any) -> None:
        qtwidgets = self._qtwidgets()
        if isinstance(anchor, qtwidgets.QWidget):
            form_layout = self._find_direct_form_layout(anchor)
            if form_layout is not None:
                row, _role = form_layout.getWidgetPosition(anchor)
                if row >= 0:
                    form_layout.insertRow(row + 1, helper)
                    return

        found = self._find_layout_and_index(self.root.layout(), anchor)
        if found is None:
            return

        layout, index = found
        if isinstance(layout, qtwidgets.QBoxLayout):
            layout.insertWidget(index + 1, helper)
        elif isinstance(layout, qtwidgets.QFormLayout):
            layout.insertRow(index + 1, helper)

    def _replace_widget(self, target: Any, replacement: Any) -> None:
        qtwidgets = self._qtwidgets()
        form_layout = self._find_direct_form_layout(target)
        if form_layout is not None:
            row, role = form_layout.getWidgetPosition(target)
            if row >= 0:
                form_layout.removeWidget(target)
                form_layout.setWidget(row, role, replacement)
                return

        found = self._find_layout_and_index(self.root.layout(), target)
        if found is None:
            return

        layout, index = found
        if isinstance(layout, qtwidgets.QBoxLayout):
            layout.removeWidget(target)
            layout.insertWidget(index, replacement)

    def _find_direct_form_layout(self, widget: Any) -> Any:
        qtwidgets = self._qtwidgets()
        for candidate in self.root.findChildren(qtwidgets.QFormLayout):
            row, _role = candidate.getWidgetPosition(widget)
            if row >= 0:
                return candidate
        return None

    def _helper_parent(self, anchor: Any) -> Any:
        form_layout = self._find_direct_form_layout(anchor) if hasattr(anchor, "parentWidget") else None
        if form_layout is not None and hasattr(form_layout, "parentWidget"):
            parent = form_layout.parentWidget()
            if parent is not None:
                return parent
        if hasattr(anchor, "parentWidget"):
            parent = anchor.parentWidget()
            if parent is not None:
                return parent
        return self.root

    def _find_layout_and_index(self, layout: Any, anchor: Any) -> Any:
        if layout is None:
            return None
        for index in range(layout.count()):
            item = layout.itemAt(index)
            if item is None:
                continue
            if item.widget() is anchor or item.layout() is anchor:
                return layout, index
            child_layout = item.layout()
            if child_layout is not None:
                found = self._find_layout_and_index(child_layout, anchor)
                if found is not None:
                    return found
        return None

    def _object_name(self, obj: Any) -> str:
        if hasattr(obj, "objectName"):
            name = obj.objectName()
            if name:
                return name
        return obj.__class__.__name__

    def _qtwidgets(self):
        from qgis.PyQt import QtWidgets

        return QtWidgets

    def _qtcore(self):
        from qgis.PyQt import QtCore

        return QtCore
