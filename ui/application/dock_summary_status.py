from __future__ import annotations


def build_dock_summary_status(
    *,
    connection_status: str | None,
    activity_summary: str | None,
    query_summary: str | None,
    workflow_status: str | None,
) -> str:
    """Build the compact dock-wide status summary shown near the footer."""

    parts = []
    seen = set()
    for value in (connection_status, activity_summary, query_summary, workflow_status):
        part = (value or "").strip()
        if not part or part in seen:
            continue
        parts.append(part)
        seen.add(part)

    if not parts:
        return "Ready"
    return " · ".join(parts)
