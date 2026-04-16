import os
import unittest
from unittest.mock import patch

from tests import _path  # noqa: F401

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from qfit.visualization.infrastructure import project_hygiene_service as project_hygiene_service_module
from qfit.visualization.application.project_hygiene_port import ProjectHygienePort
from qfit.visualization.infrastructure.project_hygiene_service import ProjectHygieneService


class _FakeLayer:
    def __init__(self, name, source, layer_id):
        self._name = name
        self._source = source
        self._id = layer_id

    def name(self):
        return self._name

    def source(self):
        return self._source

    def id(self):
        return self._id


class _FakeProject:
    def __init__(self, layers):
        self._layers = layers
        self.removed = []

    def mapLayers(self):
        return self._layers

    def removeMapLayer(self, layer_id):
        self.removed.append(layer_id)


class ProjectHygieneServiceTests(unittest.TestCase):
    def test_service_satisfies_project_hygiene_port(self):
        service = ProjectHygieneService(project=_FakeProject({}), path_exists=lambda _path: True)

        self.assertIsInstance(service, ProjectHygienePort)

    def test_remove_stale_qfit_layers_removes_only_missing_known_file_backed_layers(self):
        project = _FakeProject(
            {
                "activities": _FakeLayer(
                    "qfit activities",
                    "/tmp/missing.gpkg|layername=activities",
                    "activities-id",
                ),
                "analysis_memory": _FakeLayer(
                    "qfit frequent starting points",
                    "Point?crs=EPSG:4326",
                    "analysis-id",
                ),
                "unrelated_missing": _FakeLayer(
                    "other",
                    "/tmp/missing.gpkg|layername=other",
                    "other-id",
                ),
                "ambiguous_known_name": _FakeLayer(
                    "qfit activities",
                    "",
                    "ambiguous-id",
                ),
                "existing_gpkg": _FakeLayer(
                    "qfit activity points",
                    "/tmp/present.gpkg",
                    "points-id",
                ),
            }
        )
        service = ProjectHygieneService(
            project=project,
            path_exists=lambda path: path == "/tmp/present.gpkg",
        )

        service.remove_stale_qfit_layers()

        self.assertEqual(project.removed, ["activities-id"])

    def test_constructor_uses_default_project_and_default_path_exists(self):
        project = _FakeProject(
            {
                "activities": _FakeLayer(
                    "qfit activities",
                    "/tmp/missing.gpkg|layername=activities",
                    "activities-id",
                )
            }
        )

        with (
            patch.object(project_hygiene_service_module, "_default_project", return_value=project) as default_project,
            patch.object(project_hygiene_service_module.os.path, "exists", return_value=False) as path_exists,
        ):
            service = ProjectHygieneService()
            service.remove_stale_qfit_layers()

        default_project.assert_called_once_with()
        path_exists.assert_called_once_with("/tmp/missing.gpkg")
        self.assertEqual(project.removed, ["activities-id"])


if __name__ == "__main__":
    unittest.main()
