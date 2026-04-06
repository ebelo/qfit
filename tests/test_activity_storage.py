import ast
import tempfile
import unittest
from pathlib import Path

from tests import _path  # noqa: F401
from qfit.activity_storage import ActivityStore, GeoPackageActivityStore


class ActivityStoreAdapterTests(unittest.TestCase):
    def test_geopackage_activity_store_satisfies_port(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = GeoPackageActivityStore(str(Path(tmpdir) / "qfit.sqlite"))
            self.assertIsInstance(store, ActivityStore)


class GeoPackageWriterStoragePortTests(unittest.TestCase):
    def test_writer_accepts_and_stores_activity_store_factory(self):
        module_path = (
            Path(__file__).resolve().parents[1]
            / "activities"
            / "infrastructure"
            / "geopackage"
            / "gpkg_writer.py"
        )
        tree = ast.parse(module_path.read_text(), filename=str(module_path))

        geo_writer = next(
            node for node in tree.body
            if isinstance(node, ast.ClassDef) and node.name == "GeoPackageWriter"
        )
        init_fn = next(
            node for node in geo_writer.body
            if isinstance(node, ast.FunctionDef) and node.name == "__init__"
        )

        param_names = [arg.arg for arg in init_fn.args.args]
        self.assertIn("activity_store_factory", param_names)

        assigns_factory = False
        for node in ast.walk(init_fn):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if (
                        isinstance(target, ast.Attribute)
                        and isinstance(target.value, ast.Name)
                        and target.value.id == "self"
                        and target.attr == "activity_store_factory"
                    ):
                        assigns_factory = True
        self.assertTrue(assigns_factory)


if __name__ == "__main__":
    unittest.main()
