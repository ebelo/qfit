import unittest

from tests import _path  # noqa: F401

from qfit.ui.application.wizard_settings import (
    COLLAPSED_GROUPS_KEY,
    DEFAULT_COLLAPSED_GROUP_OBJECT_NAMES,
    LAST_STEP_INDEX_KEY,
    WIZARD_VERSION,
    WIZARD_VERSION_KEY,
    clamp_wizard_step_index,
    ensure_wizard_settings,
    load_wizard_settings,
    preferred_current_key_from_settings,
    save_collapsed_groups,
    save_last_step_index,
    wizard_step_key_for_index,
)


class FakeSettingsPort:
    def __init__(self, values=None):
        self.values = dict(values or {})
        self.writes = []

    def get(self, key, default=None):
        return self.values.get(key, default)

    def get_bool(self, key, default=False):
        return bool(self.get(key, default))

    def set(self, key, value):
        self.values[key] = value
        self.writes.append((key, value))


class WizardSettingsTests(unittest.TestCase):
    def test_load_defaults_match_first_launch_wizard_spec(self):
        snapshot = load_wizard_settings(FakeSettingsPort())

        self.assertIsNone(snapshot.wizard_version)
        self.assertTrue(snapshot.first_launch)
        self.assertEqual(snapshot.last_step_index, 0)
        self.assertEqual(snapshot.collapsed_groups, DEFAULT_COLLAPSED_GROUP_OBJECT_NAMES)

    def test_ensure_writes_version_and_collapsed_defaults_on_first_launch(self):
        settings = FakeSettingsPort()

        snapshot = ensure_wizard_settings(settings)

        self.assertEqual(snapshot.wizard_version, WIZARD_VERSION)
        self.assertTrue(snapshot.first_launch)
        self.assertEqual(
            settings.writes,
            [
                (WIZARD_VERSION_KEY, WIZARD_VERSION),
                (COLLAPSED_GROUPS_KEY, list(DEFAULT_COLLAPSED_GROUP_OBJECT_NAMES)),
            ],
        )

    def test_ensure_does_not_overwrite_existing_wizard_settings(self):
        settings = FakeSettingsPort(
            {
                WIZARD_VERSION_KEY: "1",
                LAST_STEP_INDEX_KEY: "3",
                COLLAPSED_GROUPS_KEY: ["temporalGroup"],
            }
        )

        snapshot = ensure_wizard_settings(settings)

        self.assertFalse(snapshot.first_launch)
        self.assertEqual(snapshot.wizard_version, 1)
        self.assertEqual(snapshot.last_step_index, 3)
        self.assertEqual(snapshot.collapsed_groups, ("temporalGroup",))
        self.assertEqual(settings.writes, [])

    def test_step_index_is_clamped_for_restore_and_save(self):
        settings = FakeSettingsPort({LAST_STEP_INDEX_KEY: "99"})
        self.assertEqual(load_wizard_settings(settings).last_step_index, 4)
        self.assertEqual(clamp_wizard_step_index("bad"), 0)
        self.assertEqual(clamp_wizard_step_index(-2), 0)

        saved = save_last_step_index(settings, 8)

        self.assertEqual(saved, 4)
        self.assertEqual(settings.values[LAST_STEP_INDEX_KEY], 4)

    def test_collapsed_groups_are_saved_in_known_spec_order(self):
        settings = FakeSettingsPort()

        saved = save_collapsed_groups(
            settings,
            ["unknownGroup", "temporalGroup", "advancedOptionsGroup"],
        )

        self.assertEqual(saved, ("advancedOptionsGroup", "temporalGroup"))
        self.assertEqual(
            settings.values[COLLAPSED_GROUPS_KEY],
            ["advancedOptionsGroup", "temporalGroup"],
        )

    def test_collapsed_groups_accept_qsettings_comma_string_values(self):
        settings = FakeSettingsPort(
            {COLLAPSED_GROUPS_KEY: "temporalGroup, layoutGroup, unknownGroup"}
        )

        snapshot = load_wizard_settings(settings)

        self.assertEqual(snapshot.collapsed_groups, ("layoutGroup", "temporalGroup"))

    def test_persisted_step_index_maps_to_stable_wizard_key(self):
        self.assertEqual(wizard_step_key_for_index(2), "map")
        self.assertEqual(wizard_step_key_for_index(99), "atlas")

    def test_first_launch_has_no_preferred_current_key(self):
        snapshot = load_wizard_settings(FakeSettingsPort())

        self.assertIsNone(preferred_current_key_from_settings(snapshot))

    def test_existing_settings_restore_preferred_current_key(self):
        snapshot = load_wizard_settings(
            FakeSettingsPort({WIZARD_VERSION_KEY: WIZARD_VERSION, LAST_STEP_INDEX_KEY: 3})
        )

        self.assertEqual(preferred_current_key_from_settings(snapshot), "analysis")


if __name__ == "__main__":
    unittest.main()
