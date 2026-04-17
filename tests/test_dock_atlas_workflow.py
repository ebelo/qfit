import unittest
from unittest.mock import MagicMock

from tests import _path  # noqa: F401
from qfit.activities.application.activity_selection_state import ActivitySelectionState
from qfit.activities.domain.activity_query import ActivityQuery
from qfit.ui.application import DockAtlasExportRequest, DockAtlasWorkflowCoordinator


class DockAtlasWorkflowCoordinatorTests(unittest.TestCase):
    def test_build_export_command_delegates_to_use_case(self):
        atlas_export_use_case = MagicMock()
        atlas_export_use_case.build_command.return_value = "command"
        coordinator = DockAtlasWorkflowCoordinator(
            atlas_export_use_case=atlas_export_use_case,
        )
        request = DockAtlasExportRequest(
            atlas_layer="atlas-layer",
            selection_state=ActivitySelectionState(
                query=ActivityQuery(),
                filtered_count=5,
            ),
            output_path="/tmp/out.pdf",
            atlas_title="Spring Atlas",
            atlas_subtitle="Road and trail",
            on_finished="finished-callback",
            pre_export_tile_mode="Raster",
            preset_name="Outdoors",
            access_token="token",
            style_owner="mapbox",
            style_id="outdoors-v12",
            background_enabled=True,
            profile_plot_style="profile-style",
        )

        command = coordinator.build_export_command(request)

        self.assertEqual(command, "command")
        atlas_export_use_case.build_command.assert_called_once_with(
            atlas_layer="atlas-layer",
            selection_state=request.selection_state,
            output_path="/tmp/out.pdf",
            atlas_title="Spring Atlas",
            atlas_subtitle="Road and trail",
            on_finished="finished-callback",
            pre_export_tile_mode="Raster",
            preset_name="Outdoors",
            access_token="token",
            style_owner="mapbox",
            style_id="outdoors-v12",
            background_enabled=True,
            profile_plot_style="profile-style",
        )


if __name__ == "__main__":
    unittest.main()
