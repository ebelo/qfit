import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch

from tests import _path  # noqa: F401

from qfit.ui.application.local_first_control_installer import (
    after_local_first_control_move_installed,
    install_local_first_audited_controls,
    install_local_first_group_controls,
    install_local_first_control_move,
    install_local_first_widget_controls,
    install_local_first_widget_move,
    local_first_after_install_hook_for_key,
    local_first_layout_index_of,
)
from qfit.ui.application.local_first_control_moves import (
    HIDE_LEGACY_ATLAS_EXPORT_BUTTON_HOOK,
    REFRESH_CONDITIONAL_VISIBILITY_HOOK,
    local_first_control_move_for_key,
    local_first_widget_move_for_key,
)


class LocalFirstControlInstallerTests(unittest.TestCase):
    def test_installs_audited_controls_in_inventory_order(self):
        dock = object()
        composition = object()

        with patch(
            "qfit.ui.application.local_first_control_installer.install_local_first_widget_move",
            return_value=True,
        ) as install_widget_move, patch(
            "qfit.ui.application.local_first_control_installer.install_local_first_control_move",
            return_value=True,
        ) as install_control_move, patch(
            "qfit.ui.application.local_first_control_installer.after_local_first_control_move_installed",
        ) as after_control_move:
            install_local_first_audited_controls(dock, composition)

        self.assertEqual(
            install_widget_move.call_args_list,
            [
                call(dock, composition, "activity_style"),
            ],
        )
        self.assertEqual(
            install_control_move.call_args_list,
            [
                call(dock, composition, "activity_preview"),
                call(dock, composition, "backfill_routes"),
                call(dock, composition, "map_filters"),
                call(dock, composition, "atlas_pdf"),
                call(dock, composition, "basemap"),
                call(dock, composition, "storage"),
            ],
        )
        self.assertEqual(
            after_control_move.call_args_list,
            [
                call(dock, "activity_preview", installed=True),
                call(dock, "backfill_routes", installed=True),
                call(dock, "map_filters", installed=True),
                call(dock, "atlas_pdf", installed=True),
                call(dock, "basemap", installed=True),
                call(dock, "storage", installed=True),
            ],
        )

    def test_control_move_lookup_installs_matching_group(self):
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
        map_content = SimpleNamespace(
            filter_controls_layout=MagicMock(return_value=target_layout),
            set_filter_controls_visible=MagicMock(),
        )

        installed = install_local_first_control_move(
            dock,
            SimpleNamespace(map_content=map_content),
            "map_filters",
        )

        self.assertTrue(installed)
        target_layout.addWidget.assert_called_once_with(group)
        self.assertTrue(dock._local_first_filter_controls_installed)

    def test_widget_move_lookup_installs_matching_widgets(self):
        style_label = MagicMock()
        style_combo = MagicMock()
        dock = SimpleNamespace(
            stylePresetLabel=style_label,
            stylePresetComboBox=style_combo,
        )
        target_layout = MagicMock()
        map_content = SimpleNamespace(
            style_controls_layout=MagicMock(return_value=target_layout),
            set_style_controls_visible=MagicMock(),
        )

        installed = install_local_first_widget_move(
            dock,
            SimpleNamespace(map_content=map_content),
            "activity_style",
        )

        self.assertTrue(installed)
        self.assertEqual(
            target_layout.addWidget.call_args_list,
            [call(style_label), call(style_combo)],
        )
        self.assertTrue(dock._local_first_activity_style_controls_installed)

    def test_after_control_move_installed_runs_hook_only_after_successful_move(self):
        hook = MagicMock()
        dock = SimpleNamespace()

        with patch(
            "qfit.ui.application.local_first_control_installer."
            "local_first_after_install_hook_for_key",
            return_value=hook,
        ) as hook_for_key:
            after_local_first_control_move_installed(dock, "basemap", installed=False)
            after_local_first_control_move_installed(dock, "basemap", installed=True)

        hook_for_key.assert_called_once_with(REFRESH_CONDITIONAL_VISIBILITY_HOOK)
        hook.assert_called_once_with(dock)

    def test_after_install_hook_lookup_resolves_application_hooks(self):
        self.assertIsNotNone(
            local_first_after_install_hook_for_key(
                REFRESH_CONDITIONAL_VISIBILITY_HOOK,
            )
        )
        self.assertIsNotNone(
            local_first_after_install_hook_for_key(
                HIDE_LEGACY_ATLAS_EXPORT_BUTTON_HOOK,
            )
        )

    def test_layout_index_falls_back_to_test_layout_widget_list(self):
        anchor = object()
        layout = SimpleNamespace(widgets=[object(), anchor])

        self.assertEqual(local_first_layout_index_of(layout, anchor), 1)
        self.assertIsNone(local_first_layout_index_of(layout, object()))
        self.assertIsNone(local_first_layout_index_of(SimpleNamespace(), anchor))

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
        for widget in (style_label, style_combo):
            widget.parentWidget.return_value = source_parent
        dock = SimpleNamespace(
            stylePresetLabel=style_label,
            stylePresetComboBox=style_combo,
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
            [call(style_label), call(style_combo)],
        )
        self.assertEqual(
            target_layout.addWidget.call_args_list,
            [call(style_label), call(style_combo)],
        )
        for widget in (style_label, style_combo):
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
