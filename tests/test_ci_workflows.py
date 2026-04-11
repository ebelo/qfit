"""Sanity checks for GitHub Actions workflow files."""

import configparser
import importlib.util
import pathlib
import tempfile
import types
import unittest
import zipfile
from importlib import metadata
from unittest.mock import patch

WORKFLOWS_DIR = pathlib.Path(__file__).resolve().parents[1] / ".github" / "workflows"
METADATA_PATH = WORKFLOWS_DIR.parents[1] / "metadata.txt"


def _read_workflow(name: str) -> str:
    return (WORKFLOWS_DIR / name).read_text()


class BuildWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.text = _read_workflow("build.yml")

    def test_triggers_on_push_to_main(self):
        self.assertIn("branches:", self.text)
        self.assertIn("- main", self.text)

    def test_uploads_artifact(self):
        self.assertIn("actions/upload-artifact@", self.text)

    def test_runs_package_script(self):
        self.assertIn("scripts/package_plugin.py", self.text)


class ReleaseWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.text = _read_workflow("release.yml")

    def test_triggers_on_version_tags_only(self):
        self.assertIn("tags:", self.text)
        self.assertIn("- 'v*'", self.text)

    def test_does_not_trigger_on_branches(self):
        # The on.push section should only have tags, not branches
        lines = self.text.splitlines()
        in_push = False
        for line in lines:
            stripped = line.strip()
            if stripped == "push:":
                in_push = True
            elif in_push and stripped and not stripped.startswith("#"):
                if stripped == "tags:":
                    continue
                if stripped.startswith("- "):
                    continue
                # Any other top-level key means we left the push section
                break
        self.assertNotIn("branches:", self.text.split("tags:")[0].split("push:")[-1]
                         if "push:" in self.text else "")

    def test_has_contents_write_permission(self):
        self.assertIn("contents: write", self.text)

    def test_creates_github_release(self):
        self.assertIn("gh release create", self.text)

    def test_runs_package_script(self):
        self.assertIn("scripts/package_plugin.py", self.text)

    def test_runs_unit_tests(self):
        self.assertIn("unittest discover", self.text)


class MetadataTests(unittest.TestCase):
    def test_metadata_omits_plugin_category(self):
        parser = configparser.ConfigParser()
        parser.read(METADATA_PATH)

        self.assertFalse(parser.has_option("general", "category"))


class PackageScriptTests(unittest.TestCase):
    @staticmethod
    def _load_module():
        spec = importlib.util.spec_from_file_location(
            "package_plugin",
            WORKFLOWS_DIR.parents[1] / "scripts" / "package_plugin.py",
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_script_exists(self):
        script = WORKFLOWS_DIR.parents[1] / "scripts" / "package_plugin.py"
        self.assertTrue(script.exists(), "scripts/package_plugin.py must exist")

    def test_script_is_importable(self):
        """Verify the packaging module can be imported without side effects."""
        mod = self._load_module()
        self.assertTrue(callable(mod.build_zip))

    def test_build_zip_vendors_pypdf_into_plugin_archive(self):
        """The packaged plugin ZIP should be self-contained for atlas PDF export."""
        mod = self._load_module()

        with tempfile.TemporaryDirectory() as tmpdir:
            original_dist_dir = mod.DIST_DIR
            mod.DIST_DIR = pathlib.Path(tmpdir)
            try:
                archive_path = mod.build_zip()
            finally:
                mod.DIST_DIR = original_dist_dir

            with zipfile.ZipFile(archive_path) as archive:
                names = set(archive.namelist())

        self.assertIn("qfit/vendor/pypdf/__init__.py", names)
        self.assertIn("qfit/vendor/licenses/pypdf_LICENSE.txt", names)

    def test_build_zip_excludes_dev_only_artifacts(self):
        mod = self._load_module()

        with tempfile.TemporaryDirectory() as tmpdir:
            original_dist_dir = mod.DIST_DIR
            mod.DIST_DIR = pathlib.Path(tmpdir)
            try:
                archive_path = mod.build_zip()
            finally:
                mod.DIST_DIR = original_dist_dir

            with zipfile.ZipFile(archive_path) as archive:
                names = set(archive.namelist())

        self.assertNotIn("qfit/.coverage", names)
        self.assertNotIn("qfit/.github/workflows/build.yml", names)
        self.assertNotIn("qfit/sonar-project.properties", names)

    def test_resolve_package_dir_raises_when_dependency_missing(self):
        mod = self._load_module()

        with patch.object(mod.importlib.util, "find_spec", return_value=None):
            with self.assertRaisesRegex(RuntimeError, "pip install definitely-missing"):
                mod._resolve_package_dir("definitely-missing")

    def test_resolve_distribution_license_handles_missing_distribution(self):
        mod = self._load_module()

        with patch.object(
            mod.metadata,
            "distribution",
            side_effect=metadata.PackageNotFoundError,
        ):
            self.assertIsNone(mod._resolve_distribution_license("missing-dist"))

    def test_resolve_distribution_license_prefers_nested_licenses_dir(self):
        mod = self._load_module()
        fake_dist = types.SimpleNamespace(
            files=[pathlib.Path("foo"), pathlib.Path("pkg/licenses/LICENSE.txt")],
            locate_file=lambda file: pathlib.Path("/tmp") / file,
        )

        with patch.object(mod.metadata, "distribution", return_value=fake_dist):
            resolved = mod._resolve_distribution_license("pypdf")

        self.assertEqual(resolved, pathlib.Path("/tmp/pkg/licenses/LICENSE.txt").resolve())

    def test_main_prints_built_archive_path(self):
        mod = self._load_module()
        archive_path = pathlib.Path("/tmp/qfit-test.zip")

        with patch.object(mod, "build_zip", return_value=archive_path), \
             patch("builtins.print") as mock_print:
            result = mod.main()

        self.assertEqual(result, 0)
        mock_print.assert_called_once_with(f"Built {archive_path}")


if __name__ == "__main__":
    unittest.main()
