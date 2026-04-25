from __future__ import annotations


def build_wizard_footer_status(
    *,
    connection_status: str | None,
    activity_summary: str | None,
    map_summary: str | None,
    analysis_status: str | None,
    atlas_status: str | None,
) -> str:
    """Build the compact persistent footer text for the #609 wizard shell.

    The footer deliberately summarizes page-level render facts instead of
    reading current dock widgets. That keeps the wizard replacement path free to
    migrate one page at a time while still giving users the one-glance status
    requested by the #608 UX audit.
    """

    return _join_unique_status_parts(
        connection_status,
        activity_summary,
        map_summary,
        analysis_status,
        atlas_status,
    )


def _join_unique_status_parts(*values: str | None) -> str:
    parts: list[str] = []
    seen: set[str] = set()
    for value in values:
        part = (value or "").strip()
        if not part or part in seen:
            continue
        parts.append(part)
        seen.add(part)

    if not parts:
        return "Ready"
    return " · ".join(parts)


__all__ = ["build_wizard_footer_status"]
