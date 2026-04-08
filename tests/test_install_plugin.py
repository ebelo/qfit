import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch


_SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

_SPEC = importlib.util.spec_from_file_location("qfit_install_plugin", _SCRIPTS_DIR / "install_plugin.py")
install_plugin = importlib.util.module_from_spec(_SPEC)
assert _SPEC.loader is not None
_SPEC.loader.exec_module(install_plugin)


class InstallPluginTests(unittest.TestCase):
    def test_parse_args_defaults_to_copy_mode(self):
        with patch.object(sys, "argv", ["install_plugin.py"]):
            args = install_plugin.parse_args()

        self.assertEqual(args.mode, "copy")
        self.assertEqual(args.profile, "default")

    def test_install_copy_vendors_runtime_dependencies(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "src"
            destination = Path(temp_dir) / "dest"
            root.mkdir()
            (root / "metadata.txt").write_text("name=qfit\n", encoding="utf-8")
            (root / "atlas").mkdir()
            (root / "atlas" / "export_task.py").write_text("# atlas\n", encoding="utf-8")

            with patch.object(install_plugin, "ROOT", root), patch.object(
                install_plugin, "_vendor_runtime_dependencies"
            ) as vendor_runtime_dependencies:
                install_plugin.install_copy(destination)

            self.assertTrue((destination / "metadata.txt").exists())
            self.assertTrue((destination / "atlas" / "export_task.py").exists())
            vendor_runtime_dependencies.assert_called_once_with(destination)

    def test_main_falls_back_to_symlink_when_copy_mode_cannot_vendor_dependencies(self):
        plugins_dir = Path("/tmp/qgis-plugins")
        destination = plugins_dir / install_plugin.PLUGIN_NAME
        args = SimpleNamespace(profile="default", mode="copy", plugins_dir=None, remove=False)

        with patch.object(install_plugin, "parse_args", return_value=args), patch.object(
            install_plugin, "default_plugins_dir", return_value=plugins_dir
        ), patch.object(install_plugin, "install_copy", side_effect=RuntimeError("missing pypdf dist")), patch.object(
            install_plugin, "install_symlink"
        ) as install_symlink, patch("builtins.print") as mock_print:
            exit_code = install_plugin.main()

        self.assertEqual(exit_code, 0)
        install_symlink.assert_called_once_with(destination)
        mock_print.assert_any_call(
            "Warning: copy mode could not vendor runtime-only Python dependencies "
            "(missing pypdf dist). Falling back to symlink mode."
        )
        mock_print.assert_any_call(f"Installed {install_plugin.PLUGIN_NAME} to {destination} using mode=symlink")
        mock_print.assert_any_call(
            "Warning: symlink mode does not vendor runtime-only Python dependencies like pypdf. "
            "Use --mode copy or the packaged plugin zip when you need atlas PDF export."
        )

    def test_main_warns_when_symlink_mode_skips_runtime_dependencies(self):
        plugins_dir = Path("/tmp/qgis-plugins")
        destination = plugins_dir / install_plugin.PLUGIN_NAME
        args = SimpleNamespace(profile="default", mode="symlink", plugins_dir=None, remove=False)

        with patch.object(install_plugin, "parse_args", return_value=args), patch.object(
            install_plugin, "default_plugins_dir", return_value=plugins_dir
        ), patch.object(install_plugin, "install_symlink") as install_symlink, patch(
            "builtins.print"
        ) as mock_print:
            exit_code = install_plugin.main()

        self.assertEqual(exit_code, 0)
        install_symlink.assert_called_once_with(destination)
        mock_print.assert_any_call(f"Installed {install_plugin.PLUGIN_NAME} to {destination} using mode=symlink")
        mock_print.assert_any_call(
            "Warning: symlink mode does not vendor runtime-only Python dependencies like pypdf. "
            "Use --mode copy or the packaged plugin zip when you need atlas PDF export."
        )


if __name__ == "__main__":
    unittest.main()
