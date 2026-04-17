import importlib.util
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch


_SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

_SPEC = importlib.util.spec_from_file_location("qfit_package_plugin", _SCRIPTS_DIR / "package_plugin.py")
if _SPEC is None:
    raise RuntimeError(f"Could not locate package_plugin.py at {_SCRIPTS_DIR}")
package_plugin = importlib.util.module_from_spec(_SPEC)
if _SPEC.loader is None:
    raise RuntimeError("package_plugin.py spec has no loader")
_SPEC.loader.exec_module(package_plugin)


class PackagePluginTests(unittest.TestCase):
    def test_should_include_excludes_packaging_noise_directories(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            keep = root / "qfit_dockwidget.py"
            ignored = [
                root / "tests" / "test_example.py",
                root / ".pytest_cache" / "v" / "cache" / "nodeids",
                root / ".venv" / "lib" / "python3.12" / "site-packages" / "sample.py",
                root / "validation" / "sample.txt",
                root / "validation_artifacts" / "artifact.txt",
            ]
            keep.parent.mkdir(parents=True, exist_ok=True)
            keep.write_text("# keep\n", encoding="utf-8")
            for path in ignored:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("ignore\n", encoding="utf-8")

            with patch.object(package_plugin, "ROOT", root):
                self.assertTrue(package_plugin.should_include(keep))
                for path in ignored:
                    self.assertFalse(package_plugin.should_include(path), path)

    def test_build_zip_omits_tests_and_validation_artifacts(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "src"
            dist = Path(temp_dir) / "dist"
            root.mkdir()
            (root / "metadata.txt").write_text("[general]\nname=qfit\nversion=1.2.3\n", encoding="utf-8")
            (root / "__init__.py").write_text("# init\n", encoding="utf-8")
            (root / "core.py").write_text("# plugin\n", encoding="utf-8")
            (root / "tests").mkdir()
            (root / "tests" / "test_core.py").write_text("# test\n", encoding="utf-8")
            (root / ".pytest_cache").mkdir()
            (root / ".pytest_cache" / "README.md").write_text("cache\n", encoding="utf-8")
            (root / ".venv" / "lib" / "python3.12" / "site-packages").mkdir(parents=True)
            (root / ".venv" / "lib" / "python3.12" / "site-packages" / "sample.py").write_text("# venv\n", encoding="utf-8")
            (root / "validation").mkdir()
            (root / "validation" / "sample.txt").write_text("validation\n", encoding="utf-8")
            (root / "validation_artifacts").mkdir()
            (root / "validation_artifacts" / "artifact.txt").write_text("artifact\n", encoding="utf-8")

            with (
                patch.object(package_plugin, "ROOT", root),
                patch.object(package_plugin, "DIST_DIR", dist),
                patch.object(package_plugin, "_vendor_runtime_dependencies"),
            ):
                archive_path = package_plugin.build_zip()

            self.assertEqual(archive_path, dist / "qfit-1.2.3.zip")
            with zipfile.ZipFile(archive_path) as archive:
                names = set(archive.namelist())

            self.assertIn("qfit/metadata.txt", names)
            self.assertIn("qfit/__init__.py", names)
            self.assertIn("qfit/core.py", names)
            self.assertFalse(any(name.startswith("qfit/tests/") for name in names))
            self.assertFalse(any(name.startswith("qfit/.pytest_cache/") for name in names))
            self.assertFalse(any(name.startswith("qfit/.venv/") for name in names))
            self.assertFalse(any(name.startswith("qfit/validation/") for name in names))
            self.assertFalse(any(name.startswith("qfit/validation_artifacts/") for name in names))


if __name__ == "__main__":
    unittest.main()
