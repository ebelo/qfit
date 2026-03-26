import unittest

from tests import _path  # noqa: F401

from qfit.activity_classification import (
    ACTIVITY_LABEL_FIELDS,
    activity_prefers_pace,
    canonical_activity_label,
    normalize_activity_type,
    ordered_canonical_activity_labels,
    preferred_activity_field,
    resolve_activity_family,
)


class NormalizeActivityTypeTests(unittest.TestCase):
    def test_lowercases_and_strips_specials(self):
        self.assertEqual(normalize_activity_type("TrailRun"), "trailrun")
        self.assertEqual(normalize_activity_type("Trail Run"), "trailrun")
        self.assertEqual(normalize_activity_type("Trail-Run"), "trailrun")
        self.assertEqual(normalize_activity_type("RIDE"), "ride")

    def test_empty_and_none_return_empty_string(self):
        self.assertEqual(normalize_activity_type(None), "")
        self.assertEqual(normalize_activity_type(""), "")
        self.assertEqual(normalize_activity_type("  "), "")

    def test_digits_preserved(self):
        self.assertEqual(normalize_activity_type("Run100"), "run100")


class CanonicalActivityLabelTests(unittest.TestCase):
    def test_prefers_sport_type_when_set(self):
        self.assertEqual(canonical_activity_label("Ride", "GravelRide"), "GravelRide")
        self.assertEqual(canonical_activity_label("Run", "TrailRun"), "TrailRun")

    def test_falls_back_to_activity_type(self):
        self.assertEqual(canonical_activity_label("Ride", None), "Ride")
        self.assertEqual(canonical_activity_label("Ride", ""), "Ride")
        self.assertEqual(canonical_activity_label("Ride", "   "), "Ride")

    def test_strips_non_empty_values(self):
        self.assertEqual(canonical_activity_label("  Ride  ", None), "Ride")
        self.assertEqual(canonical_activity_label("Run", "  Trail Run  "), "Trail Run")

    def test_returns_none_when_both_absent(self):
        self.assertIsNone(canonical_activity_label(None, None))
        self.assertIsNone(canonical_activity_label("", None))
        self.assertIsNone(canonical_activity_label(None, ""))


class PreferredActivityFieldTests(unittest.TestCase):
    def test_prefers_sport_type_when_available(self):
        self.assertEqual(preferred_activity_field(["name", "sport_type", "activity_type"]), "sport_type")

    def test_falls_back_to_activity_type(self):
        self.assertEqual(preferred_activity_field(["name", "activity_type"]), "activity_type")

    def test_uses_shared_field_priority_order(self):
        self.assertEqual(ACTIVITY_LABEL_FIELDS, ("sport_type", "activity_type"))

    def test_returns_none_when_neither_field_exists(self):
        self.assertIsNone(preferred_activity_field(["name", "distance_m"]))


class OrderedCanonicalActivityLabelsTests(unittest.TestCase):
    def test_prefers_sport_type_and_preserves_first_seen_order(self):
        labels = ordered_canonical_activity_labels([
            ("Ride", "GravelRide"),
            ("Run", "TrailRun"),
            ("Ride", None),
        ])
        self.assertEqual(labels, ["GravelRide", "TrailRun", "Ride"])

    def test_deduplicates_case_insensitively_after_normalization(self):
        labels = ordered_canonical_activity_labels([
            ("Ride", "Trail Run"),
            ("Ride", "trail-run"),
            ("Ride", "TRAILRUN"),
        ])
        self.assertEqual(labels, ["Trail Run"])

    def test_skips_blank_pairs(self):
        labels = ordered_canonical_activity_labels([
            (None, None),
            ("", "   "),
            ("Ride", None),
        ])
        self.assertEqual(labels, ["Ride"])


class ResolveActivityFamilyTests(unittest.TestCase):
    def test_known_types_resolve_to_correct_family(self):
        self.assertEqual(resolve_activity_family("Run"), "running")
        self.assertEqual(resolve_activity_family("TrailRun"), "running")
        self.assertEqual(resolve_activity_family("EveningJog"), "running")
        self.assertEqual(resolve_activity_family("Ride"), "cycling")
        self.assertEqual(resolve_activity_family("GravelRide"), "cycling")
        self.assertEqual(resolve_activity_family("Hike"), "walking")
        self.assertEqual(resolve_activity_family("Walk"), "walking")
        self.assertEqual(resolve_activity_family("AlpineSki"), "winter")
        self.assertEqual(resolve_activity_family("Snowshoe"), "winter")
        self.assertEqual(resolve_activity_family("Swim"), "water")
        self.assertEqual(resolve_activity_family("Kitesurf"), "water")
        self.assertEqual(resolve_activity_family("RockClimbing"), "mountain")
        self.assertEqual(resolve_activity_family("Workout"), "fitness")
        self.assertEqual(resolve_activity_family("VirtualRide"), "machine")
        self.assertEqual(resolve_activity_family("BikeCommute"), "machine")

    def test_machine_family_wins_over_cycling_for_commute(self):
        # "commute" token takes priority over "ride" / "bike"
        self.assertEqual(resolve_activity_family("BikeCommute"), "machine")
        self.assertEqual(resolve_activity_family("EBikeRide"), "machine")

    def test_unknown_and_empty_default_to_machine(self):
        self.assertEqual(resolve_activity_family("SomeRandomSport"), "machine")
        self.assertEqual(resolve_activity_family(None), "machine")
        self.assertEqual(resolve_activity_family(""), "machine")

    def test_normalisation_is_whitespace_and_case_insensitive(self):
        self.assertEqual(resolve_activity_family("TRAIL RUN"), "running")
        self.assertEqual(resolve_activity_family("trail-run"), "running")


class ActivityPrefersPaceTests(unittest.TestCase):
    def test_running_and_walking_prefer_pace(self):
        self.assertTrue(activity_prefers_pace("Run"))
        self.assertTrue(activity_prefers_pace("Walk"))
        self.assertTrue(activity_prefers_pace("Hike"))
        self.assertTrue(activity_prefers_pace("TrailRun"))

    def test_cycling_and_other_prefer_speed(self):
        self.assertFalse(activity_prefers_pace("Ride"))
        self.assertFalse(activity_prefers_pace("GravelRide"))
        self.assertFalse(activity_prefers_pace("Swim"))
        self.assertFalse(activity_prefers_pace(None))

    def test_sport_type_takes_priority_over_activity_type(self):
        # sport_type="TrailRun" should give pace even if activity_type="Run" (same family)
        self.assertTrue(activity_prefers_pace("Run", "TrailRun"))
        # sport_type overrides activity_type when they disagree on pace
        self.assertFalse(activity_prefers_pace("Run", "GravelRide"))

    def test_falls_back_to_activity_type_when_sport_type_absent(self):
        self.assertTrue(activity_prefers_pace("Run", None))
        self.assertFalse(activity_prefers_pace("Ride", None))


if __name__ == "__main__":
    unittest.main()
