import unittest

from tests import _path  # noqa: F401

from qfit.ui.application.workflow_settings import (
    COLLAPSED_GROUPS_KEY,
    DEFAULT_COLLAPSED_GROUP_OBJECT_NAMES,
    LAST_STEP_INDEX_KEY,
    LAST_STEP_INDEX_USER_SELECTED_KEY,
    WORKFLOW_SETTINGS_VERSION,
    WORKFLOW_SETTINGS_VERSION_KEY,
    WorkflowSettingsSnapshot,
    clamp_workflow_step_index,
    ensure_workflow_settings,
    load_workflow_settings,
    preferred_current_key_from_workflow_settings,
    save_workflow_step_index,
    workflow_step_key_for_index,
)
from qfit.ui.application.wizard_settings import (
    WIZARD_VERSION,
    WIZARD_VERSION_KEY,
    WizardSettingsSnapshot,
    ensure_wizard_settings,
    load_wizard_settings,
    save_last_step_index,
)


class FakeSettingsPort:
    def __init__(self, values=None):
        self.values = dict(values or {})
        self.writes = []

    def get(self, key, default=None):
        return self.values.get(key, default)

    def set(self, key, value):
        self.values[key] = value
        self.writes.append((key, value))


class WorkflowSettingsTests(unittest.TestCase):
    def test_load_defaults_match_first_launch_workflow_spec(self):
        snapshot = load_workflow_settings(FakeSettingsPort())

        self.assertIsNone(snapshot.settings_version)
        self.assertIsNone(snapshot.wizard_version)
        self.assertTrue(snapshot.first_launch)
        self.assertEqual(snapshot.last_step_index, 0)
        self.assertFalse(snapshot.last_step_index_user_selected)
        self.assertEqual(snapshot.collapsed_groups, DEFAULT_COLLAPSED_GROUP_OBJECT_NAMES)

    def test_ensure_writes_workflow_defaults_to_existing_storage_keys(self):
        settings = FakeSettingsPort()

        snapshot = ensure_workflow_settings(settings)

        self.assertEqual(snapshot.settings_version, WORKFLOW_SETTINGS_VERSION)
        self.assertTrue(snapshot.first_launch)
        self.assertEqual(
            settings.writes,
            [
                (WORKFLOW_SETTINGS_VERSION_KEY, WORKFLOW_SETTINGS_VERSION),
                (COLLAPSED_GROUPS_KEY, list(DEFAULT_COLLAPSED_GROUP_OBJECT_NAMES)),
            ],
        )

    def test_existing_legacy_storage_values_load_as_workflow_settings(self):
        settings = FakeSettingsPort(
            {
                WORKFLOW_SETTINGS_VERSION_KEY: "1",
                LAST_STEP_INDEX_KEY: "3",
                LAST_STEP_INDEX_USER_SELECTED_KEY: "true",
                COLLAPSED_GROUPS_KEY: ["temporalGroup"],
            }
        )

        snapshot = load_workflow_settings(settings)

        self.assertFalse(snapshot.first_launch)
        self.assertEqual(snapshot.settings_version, 1)
        self.assertEqual(snapshot.last_step_index, 3)
        self.assertTrue(snapshot.last_step_index_user_selected)
        self.assertEqual(snapshot.collapsed_groups, ("temporalGroup",))

    def test_step_index_is_clamped_for_restore_and_save(self):
        settings = FakeSettingsPort({LAST_STEP_INDEX_KEY: "99"})
        self.assertEqual(load_workflow_settings(settings).last_step_index, 4)
        self.assertEqual(clamp_workflow_step_index("bad"), 0)
        self.assertEqual(clamp_workflow_step_index(-2), 0)

        saved = save_workflow_step_index(settings, 8)

        self.assertEqual(saved, 4)
        self.assertEqual(settings.values[LAST_STEP_INDEX_KEY], 4)
        self.assertTrue(settings.values[LAST_STEP_INDEX_USER_SELECTED_KEY])

    def test_persisted_step_index_maps_to_stable_workflow_key(self):
        self.assertEqual(workflow_step_key_for_index(2), "map")
        self.assertEqual(workflow_step_key_for_index(99), "atlas")

    def test_existing_settings_restore_preferred_current_key(self):
        snapshot = load_workflow_settings(
            FakeSettingsPort(
                {
                    WORKFLOW_SETTINGS_VERSION_KEY: WORKFLOW_SETTINGS_VERSION,
                    LAST_STEP_INDEX_KEY: 3,
                }
            )
        )

        self.assertEqual(
            preferred_current_key_from_workflow_settings(snapshot),
            "analysis",
        )

    def test_wizard_wrapper_preserves_legacy_api_and_aliases(self):
        settings = FakeSettingsPort()
        wrapper_snapshot = ensure_wizard_settings(settings)

        self.assertIs(WizardSettingsSnapshot, WorkflowSettingsSnapshot)
        self.assertEqual(WIZARD_VERSION, WORKFLOW_SETTINGS_VERSION)
        self.assertEqual(WIZARD_VERSION_KEY, WORKFLOW_SETTINGS_VERSION_KEY)
        reloaded_snapshot = load_wizard_settings(settings)
        self.assertTrue(wrapper_snapshot.first_launch)
        self.assertFalse(reloaded_snapshot.first_launch)
        self.assertEqual(reloaded_snapshot.settings_version, WORKFLOW_SETTINGS_VERSION)
        self.assertEqual(wrapper_snapshot.wizard_version, WORKFLOW_SETTINGS_VERSION)
        self.assertEqual(save_last_step_index(settings, 2), 2)
        self.assertEqual(settings.values[LAST_STEP_INDEX_KEY], 2)

    def test_snapshot_accepts_legacy_wizard_version_keyword(self):
        snapshot = WizardSettingsSnapshot(wizard_version=WORKFLOW_SETTINGS_VERSION)

        self.assertEqual(snapshot.settings_version, WORKFLOW_SETTINGS_VERSION)
        self.assertEqual(snapshot.wizard_version, WORKFLOW_SETTINGS_VERSION)


if __name__ == "__main__":
    unittest.main()
