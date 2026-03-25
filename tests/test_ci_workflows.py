"""Sanity checks for GitHub Actions workflow files."""

import pathlib
import unittest

import yaml

WORKFLOWS_DIR = pathlib.Path(__file__).resolve().parents[1] / ".github" / "workflows"


def _load_workflow(name: str) -> dict:
    path = WORKFLOWS_DIR / name
    with open(path) as fh:
        data = yaml.safe_load(fh)
    # PyYAML parses bare `on:` as boolean True; normalize to the string key.
    if True in data and "on" not in data:
        data["on"] = data.pop(True)
    return data


class BuildWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.wf = _load_workflow("build.yml")

    def test_triggers_on_push_to_main(self):
        self.assertIn("main", self.wf["on"]["push"]["branches"])

    def test_uploads_artifact(self):
        steps = self.wf["jobs"]["build"]["steps"]
        upload_steps = [s for s in steps if "upload-artifact" in s.get("uses", "")]
        self.assertEqual(len(upload_steps), 1)

    def test_runs_package_script(self):
        steps = self.wf["jobs"]["build"]["steps"]
        run_texts = " ".join(s.get("run", "") for s in steps)
        self.assertIn("scripts/package_plugin.py", run_texts)


class ReleaseWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.wf = _load_workflow("release.yml")

    def test_triggers_on_version_tags_only(self):
        tags = self.wf["on"]["push"]["tags"]
        self.assertEqual(tags, ["v*"])

    def test_does_not_trigger_on_branches(self):
        self.assertNotIn("branches", self.wf["on"].get("push", {}))

    def test_has_contents_write_permission(self):
        self.assertEqual(self.wf["permissions"]["contents"], "write")

    def test_creates_github_release(self):
        steps = self.wf["jobs"]["release"]["steps"]
        run_texts = " ".join(s.get("run", "") for s in steps)
        self.assertIn("gh release create", run_texts)

    def test_runs_package_script(self):
        steps = self.wf["jobs"]["release"]["steps"]
        run_texts = " ".join(s.get("run", "") for s in steps)
        self.assertIn("scripts/package_plugin.py", run_texts)

    def test_runs_unit_tests_before_packaging(self):
        steps = self.wf["jobs"]["release"]["steps"]
        step_names = [s.get("name", "") for s in steps]
        test_idx = next(i for i, n in enumerate(step_names) if "test" in n.lower())
        build_idx = next(i for i, n in enumerate(step_names) if "build" in n.lower())
        self.assertLess(test_idx, build_idx)


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
