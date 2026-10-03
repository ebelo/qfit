"""Sanity checks for GitHub Actions workflow files."""

import configparser
import hashlib
import importlib.util
import os
import pathlib
import shutil
import subprocess
import tempfile
import types
import unittest
import zipfile
from importlib import metadata
from unittest.mock import patch

import yaml

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

    def test_builds_and_uploads_qgis_major_packages(self):
        self.assertIn("scripts/package_plugin.py --qgis-major 3", self.text)
        self.assertIn("scripts/package_plugin.py --qgis-major 4", self.text)
        self.assertIn("dist/*-qgis*.zip", self.text)


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

    def test_releases_qgis_major_packages(self):
        self.assertIn("scripts/package_plugin.py --qgis-major 3", self.text)
        self.assertIn("scripts/package_plugin.py --qgis-major 4", self.text)
        self.assertIn("dist/*-qgis*.zip", self.text)

    def test_release_checksum_generation_and_attachment(self):
        if os.name == "nt" or not all(shutil.which(tool) for tool in ("bash", "sha256sum")):
            self.skipTest("Release shell integration needs Linux/WSL with bash and sha256sum")
        steps = yaml.safe_load(self.text)["jobs"]["release"]["steps"]
        checksum_step = next(step for step in steps if step["name"] == "Generate ZIP checksums")
        release_step = next(step for step in steps if step["name"] == "Create GitHub Release")
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            dist = root / "dist"
            dist.mkdir()
            packages = {
                f"qfit-1.2.3-qgis{major}.zip": f"package {major}".encode()
                for major in (3, 4)
            }
            for name, payload in packages.items():
                (dist / name).write_bytes(payload)
            env = {**os.environ, "GITHUB_REF_NAME": "v1.2.3"}
            subprocess.run(
                ["bash", "-e", "-o", "pipefail", "-c", checksum_step["run"]],
                cwd=root, env=env, check=True, capture_output=True,
            )
            manifest = dist / "qfit-1.2.3-SHA256SUMS.txt"
            actual = dict(line.split("  ", 1)[::-1] for line in manifest.read_text().splitlines())
            expected = {name: hashlib.sha256(payload).hexdigest() for name, payload in packages.items()}
            self.assertEqual(actual, expected)
            subprocess.run(
                ["sha256sum", "--check", manifest.name],
                cwd=dist, check=True, capture_output=True,
            )
            bin_dir = root / "bin"
            bin_dir.mkdir()
            gh_stub = bin_dir / "gh"
            gh_stub.write_text('#!/bin/sh\nprintf "%s\\n" "$@" > "$CAPTURED_ARGS"\n')
            gh_stub.chmod(0o755)
            captured = root / "release-args.txt"
            env.update(PATH=f"{bin_dir}{os.pathsep}{env['PATH']}", CAPTURED_ARGS=str(captured))
            command = release_step["run"].replace("${{ github.ref_name }}", "v1.2.3")
            subprocess.run(
                ["bash", "-e", "-o", "pipefail", "-c", command],
                cwd=root, env=env, check=True, capture_output=True,
            )
            args = captured.read_text().splitlines()
            self.assertEqual(args[:3], ["release", "create", "v1.2.3"])
            self.assertIn("--draft", args)
            self.assertEqual(
                {arg for arg in args if arg.startswith("dist/")},
                {f"dist/{name}" for name in packages} | {f"dist/{manifest.name}"},
            )


class TestsWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.text = _read_workflow("tests.yml")

    def test_docker_jobs_use_the_verified_open_font_images(self):
        self.assertEqual(self.text.count("QFIT_REQUIRE_OPEN_FONTS=1"), 2)
        for version in ("3.44.11", "4.2.0"):
            self.assertIn(f"--build-arg QGIS_IMAGE=qgis/qgis:{version}", self.text)
            self.assertIn(f"-t qfit/qgis:{version}-fonts scripts/docker", self.text)
            self.assertIn(f"qfit/qgis:{version}-fonts\n", self.text)

    def test_unit_job_uses_pytest(self):
        self.assertIn("python -m pip install --upgrade pytest", self.text)
        self.assertIn("python -m pytest tests/ -x -q --tb=short", self.text)

    def test_docker_jobs_run_qgis_runtime_suite(self):
        self.assertIn("qgis/qgis:3.44.11", self.text)
        self.assertIn("qgis/qgis:4.2.0", self.text)
        self.assertIn("QFIT_REQUIRE_QGIS=1", self.text)
        self.assertIn("REAL_QGIS_TESTS", self.text)
        self.assertEqual(self.text.count("${REAL_QGIS_TESTS}"), 2)
        self.assertIn("tests/test_qgis_smoke.py", self.text)
        self.assertIn("tests/test_qt6_class_enum_probe.py", self.text)
        self.assertIn("tests/test_gpkg_schema.py", self.text)
        self.assertIn("tests/test_layer_style_service.py", self.text)


class PluginSecurityScanWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.text = _read_workflow("plugin-security-scan.yml")

    def test_scans_both_qgis_major_packages(self):
        self.assertIn("--qgis-major 3", self.text)
        self.assertIn("--qgis-major 4", self.text)
        self.assertIn("debug/plugin-security-scan/qgis3", self.text)
        self.assertIn("debug/plugin-security-scan/qgis4", self.text)


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

    def test_build_zip_vendors_runtime_dependencies_into_plugin_archive(self):
        """The plugin ZIP should include PDF and FIT runtime dependencies."""
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
        self.assertIn("qfit/vendor/fitdecode/__init__.py", names)
        self.assertIn("qfit/vendor/licenses/fitdecode_LICENSE.txt", names)

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
