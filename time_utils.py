from datetime import datetime, timedelta
from typing import Optional, Union

DateLike = Union[str, datetime, None]


def parse_iso_datetime(value: DateLike) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value

    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def format_iso_datetime(value: Optional[datetime]) -> Optional[str]:
    if value is None:
        return None
    text = value.isoformat()
    if text.endswith("+00:00"):
        return text[:-6] + "Z"
    return text


def add_seconds_iso(value: DateLike, seconds) -> Optional[str]:
    if value is None or seconds is None:
        return None
    base = parse_iso_datetime(value)
    if base is None:
        return None
    try:
        delta_seconds = int(seconds)
    except (TypeError, ValueError):
        return None
    return format_iso_datetime(base + timedelta(seconds=delta_seconds))
