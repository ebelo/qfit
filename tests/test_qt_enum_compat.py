import unittest

from tests import _path  # noqa: F401

from qfit.ui.qt_enum_compat import optional_qt_enum_value, qt_enum_value


class _FlatQt:
    Horizontal = 1


class _NestedQt:
    class Orientation:
        Horizontal = 2


class QtEnumCompatTest(unittest.TestCase):
    def test_resolves_qt5_flat_enum_member(self):
        self.assertEqual(qt_enum_value(_FlatQt, "Orientation", "Horizontal"), 1)

    def test_resolves_qt6_nested_enum_member(self):
        self.assertEqual(qt_enum_value(_NestedQt, "Orientation", "Horizontal"), 2)

    def test_optional_resolver_returns_none_for_missing_member(self):
        self.assertIsNone(optional_qt_enum_value(_NestedQt, "FocusPolicy", "NoFocus"))


if __name__ == "__main__":
    unittest.main()
