from __future__ import annotations

import math

PAGES_PER_MINUTE = 150
KB_PER_PAGE = 28


def estimate_time_min(page_count: int) -> int:
    """Return the estimated atlas export duration in whole minutes."""

    return max(1, _round_half_up(_normalise_page_count(page_count) / PAGES_PER_MINUTE))


def estimate_size_mb(page_count: int) -> float:
    """Return the estimated atlas PDF size in megabytes."""

    page_count = _normalise_page_count(page_count)
    if page_count == 0:
        return 0.0
    return max(0.1, round(page_count * KB_PER_PAGE / 1024, 1))


def _normalise_page_count(page_count: int) -> int:
    return max(0, int(page_count))


def _round_half_up(value: float) -> int:
    return math.floor(value + 0.5)
