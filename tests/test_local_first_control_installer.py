import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, call

from tests import _path  # noqa: F401

from qfit.ui.application.local_first_control_installer import (
    install_local_first_group_controls,
    install_local_first_widget_controls,
)
from qfit.ui.application.local_first_control_moves import (
    local_first_control_move_for_key,
    local_first_widget_move_for_key,
)


class LocalFirstControlInstallerTests(unittest.TestCase):
    def test_installs_group_move_from_audited_inventory(self):
        source_layout = MagicMock()
        source_parent = SimpleNamespace(layout=lambda: source_layout)
        group = MagicMock()
        group.parentWidget.return_value = source_parent
        dock = SimpleNamespace(
            filterGroupBox=group,
            activityTypeComboBox=object(),
            activitySearchLineEdit=object(),
            dateFromEdit=object(),
            dateToEdit=object(),
            minDistanceSpinBox=object(),
            maxDistanceSpinBox=object(),
            detailedRouteStatusComboBox=object(),
        )
        target_layout = MagicMock()
        panel = object()
        map_content = SimpleNamespace(
            filter_controls_panel=panel,
            filter_controls_layout=MagicMock(return_value=target_layout),
            set_filter_controls_visible=MagicMock(),
        )

        installed = install_local_first_group_controls(
            dock,
            SimpleNamespace(map_content=map_content),
            local_first_control_move_for_key("map_filters"),
        )

        self.assertTrue(installed)
        source_layout.removeWidget.assert_called_once_with(group)
        group.setParent.assert_called_once_with(panel)
        group.setTitle.assert_called_once_with("Map filters")
        target_layout.addWidget.assert_called_once_with(group)
        group.show.assert_called_once_with()
        map_content.set_filter_controls_visible.assert_called_once_with()
        self.assertTrue(dock._local_first_filter_controls_installed)
        self.assertEqual(dock._local_first_filter_controls_installed_target, id(map_content))

    def test_group_move_requires_audited_backing_widgets(self):
        target_layout = MagicMock()
        dock = SimpleNamespace(
            atlasPdfGroupBox=MagicMock(),
            atlasPdfPathLineEdit=object(),
        )

        installed = install_local_first_group_controls(
            dock,
            SimpleNamespace(
                atlas_content=SimpleNamespace(outer_layout=lambda: target_layout),
            ),
            local_first_control_move_for_key("atlas_pdf"),
        )

        self.assertFalse(installed)
        target_layout.addWidget.assert_not_called()
        self.assertFalse(getattr(dock, "_local_first_atlas_pdf_controls_installed", False))

    def test_installs_loose_widget_move_from_audited_inventory(self):
        source_layout = MagicMock()
        source_parent = SimpleNamespace(layout=lambda: source_layout)
        style_label = MagicMock()
        style_combo = MagicMock()
        preview_label = MagicMock()
        preview_combo = MagicMock()
        for widget in (style_label, style_combo, preview_label, preview_combo):
            widget.parentWidget.return_value = source_parent
        dock = SimpleNamespace(
            stylePresetLabel=style_label,
            stylePresetComboBox=style_combo,
            previewSortLabel=preview_label,
            previewSortComboBox=preview_combo,
        )
        target_layout = MagicMock()
        panel = object()
        map_content = SimpleNamespace(
            style_controls_panel=panel,
            style_controls_layout=MagicMock(return_value=target_layout),
            set_style_controls_visible=MagicMock(),
        )

        installed = install_local_first_widget_controls(
            dock,
            SimpleNamespace(map_content=map_content),
            local_first_widget_move_for_key("activity_style"),
        )

        self.assertTrue(installed)
        self.assertEqual(
            source_layout.removeWidget.call_args_list,
            [call(style_label), call(style_combo), call(preview_label), call(preview_combo)],
        )
        self.assertEqual(
            target_layout.addWidget.call_args_list,
            [call(style_label), call(style_combo), call(preview_label), call(preview_combo)],
        )
        for widget in (style_label, style_combo, preview_label, preview_combo):
            widget.setParent.assert_called_once_with(panel)
            widget.show.assert_called_once_with()
        map_content.set_style_controls_visible.assert_called_once_with()
        self.assertTrue(dock._local_first_activity_style_controls_installed)
        self.assertEqual(
            dock._local_first_activity_style_controls_installed_target,
            id(map_content),
        )


if __name__ == "__main__":
    unittest.main()
