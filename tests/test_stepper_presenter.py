import unittest

from tests import _path  # noqa: F401

from qfit.ui.application.dock_workflow_sections import (
    DockWorkflowStepState,
    build_wizard_step_statuses,
)
from qfit.ui.application.stepper_presenter import (
    STEPPER_STATE_CURRENT,
    STEPPER_STATE_DONE,
    STEPPER_STATE_LOCKED,
    STEPPER_STATE_UPCOMING,
    build_stepper_items,
    build_stepper_states,
    can_request_step,
    step_index_for_key,
    step_key_for_index,
)


class StepperPresenterTests(unittest.TestCase):
    def test_maps_workflow_states_to_stepper_bar_contract(self):
        statuses = build_wizard_step_statuses(
            current_key="map",
            completed_keys={"connection", "sync"},
            unlocked_keys={"analysis"},
        )

        items = build_stepper_items(statuses)

        self.assertEqual(
            [(item.key, item.index, item.label, item.state, item.enabled) for item in items],
            [
                ("connection", 0, "Connection", STEPPER_STATE_DONE, True),
                ("sync", 1, "Synchronization", STEPPER_STATE_DONE, True),
                ("map", 2, "Map & filters", STEPPER_STATE_CURRENT, True),
                ("analysis", 3, "Spatial analysis (optional)", STEPPER_STATE_UPCOMING, True),
                ("atlas", 4, "Atlas PDF", STEPPER_STATE_LOCKED, False),
            ],
        )
        self.assertEqual(
            [status.state for status in statuses],
            [
                DockWorkflowStepState.DONE,
                DockWorkflowStepState.DONE,
                DockWorkflowStepState.CURRENT,
                DockWorkflowStepState.UNLOCKED,
                DockWorkflowStepState.LOCKED,
            ],
        )

    def test_build_stepper_states_returns_set_state_values_in_order(self):
        statuses = build_wizard_step_statuses(current_key="connection")

        self.assertEqual(
            build_stepper_states(statuses),
            (
                STEPPER_STATE_CURRENT,
                STEPPER_STATE_LOCKED,
                STEPPER_STATE_LOCKED,
                STEPPER_STATE_LOCKED,
                STEPPER_STATE_LOCKED,
            ),
        )

    def test_can_request_step_rejects_only_locked_steps(self):
        statuses = build_wizard_step_statuses(
            current_key="map",
            completed_keys={"connection", "sync"},
            unlocked_keys={"analysis"},
        )

        self.assertTrue(can_request_step(statuses, 0))
        self.assertTrue(can_request_step(statuses, 2))
        self.assertTrue(can_request_step(statuses, 3))
        self.assertFalse(can_request_step(statuses, 4))

    def test_step_index_key_helpers_use_stable_wizard_order(self):
        self.assertEqual(step_key_for_index(0), "connection")
        self.assertEqual(step_key_for_index(4), "atlas")
        self.assertEqual(step_index_for_key("map"), 2)

    def test_step_index_key_helpers_reject_unknown_values(self):
        with self.assertRaises(IndexError):
            step_key_for_index(-1)
        with self.assertRaises(IndexError):
            step_key_for_index(99)
        with self.assertRaises(KeyError):
            step_index_for_key("unknown")
        with self.assertRaises(IndexError):
            can_request_step(build_wizard_step_statuses(current_key="connection"), 99)


if __name__ == "__main__":
    unittest.main()
