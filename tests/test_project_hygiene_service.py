import importlib
import importlib.util
import os
import sys
import unittest
from unittest.mock import MagicMock

from tests import _path  # noqa: F401

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    _REAL_QGIS_PRESENT = importlib.util.find_spec("qgis") is not None
except ValueError:
    _REAL_QGIS_PRESENT = any(
        os.path.isdir(os.path.join(p, "qgis")) for p in sys.path if p
    )

try:
    from qfit.analysis.infrastructure.frequent_start_points_layer import (
        FREQUENT_STARTING_POINTS_LAYER_NAME,
    )
    from qfit.visualization.infrastructure.project_hygiene_service import (
        ProjectHygieneService,
    )

    QGIS_AVAILABLE = True
    QGIS_IMPORT_ERROR = None
except Exception as exc:  # pragma: no cover
    FREQUENT_STARTING_POINTS_LAYER_NAME = "qfit frequent starting points"
    ProjectHygieneService = None
    QGIS_AVAILABLE = False
    QGIS_IMPORT_ERROR = exc

SKIP_REAL = f"QGIS not available: {QGIS_IMPORT_ERROR}" if not QGIS_AVAILABLE else ""


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


def _load_service_with_mock_qgis():
    qgis_module = MagicMock()
    qgis_core = MagicMock()
    qgis_core.QgsProject = MagicMock()

    saved_modules = {
        name: sys.modules.get(name)
        for name in [
            "qgis",
            "qgis.core",
            "qfit.visualization.infrastructure.project_hygiene_service",
        ]
    }

    sys.modules["qgis"] = qgis_module
    sys.modules["qgis.core"] = qgis_core
    sys.modules.pop("qfit.visualization.infrastructure.project_hygiene_service", None)

    try:
        module = importlib.import_module("qfit.visualization.infrastructure.project_hygiene_service")
        return module.ProjectHygieneService, module
    except Exception:  # pragma: no cover
        return None, None
    finally:
        for name, original in saved_modules.items():
            if original is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = original


_MOCK_SERVICE_CLS = None
_MOCK_SERVICE_MODULE = None
if not QGIS_AVAILABLE:
    _MOCK_SERVICE_CLS, _MOCK_SERVICE_MODULE = _load_service_with_mock_qgis()

SKIP_MOCK = "QGIS is installed — real-QGIS suite provides coverage" if QGIS_AVAILABLE else ""
SKIP_MOCK_LOAD = (
    "Could not load ProjectHygieneService with mock QGIS"
    if (_MOCK_SERVICE_CLS is None and not _REAL_QGIS_PRESENT)
    else ""
)


class _ProjectHygieneServiceBehaviorMixin:
    service_cls = None

    def test_remove_stale_qfit_layers_removes_only_missing_known_file_backed_layers(self):
        project = _FakeProject(
            {
                "activities": _FakeLayer(
                    "qfit activities",
                    "/tmp/missing.gpkg|layername=activities",
                    "activities-id",
                ),
                "analysis_memory": _FakeLayer(
                    FREQUENT_STARTING_POINTS_LAYER_NAME,
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
        service = self.service_cls(
            project=project,
            path_exists=lambda path: path == "/tmp/present.gpkg",
        )

        service.remove_stale_qfit_layers()

        self.assertEqual(project.removed, ["activities-id"])


@unittest.skipUnless(QGIS_AVAILABLE, SKIP_REAL)
class ProjectHygieneServiceRealTests(
    _ProjectHygieneServiceBehaviorMixin,
    unittest.TestCase,
):
    service_cls = ProjectHygieneService


@unittest.skipIf(QGIS_AVAILABLE, SKIP_MOCK)
@unittest.skipIf(_MOCK_SERVICE_CLS is None, SKIP_MOCK_LOAD)
class ProjectHygieneServiceMockTests(
    _ProjectHygieneServiceBehaviorMixin,
    unittest.TestCase,
):
    service_cls = _MOCK_SERVICE_CLS


if __name__ == "__main__":
    unittest.main()
