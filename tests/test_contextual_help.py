import unittest
from types import SimpleNamespace

from tests import _path  # noqa: F401

from ui.contextual_help import (
    DOCK_HELP_ENTRIES,
    ContextualHelpBinder,
    HelpEntry,
    build_dock_help_entries,
)


class _FakeQt:
    TextSelectableByMouse = "selectable"
    WhatsThisCursor = "whats-this"
    NoFocus = "no-focus"


class _FakeWidgetItem:
    def __init__(self, widget=None, layout=None):
        self._widget = widget
        self._layout = layout

    def widget(self):
        return self._widget

    def layout(self):
        return self._layout


class _FakeBaseLayout:
    def __init__(self, parent=None):
        self.parent = parent
        self.items = []

    def count(self):
        return len(self.items)

    def itemAt(self, index):
        if 0 <= index < len(self.items):
            return self.items[index]
        return None

    def addWidget(self, widget):
        self.items.append(_FakeWidgetItem(widget=widget))

    def addLayout(self, layout):
        self.items.append(_FakeWidgetItem(layout=layout))

    def removeWidget(self, widget):
        self.items = [item for item in self.items if item.widget() is not widget]


class _FakeQBoxLayout(_FakeBaseLayout):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.contents_margins = None
        self.spacing = None
        self.stretches = {}
        if parent is not None and hasattr(parent, "setLayout"):
            parent.setLayout(self)

    def insertWidget(self, index, widget):
        self.items.insert(index, _FakeWidgetItem(widget=widget))

    def setContentsMargins(self, *margins):
        self.contents_margins = margins

    def setSpacing(self, spacing):
        self.spacing = spacing

    def setStretch(self, index, stretch):
        self.stretches[index] = stretch


class _FakeQFormLayout(_FakeBaseLayout):
    LABEL_ROLE = 0
    FIELD_ROLE = 1

    def __init__(self, parent=None):
        super().__init__(parent)
        self.rows = []

    def addRow(self, label_or_widget, field=None):
        if field is None:
            self.rows.append({"single": label_or_widget})
            self.items.append(_FakeWidgetItem(widget=label_or_widget))
            return
        self.rows.append({"label": label_or_widget, "field": field})
        self.items.append(_FakeWidgetItem(widget=label_or_widget))
        self.items.append(_FakeWidgetItem(widget=field))

    def insertRow(self, row, widget):
        self.rows.insert(row, {"single": widget})
        self.items.insert(row, _FakeWidgetItem(widget=widget))

    def getWidgetPosition(self, widget):
        for index, row in enumerate(self.rows):
            if row.get("single") is widget:
                return index, self.FIELD_ROLE
            if row.get("label") is widget:
                return index, self.LABEL_ROLE
            if row.get("field") is widget:
                return index, self.FIELD_ROLE
        return -1, None

    def removeWidget(self, widget):
        for row in self.rows:
            if row.get("single") is widget:
                row["single"] = None
            if row.get("label") is widget:
                row["label"] = None
            if row.get("field") is widget:
                row["field"] = None
        super().removeWidget(widget)

    def setWidget(self, row, role, widget):
        entry = self.rows[row]
        if "single" in entry:
            entry["single"] = widget
        elif role == self.LABEL_ROLE:
            entry["label"] = widget
        else:
            entry["field"] = widget
        insert_at = max(row, 0)
        self.items.insert(insert_at, _FakeWidgetItem(widget=widget))


class _FakeWidget:
    def __init__(self, text="", parent=None, object_name=""):
        self._text = text
        self._parent = parent
        self._object_name = object_name
        self.tooltip = None
        self.whats_this = None
        self.status_tip = None
        self.word_wrap = False
        self.interaction_flags = None
        self.style_sheet = None
        self.visible = False
        self.cursor = None
        self.focus_policy = None
        self.auto_raise = False
        self.layout_obj = None
        self._children = []
        if parent is not None and hasattr(parent, "_children"):
            parent._children.append(self)

    def setObjectName(self, name):
        self._object_name = name

    def objectName(self):
        return self._object_name

    def setText(self, text):
        self._text = text

    def text(self):
        return self._text

    def setToolTip(self, text):
        self.tooltip = text

    def setWhatsThis(self, text):
        self.whats_this = text

    def setStatusTip(self, text):
        self.status_tip = text

    def setWordWrap(self, value):
        self.word_wrap = value

    def setTextInteractionFlags(self, value):
        self.interaction_flags = value

    def setStyleSheet(self, value):
        self.style_sheet = value

    def show(self):
        self.visible = True

    def hide(self):
        self.visible = False

    def isVisible(self):
        return self.visible

    def setParent(self, parent):
        self._parent = parent
        if parent is not None and hasattr(parent, "_children") and self not in parent._children:
            parent._children.append(self)

    def parentWidget(self):
        return self._parent

    def setLayout(self, layout):
        self.layout_obj = layout

    def layout(self):
        return self.layout_obj

    def findChildren(self, cls):
        found = []
        for child in self._children:
            if isinstance(child, cls):
                found.append(child)
            if hasattr(child, "findChildren"):
                found.extend(child.findChildren(cls))
        return found


