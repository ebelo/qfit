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
    def test_packaged_flake8_config_documents_qgis_import_bootstrap_ignores(self):
        config = package_plugin.PACKAGED_FLAKE8_CONFIG.read_text(encoding="utf-8")

        expected_e402_ignores = (
            "*/activities/application/fetch_task.py: E402",
            "*/activities/infrastructure/geopackage/gpkg_writer.py: E402",
            "*/atlas/export_service.py: E402",
            "*/atlas/export_task.py: E402",
            "*/providers/infrastructure/strava_client.py: E402",
            "qfit_dockwidget.py: E402",
            "*/visualization/infrastructure/background_map_service.py: E402",
            "*/visualization/infrastructure/layer_style_service.py: E402",
            "*/visualization/infrastructure/qgis_layer_gateway.py: E402",
        )

        self.assertIn("per-file-ignores =", config)
        for expected_ignore in expected_e402_ignores:
            self.assertIn(expected_ignore, config)

    def test_should_include_excludes_packaging_noise_directories(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            keep = root / "qfit_dockwidget.py"
            ignored = [
                root / "tests" / "test_example.py",
                root / ".pytest_cache" / "v" / "cache" / "nodeids",
                root / ".venv" / "lib" / "python3.12" / "site-packages" / "sample.py",
                root / "debug" / "plugin-security-scan" / "summary.txt",
                root / "packaging" / "qgis-flake8.cfg",
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
            (root / ".bandit").write_text("[bandit]\n", encoding="utf-8")
            (root / ".flake8").write_text("[flake8]\n", encoding="utf-8")
            (root / "tests").mkdir()
            (root / "tests" / "test_core.py").write_text("# test\n", encoding="utf-8")
            (root / ".pytest_cache").mkdir()
            (root / ".pytest_cache" / "README.md").write_text("cache\n", encoding="utf-8")
            (root / ".venv" / "lib" / "python3.12" / "site-packages").mkdir(parents=True)
            (root / ".venv" / "lib" / "python3.12" / "site-packages" / "sample.py").write_text("# venv\n", encoding="utf-8")
            (root / "debug" / "plugin-security-scan").mkdir(parents=True)
            (root / "debug" / "plugin-security-scan" / "summary.txt").write_text("summary\n", encoding="utf-8")
            (root / "packaging").mkdir()
            packaged_flake8_config = root / "packaging" / "qgis-flake8.cfg"
            packaged_flake8_config.write_text(
                "[flake8]\n"
                "extend-exclude = vendor/*\n"
                "extend-ignore = W503\n"
                "per-file-ignores =\n"
                "    qfit_dockwidget.py: E402\n",
                encoding="utf-8",
            )
            (root / "validation").mkdir()
            (root / "validation" / "sample.txt").write_text("validation\n", encoding="utf-8")
            (root / "validation_artifacts").mkdir()
            (root / "validation_artifacts" / "artifact.txt").write_text("artifact\n", encoding="utf-8")

            with (
                patch.object(package_plugin, "ROOT", root),
                patch.object(package_plugin, "DIST_DIR", dist),
                patch.object(package_plugin, "PACKAGED_FLAKE8_CONFIG", packaged_flake8_config),
                patch.object(package_plugin, "_vendor_runtime_dependencies"),
            ):
                archive_path = package_plugin.build_zip()

            self.assertEqual(archive_path, dist / "qfit-1.2.3.zip")
            with zipfile.ZipFile(archive_path) as archive:
                names = set(archive.namelist())
                packaged_config = archive.read("qfit/.flake8").decode("utf-8")

            self.assertIn("qfit/metadata.txt", names)
            self.assertIn("qfit/__init__.py", names)
            self.assertIn("qfit/core.py", names)
            self.assertIn("qfit/.bandit", names)
            self.assertIn("qfit/.flake8", names)
            self.assertNotIn("qfit/packaging/qgis-flake8.cfg", names)
            self.assertIn("extend-exclude = vendor/*", packaged_config)
            self.assertIn("extend-ignore = W503", packaged_config)
            self.assertIn("qfit_dockwidget.py: E402", packaged_config)
            self.assertFalse(any(name.startswith("qfit/tests/") for name in names))
            self.assertFalse(any(name.startswith("qfit/.pytest_cache/") for name in names))
            self.assertFalse(any(name.startswith("qfit/.venv/") for name in names))
            self.assertFalse(any(name.startswith("qfit/debug/") for name in names))
            self.assertFalse(any(name.startswith("qfit/validation/") for name in names))
            self.assertFalse(any(name.startswith("qfit/validation_artifacts/") for name in names))

    def test_build_zip_fails_when_packaged_flake8_config_is_missing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "src"
            dist = Path(temp_dir) / "dist"
            root.mkdir()
            (root / "metadata.txt").write_text("[general]\nname=qfit\nversion=1.2.3\n", encoding="utf-8")
            (root / "__init__.py").write_text("# init\n", encoding="utf-8")

            with (
                patch.object(package_plugin, "ROOT", root),
                patch.object(package_plugin, "DIST_DIR", dist),
                patch.object(package_plugin, "PACKAGED_FLAKE8_CONFIG", root / "missing-flake8.cfg"),
                patch.object(package_plugin, "_vendor_runtime_dependencies"),
            ):
                with self.assertRaisesRegex(RuntimeError, "Packaged Flake8 config not found"):
                    package_plugin.build_zip()


if __name__ == "__main__":
    unittest.main()
