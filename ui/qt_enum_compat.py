from __future__ import annotations


def qt_enum_value(qt, enum_name: str, member_name: str):
    """Return a Qt enum value across Qt 5 flat and Qt 6 nested enum APIs."""

    direct_value = getattr(qt, member_name, None)
    if direct_value is not None:
        return direct_value

    enum_type = getattr(qt, enum_name, None)
    enum_value = getattr(enum_type, member_name, None) if enum_type is not None else None
    if enum_value is not None:
        return enum_value

    msg = f"Qt has neither {member_name!r} nor {enum_name}.{member_name!r}"
    raise AttributeError(msg)


def optional_qt_enum_value(qt, enum_name: str, member_name: str):
    try:
        return qt_enum_value(qt, enum_name, member_name)
    except AttributeError:
        return None


__all__ = ["optional_qt_enum_value", "qt_enum_value"]
