import tempfile
import unittest

from pathlib import Path
from unittest.mock import patch

from tests import _path  # noqa: F401
from qfit.validation import qgis_import_compat_probe as probe
from qfit.validation.qgis_import_compat_probe import (
    collect_eager_qgis_imports,
    main,
    parse_args,
    render_report,
)


class QgisImportCompatProbeTests(unittest.TestCase):
    def test_collects_only_module_scope_qgis_imports_from_packaged_code(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "plugin.py").write_text(
                "from qgis.PyQt.QtCore import QDate, Qt\n"
                "\n"
                "def later():\n"
                "    from qgis.core import QgsProject\n"
                "    return QgsProject\n",
                encoding="utf-8",
            )
            (root / "tests").mkdir()
            (root / "tests" / "test_plugin.py").write_text(
                "from qgis.core import QgsApplication\n",
                encoding="utf-8",
            )

            refs = collect_eager_qgis_imports(root)

        self.assertEqual(len(refs), 1)
        self.assertEqual(refs[0].relative_path, "plugin.py")
        self.assertEqual(refs[0].line, 1)
        self.assertEqual(refs[0].module, "qgis.PyQt.QtCore")
        self.assertEqual(refs[0].names, ("QDate", "Qt"))

    def test_collects_imports_when_match_node_is_unavailable(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "plugin.py").write_text(
                "class PluginClass:\n"
                "    from qgis.gui import QgsFileWidget\n",
                encoding="utf-8",
            )

            with patch.object(probe, "MATCH_NODE", None):
                refs = collect_eager_qgis_imports(root)

        self.assertEqual(len(refs), 1)
        self.assertEqual(refs[0].module, "qgis.gui")
        self.assertEqual(refs[0].names, ("QgsFileWidget",))

    def test_collects_guarded_module_scope_qgis_imports(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "plugin.py").write_text(
                "try:\n"
                "    from qgis.core import QgsProject\n"
                "except ImportError:\n"
                "    from qgis.PyQt.QtCore import QVariant\n"
                "if True:\n"
                "    import qgis.gui\n"
                "for item in []:\n"
                "    from qgis.PyQt.QtGui import QColor\n"
                "match 1:\n"
                "    case 1:\n"
                "        from qgis.PyQt.QtWidgets import QWidget\n"
                "class PluginClass:\n"
                "    from qgis.gui import QgsFileWidget\n",
                encoding="utf-8",
            )

            refs = collect_eager_qgis_imports(root)

        modules = {ref.module for ref in refs}
        self.assertEqual(
            modules,
            {
                "qgis.core",
                "qgis.PyQt.QtCore",
                "import",
                "qgis.PyQt.QtGui",
                "qgis.PyQt.QtWidgets",
                "qgis.gui",
            },
        )

    def test_report_explains_package_time_failure_mode(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "plugin.py").write_text(
                "from qgis.core import QgsApplication\n",
                encoding="utf-8",
            )

            report = render_report(collect_eager_qgis_imports(root))

        self.assertIn("Packaged Python modules with eager qgis imports: 1", report)
        self.assertIn("line 1: qgis.core -> QgsApplication", report)
        self.assertIn("Runtime branching cannot protect module-scope imports", report)

    def test_parse_args_accepts_custom_root(self):
        args = parse_args(["--root", "/tmp/qfit-probe-root"])

        self.assertEqual(args.root, Path("/tmp/qfit-probe-root"))

    def test_main_prints_report(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "plugin.py").write_text(
                "from qgis.core import QgsApplication\n",
                encoding="utf-8",
            )

            with patch("builtins.print") as mock_print:
                result = main(["--root", str(root)])

        self.assertEqual(result, 0)
        printed_report = mock_print.call_args.args[0]
        self.assertIn("line 1: qgis.core -> QgsApplication", printed_report)


if __name__ == "__main__":
    unittest.main()
