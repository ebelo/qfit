"""Sanity checks for GitHub Actions workflow files."""

import pathlib
import unittest

WORKFLOWS_DIR = pathlib.Path(__file__).resolve().parents[1] / ".github" / "workflows"


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


class PackageScriptTests(unittest.TestCase):
    def test_script_exists(self):
        script = WORKFLOWS_DIR.parents[1] / "scripts" / "package_plugin.py"
        self.assertTrue(script.exists(), "scripts/package_plugin.py must exist")

    def test_script_is_importable(self):
        """Verify the packaging module can be imported without side effects."""
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "package_plugin",
            WORKFLOWS_DIR.parents[1] / "scripts" / "package_plugin.py",
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        self.assertTrue(callable(mod.build_zip))


if __name__ == "__main__":
    unittest.main()
