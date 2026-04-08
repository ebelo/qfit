import sys
import unittest
from types import ModuleType
from unittest.mock import MagicMock, patch

from tests import _path  # noqa: F401
from qfit.atlas.cover_composer import AtlasCoverComposer


class TestAtlasCoverComposer(unittest.TestCase):
    def test_build_layout_delegates_to_export_task_builder(self):
        fake_module = ModuleType("qfit.atlas.export_task")
        fake_builder = MagicMock(return_value="layout")
        fake_module.build_cover_layout = fake_builder

        with patch.dict(sys.modules, {"qfit.atlas.export_task": fake_module}):
            result = AtlasCoverComposer().build_layout(
                "atlas-layer",
                project="project",
                map_layers=["layer"],
                cover_data={"title": "Atlas"},
            )

        self.assertEqual(result, "layout")
        fake_builder.assert_called_once_with(
            "atlas-layer",
            project="project",
            map_layers=["layer"],
            cover_data={"title": "Atlas"},
        )


if __name__ == "__main__":
    unittest.main()
