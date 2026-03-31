import unittest

from tests import _path  # noqa: F401

from qfit.activity_classification import normalize_activity_type as legacy_normalize_activity_type
from qfit.activity_query import ActivityQuery as LegacyActivityQuery
from qfit.activities.domain.activity_classification import normalize_activity_type
from qfit.activities.domain.activity_query import ActivityQuery
from qfit.activities.domain.models import Activity
from qfit.models import Activity as LegacyActivity


class ActivityDomainCompatibilityTests(unittest.TestCase):
    def test_legacy_and_domain_activity_model_are_the_same_dataclass(self):
        self.assertIs(LegacyActivity, Activity)

    def test_legacy_and_domain_query_types_are_the_same_class(self):
        self.assertIs(LegacyActivityQuery, ActivityQuery)

    def test_legacy_and_domain_classification_helpers_match(self):
        self.assertIs(legacy_normalize_activity_type, normalize_activity_type)
        self.assertEqual(normalize_activity_type("Trail Run"), "trailrun")


if __name__ == "__main__":
    unittest.main()