class _FakeLabel(_FakeWidget):
    pass


class _FakeQToolButton(_FakeWidget):
    def setAutoRaise(self, value):
        self.auto_raise = value

    def setCursor(self, value):
        self.cursor = value

    def setFocusPolicy(self, value):
        self.focus_policy = value


class _FakeRoot(_FakeWidget):
    def __init__(self):
        super().__init__(parent=None, object_name="root")
        self._layout = _FakeQBoxLayout(self)

    def layout(self):
        return self._layout


class _FakeQtWidgetsModule:
    QWidget = _FakeWidget
    QLabel = _FakeLabel
    QToolButton = _FakeQToolButton
    QHBoxLayout = _FakeQBoxLayout
    QBoxLayout = _FakeQBoxLayout
    QFormLayout = _FakeQFormLayout


class _TestBinder(ContextualHelpBinder):
    def _qtwidgets(self):
        return _FakeQtWidgetsModule

    def _qtcore(self):
        return SimpleNamespace(Qt=_FakeQt)


class ContextualHelpTests(unittest.TestCase):
    def test_dock_help_entries_cover_high_value_confusing_controls(self):
        entries = {entry.anchor_name: entry for entry in build_dock_help_entries()}

        for anchor_name in [
            "detailedRouteStrategyComboBox",
            "maxDetailedActivitiesSpinBox",
            "perPageSpinBox",
            "maxPagesSpinBox",
            "writeActivityPointsCheckBox",
            "pointSamplingStrideSpinBox",
            "backgroundPresetComboBox",
            "atlasTitleLineEdit",
            "atlasSubtitleLineEdit",
            "refreshButton",
            "loadButton",
            "clearDatabaseButton",
            "applyFiltersButton",
            "buttonLayout",
        ]:
            self.assertIn(anchor_name, entries)

        self.assertEqual(entries["detailedRouteStrategyComboBox"].label_text, "Detailed route strategy")
        self.assertIn("Missing routes only", entries["detailedRouteStrategyComboBox"].helper_text)
        self.assertEqual(entries["maxDetailedActivitiesSpinBox"].label_text, "Max new detailed routes this run")
        self.assertTrue(entries["maxDetailedActivitiesSpinBox"].help_button)
        self.assertIn("downloads up to 25 new detailed routes", entries["maxDetailedActivitiesSpinBox"].helper_text)
        self.assertEqual(entries["perPageSpinBox"].label_text, "Activities per page")
        self.assertIn("fewer API requests", entries["perPageSpinBox"].tooltip)
        self.assertEqual(entries["maxPagesSpinBox"].label_text, "Max pages")
        self.assertTrue(entries["maxPagesSpinBox"].help_button)
        self.assertIn("All is recommended", entries["maxPagesSpinBox"].helper_text)
        self.assertEqual(
            entries["writeActivityPointsCheckBox"].target_text,
            "Write sampled activity points from detailed tracks",
        )
        self.assertIn("activity_points layer", entries["writeActivityPointsCheckBox"].helper_text)
        self.assertEqual(entries["pointSamplingStrideSpinBox"].label_text, "Keep every Nth point")
        self.assertEqual(entries["backgroundPresetComboBox"].label_text, "Basemap preset")
        self.assertEqual(entries["atlasTitleLineEdit"].label_text, "Atlas title")
        self.assertEqual(entries["atlasSubtitleLineEdit"].label_text, "Atlas subtitle")
        self.assertEqual(entries["refreshButton"].target_text, "Fetch activities")
        self.assertEqual(entries["applyFiltersButton"].target_text, "Apply filters")
        self.assertEqual(entries["clearDatabaseButton"].target_text, "Clear database…")
        self.assertIn("after confirmation", entries["clearDatabaseButton"].tooltip)
        self.assertIn("Store activities", entries["buttonLayout"].helper_text)
        self.assertIn("Use Apply filters", entries["buttonLayout"].helper_text)
        self.assertNotIn("Apply current filters", entries["buttonLayout"].helper_text)

    def test_contextual_help_binder_is_importable_without_instantiating_qgis_widgets(self):
        binder = ContextualHelpBinder(root=object())
        self.assertIsNotNone(binder)

    def test_apply_updates_label_target_tooltips_and_creates_helper_and_help_button(self):
        root = _FakeRoot()
        form = _FakeQFormLayout(root)
        root._children.append(form)

        label = _FakeLabel("Old label", root, "speedLabel")
        anchor = _FakeWidget("Old control text", root, "speedSpinBox")
        form.addRow(label, anchor)
        root.speedLabel = label
        root.speedSpinBox = anchor

        binder = _TestBinder(root)
        binder.apply(
            [
                HelpEntry(
                    anchor_name="speedSpinBox",
                    label_name="speedLabel",
                    label_text="Average speed",
                    target_text="Fast enough",
                    tooltip="Explains the field",
                    helper_text="Inline helper copy",
                    help_button=True,
                )
            ]
        )

        self.assertEqual(label.text(), "Average speed")
        self.assertEqual(anchor.text(), "Fast enough")
        self.assertEqual(anchor.tooltip, "Explains the field")
        self.assertEqual(label.whats_this, "Explains the field")

        helper = getattr(root, "speedSpinBoxContextHelpLabel")
        self.assertEqual(helper.text(), "Inline helper copy")
        self.assertTrue(helper.word_wrap)
        self.assertEqual(helper.interaction_flags, _FakeQt.TextSelectableByMouse)
        self.assertIn("palette(mid)", helper.style_sheet)

        wrapper = anchor.parentWidget()
        self.assertEqual(wrapper.objectName(), "speedSpinBoxHelpField")
        self.assertEqual(wrapper.layout().contents_margins, (0, 0, 0, 0))
        self.assertEqual(wrapper.layout().spacing, 6)
        self.assertEqual(wrapper.layout().stretches[0], 1)

        help_button = None
        for item in wrapper.layout().items:
            widget = item.widget()
            if isinstance(widget, _FakeQToolButton):
                help_button = widget
                break
        self.assertIsNotNone(help_button)
        self.assertEqual(help_button.text(), "?")
        self.assertTrue(help_button.auto_raise)
        self.assertEqual(help_button.cursor, _FakeQt.WhatsThisCursor)
        self.assertEqual(help_button.focus_policy, _FakeQt.NoFocus)
        self.assertEqual(help_button.tooltip, "Explains the field")

    def test_apply_reuses_existing_helper_label_and_skips_second_help_wrapper(self):
        root = _FakeRoot()
        anchor = _FakeWidget(parent=root, object_name="distanceSpinBox")
        wrapper = _FakeWidget(parent=root, object_name="distanceSpinBoxHelpField")
        anchor.setParent(wrapper)
        root.distanceSpinBox = anchor
        root.distanceSpinBoxContextHelpLabel = _FakeLabel("Old helper", root, "distanceSpinBoxContextHelpLabel")

        binder = _TestBinder(root)
        binder.apply(
            [
                HelpEntry(
                    anchor_name="distanceSpinBox",
                    helper_text="New helper",
                    help_button=True,
                    tooltip="Hint",
                )
            ]
        )

        self.assertEqual(root.distanceSpinBoxContextHelpLabel.text(), "New helper")
        self.assertTrue(root.distanceSpinBoxContextHelpLabel.isVisible())
        self.assertIs(anchor.parentWidget(), wrapper)

    def test_insert_after_anchor_uses_box_layout_when_no_form_layout_exists(self):
        root = _FakeRoot()
        before = _FakeWidget(parent=root, object_name="before")
        anchor = _FakeWidget(parent=root, object_name="anchor")
        after = _FakeWidget(parent=root, object_name="after")
        root.layout().addWidget(before)
        root.layout().addWidget(anchor)
        root.layout().addWidget(after)
        root.anchor = anchor

        binder = _TestBinder(root)
        binder.apply([HelpEntry(anchor_name="anchor", helper_text="Helper text")])

        ordered_names = [item.widget().objectName() for item in root.layout().items]
        self.assertEqual(ordered_names, ["before", "anchor", "anchorContextHelpLabel", "after"])

    def test_find_layout_and_index_descends_into_nested_layouts(self):
        root = _FakeRoot()
        outer = root.layout()
        nested = _FakeQBoxLayout(root)
        anchor = _FakeWidget(parent=root, object_name="nestedAnchor")
        nested.addWidget(anchor)
        outer.addLayout(nested)

        binder = _TestBinder(root)
        layout, index = binder._find_layout_and_index(root.layout(), anchor)

        self.assertIs(layout, nested)
        self.assertEqual(index, 0)

    def test_replace_widget_updates_box_layout_position(self):
        root = _FakeRoot()
        target = _FakeWidget(parent=root, object_name="target")
        replacement = _FakeWidget(parent=root, object_name="replacement")
        root.layout().addWidget(target)

        binder = _TestBinder(root)
        binder._replace_widget(target, replacement)

        ordered_names = [item.widget().objectName() for item in root.layout().items]
        self.assertEqual(ordered_names, ["replacement"])

    def test_apply_safely_skips_missing_anchor_and_objects_without_supported_methods(self):
        root = _FakeRoot()
        root.present = object()
        binder = _TestBinder(root)

        binder.apply(
            [
                HelpEntry(anchor_name="missingAnchor", helper_text="Ignored"),
                HelpEntry(anchor_name="present", tooltip="No-op"),
            ]
        )

        self.assertFalse(hasattr(root, "missingAnchorContextHelpLabel"))
        self.assertEqual(binder._resolve_object(None), None)
        self.assertEqual(binder._object_name(object()), "object")


if __name__ == "__main__":
    unittest.main()
