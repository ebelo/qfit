"""Single source of truth for activity type classification.

All modules that need to classify, normalise, or compare activity types
(filtering, styling, export, pace/speed selection) should use the helpers
here instead of defining their own normalization or family-mapping logic.
"""
from __future__ import annotations

import re

# Resolution order matters: first matching family wins.
_FAMILY_TOKENS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("machine",  ("virtual", "trainer", "commute", "ebike", "machine")),
    ("winter",   ("ski", "snow", "sled")),
    ("water",    ("swim", "surf", "paddle", "row", "kayak", "canoe", "sup")),
    ("mountain", ("iceclimb", "climb", "mountain", "boulder", "alpinism")),
    ("running",  ("run", "jog")),
    ("walking",  ("walk", "hike", "trek", "backpack")),
    ("fitness",  ("crossfit", "workout", "yoga", "weight", "gym", "pilates")),
    ("cycling",  ("ride", "bike", "cycle")),
)


def normalize_activity_type(value: object) -> str:
    """Lowercase and strip non-alphanumeric characters from an activity type string.

    This is the canonical normalization used across filtering, styling, and
    classification.  ``'TrailRun'``, ``'Trail Run'``, and ``'trail-run'``
    all normalise to ``'trailrun'``.
    """
    text = str(value or "").strip().casefold()
    return re.sub(r"[^a-z0-9]+", "", text)


def canonical_activity_label(
    activity_type: str | None,
    sport_type: str | None,
) -> str | None:
    """Return the canonical label for an activity.

    Prefers the more-specific ``sport_type`` when set, otherwise falls back to
    ``activity_type``.  Returns ``None`` when both are absent.

    This is the agreed field-priority contract used by filtering, the UI
    combo-box, and map styling.
    """
    return sport_type or activity_type or None


def resolve_activity_family(activity_value: object) -> str:
    """Map an activity type value to a broad semantic family name.

    Returns one of: ``machine``, ``winter``, ``water``, ``mountain``,
    ``running``, ``walking``, ``fitness``, ``cycling``.
    Unknown or empty types default to ``machine``.
    """
    normalized = normalize_activity_type(activity_value)
    if not normalized:
        return "machine"
    for family, tokens in _FAMILY_TOKENS:
        if any(token in normalized for token in tokens):
            return family
    return "machine"


def activity_prefers_pace(
    activity_type: str | None,
    sport_type: str | None = None,
) -> bool:
    """Return True when the activity should display pace (min/km) over speed (km/h).

    Running, walking, and hiking activities prefer pace; all others use speed.
    The canonical label (``sport_type`` preferred) is used for the check.
    """
    label = canonical_activity_label(activity_type, sport_type) or ""
    normalized = normalize_activity_type(label)
    return any(token in normalized for token in ("run", "walk", "hike"))
