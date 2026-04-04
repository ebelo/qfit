import datetime as dt
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from tests import _path  # noqa: F401

from qfit.validation.atlas_export_harness import (
    DEFAULT_ARTIFACTS_ROOT,
    REPO_ROOT,
    SCENARIOS,
    build_env,
    build_parser,
    build_run_directory,
    list_scenarios,
    main,
    run_scenario,
)


class AtlasExportHarnessTests(unittest.TestCase):
    def test_build_run_directory_uses_predictable_timestamped_layout(self):
        run_dir = build_run_directory(
            artifacts_root=Path("/tmp/qfit-validation"),
            scenario_name="native-profile-final",
            now=dt.datetime(2026, 4, 4, 3, 15, tzinfo=dt.timezone.utc),
        )

        self.assertEqual(
            run_dir,
            Path("/tmp/qfit-validation/native-profile-final/20260404T031500Z"),
        )

    def test_build_env_sets_validation_output_directory(self):
        env = build_env(run_dir=Path("/tmp/qfit-validation/run-1"))

        self.assertEqual(env["QFIT_VALIDATION_OUTPUT_DIR"], "/tmp/qfit-validation/run-1")
        self.assertEqual(env["QFIT_VALIDATION_REPO_ROOT"], str(REPO_ROOT))
        self.assertEqual(env["QT_QPA_PLATFORM"], "offscreen")

    def test_list_scenarios_mentions_curated_entries(self):
        text = list_scenarios()

        self.assertIn("native-profile-final", text)
        self.assertIn("native-profile-renderer", text)

    def test_run_scenario_executes_registered_script_with_expected_env(self):
        scenario = SCENARIOS["native-profile-final"]

        with (
            patch("qfit.validation.atlas_export_harness.build_run_directory", return_value=Path("/tmp/qfit-validation/run-1")),
            patch("pathlib.Path.mkdir") as mkdir_mock,
            patch("subprocess.run") as run_mock,
        ):
            run_mock.return_value.returncode = 0
            result = run_scenario(
                scenario=scenario,
                artifacts_root=DEFAULT_ARTIFACTS_ROOT,
                python_executable="python-qgis",
            )

        self.assertEqual(result, 0)
        mkdir_mock.assert_called_once_with(parents=True, exist_ok=True)
        run_mock.assert_called_once()
        call = run_mock.call_args
        self.assertEqual(call.args[0], ["python-qgis", str(scenario.script_path)])
        self.assertEqual(call.kwargs["cwd"], REPO_ROOT)
        self.assertEqual(call.kwargs["env"]["QFIT_VALIDATION_OUTPUT_DIR"], "/tmp/qfit-validation/run-1")

    def test_main_lists_scenarios(self):
        with patch("builtins.print") as print_mock:
            result = main(["--list"])

        self.assertEqual(result, 0)
        printed = "\n".join(str(call.args[0]) for call in print_mock.call_args_list)
        self.assertIn("native-profile-final", printed)

    def test_main_requires_scenario_without_list(self):
        with self.assertRaises(SystemExit):
            main([])


if __name__ == "__main__":
    unittest.main()
