import importlib
import sys
import unittest
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

from tests import _path  # noqa: F401


class _StubQgsField:
    def __init__(self, name, field_type):
        self._name = name
        self._type = field_type

    def name(self):
        return self._name

    def type(self):
        return self._type


class _StubQgsFields(list):
    def append(self, field):
        super().append(field)


class _StubSaveVectorOptions:
    def __init__(self):
        self.driverName = None
        self.layerName = None
        self.fileEncoding = None
        self.actionOnExistingFile = None


class _StubVectorFileWriter:
    NoError = 0
    CreateOrOverwriteFile = 1
    CreateOrOverwriteLayer = 2
    write_result = (NoError, "", "")
    last_call = None

    @classmethod
    def SaveVectorOptions(cls):
        return _StubSaveVectorOptions()

    @classmethod
    def writeAsVectorFormatV3(cls, layer, output_path, transform_context, options):
        cls.last_call = {
            "layer": layer,
            "output_path": output_path,
            "transform_context": transform_context,
            "options": options,
        }
        return cls.write_result


class GpkgGeopackagePureTests(unittest.TestCase):
    def _install_qgis_stubs(self):
        qvariant = SimpleNamespace(String="String", Double="Double", Int="Int")
        qtcore = ModuleType("qgis.PyQt.QtCore")
        qtcore.QVariant = qvariant

        qgis_pyqt = ModuleType("qgis.PyQt")
        qgis_pyqt.QtCore = qtcore

        qgis_core = ModuleType("qgis.core")
        qgis_core.QgsField = _StubQgsField
        qgis_core.QgsFields = _StubQgsFields
        qgis_core.QgsCoordinateTransformContext = lambda: "empty-context"
        qgis_core.QgsVectorFileWriter = _StubVectorFileWriter
        qgis_core.QgsProject = type(
            "QgsProject",
            (),
            {"instance": staticmethod(lambda: None)},
        )

        qgis = ModuleType("qgis")
        qgis.core = qgis_core
        qgis.PyQt = qgis_pyqt

        return {
            "qgis": qgis,
            "qgis.core": qgis_core,
            "qgis.PyQt": qgis_pyqt,
            "qgis.PyQt.QtCore": qtcore,
        }

    def test_schema_module_and_legacy_shim_share_exports(self):
        module_names = [
            "qfit.activities.infrastructure.geopackage.gpkg_schema",
            "qfit.gpkg_schema",
        ]
        with patch.dict(sys.modules, self._install_qgis_stubs()):
            for name in module_names:
                sys.modules.pop(name, None)

            schema_module = importlib.import_module(
                "qfit.activities.infrastructure.geopackage.gpkg_schema"
            )
            legacy_module = importlib.import_module("qfit.gpkg_schema")

            fields = schema_module.make_qgs_fields(schema_module.TRACK_FIELDS[:2])

            self.assertEqual([field.name() for field in fields], ["source", "source_activity_id"])
            self.assertEqual(legacy_module.TRACK_FIELDS, schema_module.TRACK_FIELDS)
            self.assertEqual(legacy_module.GPKG_LAYER_SCHEMA, schema_module.GPKG_LAYER_SCHEMA)
            self.assertIs(legacy_module.make_qgs_fields, schema_module.make_qgs_fields)

    def test_gpkg_io_module_handles_success_and_error_paths(self):
        module_names = [
            "qfit.activities.infrastructure.geopackage.gpkg_io",
            "qfit.gpkg_io",
        ]
        qgis_stubs = self._install_qgis_stubs()
        qgis_core = qgis_stubs["qgis.core"]
        project_instance = SimpleNamespace(transformContext=lambda: "project-context")
        qgis_core.QgsProject = type(
            "QgsProject",
            (),
            {"instance": staticmethod(lambda: project_instance)},
        )

        with patch.dict(sys.modules, qgis_stubs):
            for name in module_names:
                sys.modules.pop(name, None)

            module = importlib.import_module("qfit.activities.infrastructure.geopackage.gpkg_io")
            legacy_module = importlib.import_module("qfit.gpkg_io")

            _StubVectorFileWriter.write_result = (_StubVectorFileWriter.NoError, "", "")
            module.write_layer_to_gpkg("layer", "/tmp/out.gpkg", "activity_tracks", True)
            self.assertEqual(
                _StubVectorFileWriter.last_call["options"].actionOnExistingFile,
                _StubVectorFileWriter.CreateOrOverwriteFile,
            )
            self.assertEqual(_StubVectorFileWriter.last_call["transform_context"], "project-context")
            self.assertIs(legacy_module.write_layer_to_gpkg, module.write_layer_to_gpkg)

            module.QgsProject = type(
                "QgsProject",
                (),
                {"instance": staticmethod(lambda: None)},
            )
            _StubVectorFileWriter.write_result = (99, "boom", "details")
            with self.assertRaises(RuntimeError):
                module.write_layer_to_gpkg("layer", "/tmp/out.gpkg", "activity_tracks", False)
            self.assertEqual(
                _StubVectorFileWriter.last_call["options"].actionOnExistingFile,
                _StubVectorFileWriter.CreateOrOverwriteLayer,
            )
            self.assertEqual(_StubVectorFileWriter.last_call["transform_context"], "empty-context")


if __name__ == "__main__":
    unittest.main()
