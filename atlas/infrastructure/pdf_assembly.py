from __future__ import annotations

import logging
import os
import sys
from typing import Callable

logger = logging.getLogger(__name__)


class AtlasPdfAssemblyCancelled(Exception):
    """Raised when cooperative cancellation interrupts PDF assembly."""


def load_pdf_writer():
    """Return :class:`pypdf.PdfWriter`, preferring bundled plugin vendoring.

    Resolution order:

    1. top-level ``pypdf`` from the current Python environment
    2. vendored ``qfit/vendor/pypdf`` packaged inside the plugin zip
    3. legacy/manual ``qfit.pypdf`` fallback used during ad-hoc debugging
    """

    try:
        import pypdf as _pypdf_module  # noqa: PLC0415

        return _pypdf_module.PdfWriter
    except ImportError:
        pass

    plugin_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    vendor_dir = os.path.join(plugin_root, "vendor")
    if os.path.isdir(vendor_dir) and vendor_dir not in sys.path:
        sys.path.insert(0, vendor_dir)

    try:
        import pypdf as _pypdf_module  # noqa: PLC0415

        return _pypdf_module.PdfWriter
    except ImportError:
        pass

    try:
        import qfit.pypdf as _vendored_pypdf_module  # noqa: PLC0415

        return _vendored_pypdf_module.PdfWriter
    except ImportError as exc:
        raise ImportError("pypdf is unavailable for atlas PDF merging") from exc


class AtlasPdfAssembler:
    """Atlas-owned PDF assembly component for final export document creation."""

    def __init__(
        self,
        *,
        load_pdf_writer_fn: Callable[[], type] = load_pdf_writer,
        warn: Callable[[str], None] | None = None,
        replace_file: Callable[[str, str], None] | None = None,
        remove_file: Callable[[str], None] | None = None,
        open_file: Callable[..., object] | None = None,
        is_canceled: Callable[[], bool] | None = None,
    ):
        self._load_pdf_writer = load_pdf_writer_fn
        self._warn = warn or logger.warning
        self._replace_file = replace_file or os.replace
        self._remove_file = remove_file or os.remove
        self._open_file = open_file or open
        self._is_canceled = is_canceled or (lambda: False)

    def _check_canceled(self) -> None:
        if self._is_canceled():
            raise AtlasPdfAssemblyCancelled()

    def assemble(
        self,
        page_paths: list[str],
        output_path: str,
        *,
        cover_path: str | None = None,
        toc_path: str | None = None,
    ) -> None:
        """Assemble front matter and per-page PDFs into the final atlas document."""

        front_pages = [path for path in (cover_path, toc_path) if path]
        all_paths = front_pages + page_paths
        try:
            self._check_canceled()
            if len(all_paths) == 1:
                self._replace_file(all_paths[0], output_path)
                return

            self.merge(all_paths, output_path)
        finally:
            for path in all_paths:
                try:
                    self._remove_file(path)
                except OSError:
                    pass

    def merge(self, page_paths: list[str], output_path: str) -> None:
        """Merge per-page PDF files into a single multi-page PDF."""

        try:
            pdf_writer_cls = self._load_pdf_writer()
        except ImportError:
            pdf_writer_cls = None
            self._warn("pypdf unavailable during atlas export; falling back to first-page-only PDF")

        if pdf_writer_cls is not None:
            writer = pdf_writer_cls()
            for path in page_paths:
                self._check_canceled()
                writer.append(path)
            self._check_canceled()
            with self._open_file(output_path, "wb") as fout:
                writer.write(fout)
            return

        if page_paths:
            self._check_canceled()
            self._replace_file(page_paths[0], output_path)
