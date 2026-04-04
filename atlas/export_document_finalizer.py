from __future__ import annotations

import logging
import os
from typing import Callable

logger = logging.getLogger(__name__)


def assemble_output_pdf(
    page_paths: list[str],
    output_path: str,
    *,
    cover_path: str | None = None,
    toc_path: str | None = None,
    merge_pdfs_fn: Callable[[list[str], str], None],
) -> None:
    """Assemble front matter and per-page PDFs into the final atlas document."""
    front_pages = [path for path in (cover_path, toc_path) if path]
    all_paths = front_pages + page_paths
    if len(all_paths) == 1:
        os.replace(all_paths[0], output_path)
        return

    merge_pdfs_fn(all_paths, output_path)
    for path in all_paths:
        try:
            os.remove(path)
        except OSError:
            pass


def merge_pdfs(
    page_paths: list[str],
    output_path: str,
    *,
    load_pdf_writer: Callable[[], type],
    warn: Callable[[str], None] | None = None,
) -> None:
    """Merge per-page PDF files into a single multi-page PDF."""
    try:
        pdf_writer_cls = load_pdf_writer()
    except ImportError:
        pdf_writer_cls = None
        warning_fn = warn or logger.warning
        warning_fn("pypdf unavailable during atlas export; falling back to first-page-only PDF")

    if pdf_writer_cls is not None:
        writer = pdf_writer_cls()
        for path in page_paths:
            writer.append(path)
        with open(output_path, "wb") as fout:
            writer.write(fout)
        return

    if page_paths:
        os.replace(page_paths[0], output_path)
