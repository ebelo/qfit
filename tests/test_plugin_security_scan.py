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

_SPEC = importlib.util.spec_from_file_location(
    "qfit_plugin_security_scan", _SCRIPTS_DIR / "run_plugin_security_scan.py"
)
if _SPEC is None:
    raise RuntimeError(f"Could not locate run_plugin_security_scan.py at {_SCRIPTS_DIR}")
plugin_security_scan = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = plugin_security_scan
if _SPEC.loader is None:
    raise RuntimeError("run_plugin_security_scan.py spec has no loader")
_SPEC.loader.exec_module(plugin_security_scan)


class DetectSecretsHelperTests(unittest.TestCase):
    def test_detect_secrets_has_findings_when_results_present(self):
        payload = '{"results": {"plugin.py": [{"type": "Secret Keyword"}]}}'
        self.assertTrue(plugin_security_scan.detect_secrets_has_findings(0, payload))

    def test_detect_secrets_has_findings_is_false_when_results_empty(self):
        payload = '{"results": {}}'
        self.assertFalse(plugin_security_scan.detect_secrets_has_findings(0, payload))


class EvaluateResultsTests(unittest.TestCase):
    def test_evaluate_results_fails_when_findings_not_allowed(self):
        result = plugin_security_scan.ScanResult(
            name="bandit",
            command=("bandit",),
            report_path=Path("bandit.json"),
            stderr_path=Path("bandit.stderr.txt"),
            exit_code=1,
            has_findings=True,
        )
        self.assertEqual(
            plugin_security_scan.evaluate_results([result], allow_findings=False),
            1,
        )

    def test_evaluate_results_allows_findings_when_requested(self):
        result = plugin_security_scan.ScanResult(
            name="bandit",
            command=("bandit",),
            report_path=Path("bandit.json"),
            stderr_path=Path("bandit.stderr.txt"),
            exit_code=1,
            has_findings=True,
        )
        self.assertEqual(
            plugin_security_scan.evaluate_results([result], allow_findings=True),
            0,
        )

    def test_evaluate_results_detects_execution_errors(self):
        result = plugin_security_scan.ScanResult(
            name="flake8",
            command=("flake8",),
            report_path=Path("flake8.txt"),
            stderr_path=Path("flake8.stderr.txt"),
            exit_code=127,
            has_findings=False,
        )
        self.assertEqual(
            plugin_security_scan.evaluate_results([result], allow_findings=True),
            2,
        )


class PrepareScanTreeTests(unittest.TestCase):
    def test_prepare_scan_tree_extracts_single_plugin_root(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            archive_path = temp_path / "qfit-1.2.3.zip"
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("qfit/__init__.py", "# plugin\n")
                archive.writestr("qfit/metadata.txt", "[general]\nname=qfit\n")

            reports_dir = temp_path / "debug" / "plugin-security-scan"
            original_build_zip = plugin_security_scan.package_plugin.build_zip
            plugin_security_scan.package_plugin.build_zip = lambda: archive_path
            try:
                built_archive, plugin_root = plugin_security_scan.prepare_scan_tree(reports_dir)
            finally:
                plugin_security_scan.package_plugin.build_zip = original_build_zip

            self.assertEqual(built_archive, archive_path)
            self.assertEqual(plugin_root, reports_dir / "extracted" / "qfit")
            self.assertTrue((plugin_root / "metadata.txt").exists())

    def test_prepare_scan_tree_removes_stale_reports_before_packaging(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            archive_path = temp_path / "qfit-1.2.3.zip"
            reports_dir = temp_path / "debug" / "plugin-security-scan"
            reports_dir.mkdir(parents=True)
            stale_report = reports_dir / "summary.txt"
            stale_report.write_text("old\n", encoding="utf-8")

            def fake_build_zip():
                self.assertFalse(stale_report.exists())
                with zipfile.ZipFile(archive_path, "w") as archive:
                    archive.writestr("qfit/__init__.py", "# plugin\n")
                    archive.writestr("qfit/metadata.txt", "[general]\nname=qfit\n")
                return archive_path

            with patch.object(plugin_security_scan.package_plugin, "build_zip", side_effect=fake_build_zip):
                built_archive, plugin_root = plugin_security_scan.prepare_scan_tree(reports_dir)

            self.assertEqual(built_archive, archive_path)
            self.assertEqual(plugin_root, reports_dir / "extracted" / "qfit")
            self.assertFalse(stale_report.exists())


class BuildScanCommandsTests(unittest.TestCase):
    def test_flake8_command_excludes_vendor_tree(self):
        commands = plugin_security_scan.build_scan_commands(
            Path("/tmp/plugin-root"),
            Path("/tmp/reports"),
        )

        flake8_entry = next(command for command in commands if command[0] == "flake8")
        self.assertIn("--extend-exclude=vendor/", flake8_entry[1])


if __name__ == "__main__":
    unittest.main()
