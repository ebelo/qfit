from __future__ import annotations

PAGES_PER_MINUTE = 150
KB_PER_PAGE = 28


def estimate_time_min(page_count: int) -> int:
    """Return the estimated atlas export duration in whole minutes."""

    return max(1, round(_normalise_page_count(page_count) / PAGES_PER_MINUTE))


def estimate_size_mb(page_count: int) -> float:
    """Return the estimated atlas PDF size in megabytes."""

    return round(_normalise_page_count(page_count) * KB_PER_PAGE / 1024, 1)


def _normalise_page_count(page_count: int) -> int:
    return max(0, int(page_count))
