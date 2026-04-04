import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests import _path  # noqa: F401

from qfit.validation import scenario_env


class ValidationScenarioEnvTests(unittest.TestCase):
    def test_resolve_repo_root_prefers_environment_override(self):
        with patch.dict(os.environ, {"QFIT_VALIDATION_REPO_ROOT": "/tmp/custom-repo"}, clear=False):
            self.assertEqual(scenario_env.resolve_repo_root(), Path("/tmp/custom-repo"))

    def test_ensure_repo_import_path_inserts_repo_parent(self):
        with patch("qfit.validation.scenario_env.resolve_repo_root", return_value=Path("/tmp/repo/qfit")):
            original = list(sys.path)
            try:
                scenario_env.ensure_repo_import_path()
                self.assertEqual(sys.path[0], "/tmp/repo")
            finally:
                sys.path[:] = original

    def test_resolve_artifacts_dir_uses_output_override_and_creates_it(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            target = Path(tmpdir) / "artifacts" / "run-1"
            with patch.dict(os.environ, {"QFIT_VALIDATION_OUTPUT_DIR": str(target)}, clear=False):
                resolved = scenario_env.resolve_artifacts_dir()

            self.assertEqual(resolved, target)
            self.assertTrue(target.exists())

    def test_resolve_source_gpkg_uses_override(self):
        with patch.dict(os.environ, {"QFIT_VALIDATION_SOURCE_GPKG": "/tmp/source.gpkg"}, clear=False):
            self.assertEqual(scenario_env.resolve_source_gpkg(), Path("/tmp/source.gpkg"))

    def test_resolve_reference_artifact_uses_repo_validation_artifacts_dir(self):
        with patch("qfit.validation.scenario_env.resolve_repo_root", return_value=Path("/tmp/repo/qfit")):
            self.assertEqual(
                scenario_env.resolve_reference_artifact("proof.pdf"),
                Path("/tmp/repo/qfit/validation_artifacts/proof.pdf"),
            )


if __name__ == "__main__":
    unittest.main()
