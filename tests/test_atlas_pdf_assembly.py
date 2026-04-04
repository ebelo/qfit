import sys
import unittest
from unittest.mock import MagicMock, mock_open, patch

from tests import _path  # noqa: F401

from qfit.atlas.infrastructure import pdf_assembly
from qfit.atlas.infrastructure.pdf_assembly import AtlasPdfAssembler


class AtlasPdfAssemblerTests(unittest.TestCase):
    def test_assemble_merges_multiple_pages_and_cleans_up_inputs(self):
        merge_calls = []
        remove_calls = []
        assembler = AtlasPdfAssembler(remove_file=lambda path: remove_calls.append(path))
        assembler.merge = lambda pages, out: merge_calls.append((pages, out))

        assembler.assemble(
            ["/tmp/page-1.pdf", "/tmp/page-2.pdf"],
            "/tmp/out.pdf",
            cover_path="/tmp/cover.pdf",
            toc_path="/tmp/toc.pdf",
        )

        self.assertEqual(
            merge_calls,
            [([
                "/tmp/cover.pdf",
                "/tmp/toc.pdf",
                "/tmp/page-1.pdf",
                "/tmp/page-2.pdf",
            ], "/tmp/out.pdf")],
        )
        self.assertEqual(
            remove_calls,
            ["/tmp/cover.pdf", "/tmp/toc.pdf", "/tmp/page-1.pdf", "/tmp/page-2.pdf"],
        )

    def test_assemble_replaces_single_page_without_merge(self):
        replace_calls = []
        assembler = AtlasPdfAssembler(replace_file=lambda src, dst: replace_calls.append((src, dst)))
        assembler.merge = MagicMock()

        assembler.assemble(["/tmp/page-1.pdf"], "/tmp/out.pdf")

        assembler.merge.assert_not_called()
        self.assertEqual(replace_calls, [("/tmp/page-1.pdf", "/tmp/out.pdf")])

    def test_merge_uses_vendored_qfit_pypdf_when_top_level_module_missing(self):
        import builtins
        import types

        calls = []

        class FakeWriter:
            def append(self, path):
                calls.append(("append", path))

            def write(self, handle):
                calls.append(("write", handle))

        vendored_module = types.ModuleType("qfit.pypdf")
        vendored_module.PdfWriter = FakeWriter
        original_import = builtins.__import__

        def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name == "pypdf":
                raise ImportError("missing top-level pypdf")
            return original_import(name, globals, locals, fromlist, level)

        with patch.dict("sys.modules", {"qfit.pypdf": vendored_module}, clear=False), \
             patch("builtins.__import__", side_effect=fake_import), \
             patch("builtins.open", mock_open()):
            AtlasPdfAssembler().merge(["/tmp/one.pdf", "/tmp/two.pdf"], "/tmp/out.pdf")

        self.assertEqual(calls[0], ("append", "/tmp/one.pdf"))
        self.assertEqual(calls[1], ("append", "/tmp/two.pdf"))
        self.assertEqual(calls[2][0], "write")

    def test_load_pdf_writer_prefers_top_level_pypdf(self):
        writer_cls = pdf_assembly.load_pdf_writer()
        self.assertEqual(writer_cls.__name__, "PdfWriter")

    def test_load_pdf_writer_uses_vendor_dir_after_sys_path_injection(self):
        import builtins
        import os
        import types

        original_import = builtins.__import__
        import_calls = {"pypdf": 0}
        fake_module = types.ModuleType("pypdf")

        class FakeWriter:
            pass

        fake_module.PdfWriter = FakeWriter
        sentinel_vendor_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(pdf_assembly.__file__))),
            "vendor",
        )

        def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name == "pypdf":
                import_calls["pypdf"] += 1
                if import_calls["pypdf"] == 1:
                    raise ImportError("missing before vendor path is added")
                if sentinel_vendor_dir in sys.path:
                    return fake_module
            return original_import(name, globals, locals, fromlist, level)

        with patch("os.path.isdir", return_value=True), \
             patch("builtins.__import__", side_effect=fake_import):
            if sentinel_vendor_dir in sys.path:
                sys.path.remove(sentinel_vendor_dir)
            writer_cls = pdf_assembly.load_pdf_writer()

        self.assertIs(writer_cls, FakeWriter)
        self.assertIn(sentinel_vendor_dir, sys.path)

    def test_load_pdf_writer_raises_when_no_pdf_support_is_available(self):
        import builtins

        original_import = builtins.__import__

        def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name in {"pypdf", "qfit.pypdf"}:
                raise ImportError("missing")
            return original_import(name, globals, locals, fromlist, level)

        with patch("os.path.isdir", return_value=False), \
             patch("builtins.__import__", side_effect=fake_import):
            with self.assertRaisesRegex(ImportError, "pypdf is unavailable"):
                pdf_assembly.load_pdf_writer()

    def test_merge_falls_back_to_first_page_when_pypdf_is_unavailable(self):
        replace_calls = []
        warn = MagicMock()
        assembler = AtlasPdfAssembler(
            load_pdf_writer_fn=MagicMock(side_effect=ImportError("missing")),
            warn=warn,
            replace_file=lambda src, dst: replace_calls.append((src, dst)),
        )

        assembler.merge(["/tmp/one.pdf", "/tmp/two.pdf"], "/tmp/out.pdf")

        warn.assert_called_once()
        self.assertEqual(replace_calls, [("/tmp/one.pdf", "/tmp/out.pdf")])


if __name__ == "__main__":
    unittest.main()
