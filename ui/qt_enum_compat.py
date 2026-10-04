from __future__ import annotations


def qt_enum_value(qt, enum_name: str, member_name: str):
    """Return a Qt enum value across Qt 5 flat and Qt 6 nested enum APIs.

    Uses ``is not None`` rather than truthiness so that zero-valued enum
    members (e.g. ``QDockWidget.NoDockWidgetFeatures = 0``) are returned
    correctly rather than falling through to the nested lookup.
    """

    direct_value = getattr(qt, member_name, None)
    if direct_value is not None:
        return direct_value

    enum_type = getattr(qt, enum_name, None)
    enum_value = getattr(enum_type, member_name, None) if enum_type is not None else None
    if enum_value is not None:
        return enum_value

    msg = f"Qt has neither {member_name!r} nor {enum_name}.{member_name!r}"
    raise AttributeError(msg)


def qt_class_enum_value(cls, enum_name: str, member_name: str):
    """Return a Qt enum value from a class across Qt 5 flat and Qt 6 nested APIs.

    Qt 5 exposes ``QDockWidget.DockWidgetClosable`` as a flat attribute.
    Qt 6 nests it under ``QDockWidget.DockWidgetFeature.DockWidgetClosable``.
    This helper resolves both shapes so class-body expressions work on either Qt version.

    Uses ``is not None`` rather than truthiness so that zero-valued enum
    members (e.g. ``QDockWidget.NoDockWidgetFeatures = 0``) are returned
    correctly rather than falling through to the nested lookup.
    """
    direct_value = getattr(cls, member_name, None)
    if direct_value is not None:
        return direct_value

    enum_type = getattr(cls, enum_name, None)
    enum_value = getattr(enum_type, member_name, None) if enum_type is not None else None
    if enum_value is not None:
        return enum_value

    msg = (
        f"{cls.__name__} has neither {member_name!r} "
        f"nor {enum_name}.{member_name!r}"
    )
    raise AttributeError(msg)


def qgis_enum_value(cls, enum_name: str, member_name: str):
    """Prefer scoped PyQGIS enums, falling back to older QGIS 3 SIP aliases.

    This binding-only helper imports neither QGIS nor widgets, so background
    and infrastructure adapters can share it without depending on live UI.
    Zero-valued success codes, units and symbol properties are valid members.
    """
    enum_type = getattr(cls, enum_name, None)
    enum_value = getattr(enum_type, member_name, None) if enum_type is not None else None
    if enum_value is not None:
        return enum_value
    return qt_class_enum_value(cls, enum_name, member_name)


def optional_qt_enum_value(qt, enum_name: str, member_name: str):
    try:
        return qt_enum_value(qt, enum_name, member_name)
    except AttributeError:
        return None


__all__ = [
    "optional_qt_enum_value",
    "qgis_enum_value",
    "qt_class_enum_value",
    "qt_enum_value",
]
