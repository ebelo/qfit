from __future__ import annotations


def update_local_first_atlas_document_settings(
    dock,
    atlas_title: str,
    atlas_subtitle: str,
) -> None:
    """Mirror local-first atlas document fields into export backing widgets.

    The visible local-first Atlas page owns the user-facing title and subtitle
    fields. During dock consolidation, the legacy export widgets remain the
    persistence/export backing controls, so keep this mirroring policy in the
    local-first application layer instead of embedding it in QfitDockWidget.
    """

    title_line_edit = getattr(dock, "atlasTitleLineEdit", None)
    subtitle_line_edit = getattr(dock, "atlasSubtitleLineEdit", None)
    title_changed = (
        title_line_edit is not None and title_line_edit.text() != atlas_title
    )
    subtitle_changed = (
        subtitle_line_edit is not None
        and subtitle_line_edit.text() != atlas_subtitle
    )
    if title_line_edit is not None:
        title_line_edit.setText(atlas_title)
    if subtitle_line_edit is not None:
        subtitle_line_edit.setText(atlas_subtitle)
    if title_changed or subtitle_changed:
        dock._mark_atlas_export_stale()
        dock._refresh_summary_status()


__all__ = ["update_local_first_atlas_document_settings"]
