import unittest
from unittest.mock import MagicMock

from tests import _path  # noqa: F401

from qfit.atlas.profile_backend_policy import (
    DEFAULT_PROFILE_BACKEND_POLICY,
    ProfileBackendDecision,
    ProfileBackendPolicy,
)


class _NativeConfigStub:
    def __init__(self, *, atlas_driven=False):
        self.atlas_driven = atlas_driven


class TestProfileBackendPolicy(unittest.TestCase):
    def test_decide_uses_native_layout_for_atlas_driven_config(self):
        policy = ProfileBackendPolicy()

        decision = policy.decide(_NativeConfigStub(atlas_driven=True))

        self.assertEqual(
            decision,
            ProfileBackendDecision(layout_backend="native", render_backend="native-item"),
        )
        self.assertTrue(decision.uses_native_layout_item)
        self.assertFalse(decision.uses_picture_layout_item)

    def test_decide_uses_picture_svg_for_manual_updates(self):
        policy = ProfileBackendPolicy()

        decision = policy.decide(_NativeConfigStub(atlas_driven=False))

        self.assertEqual(
            decision,
            ProfileBackendDecision(layout_backend="picture", render_backend="svg"),
        )
        self.assertTrue(decision.uses_picture_layout_item)
        self.assertTrue(decision.prefers_svg_rendering)
        self.assertTrue(decision.allows_native_image_fallback)

    def test_policy_helper_methods_match_adapter_kind(self):
        picture_adapter = MagicMock(kind="picture")
        picture_adapter.supports_native_profile = False
        picture_adapter.atlas_driven = False
        native_manual_adapter = MagicMock(kind="native")
        native_manual_adapter.supports_native_profile = True
        native_manual_adapter.atlas_driven = False
        native_atlas_adapter = MagicMock(kind="native")
        native_atlas_adapter.supports_native_profile = True
        native_atlas_adapter.atlas_driven = True

        self.assertTrue(DEFAULT_PROFILE_BACKEND_POLICY.should_render_svg(picture_adapter))
        self.assertTrue(DEFAULT_PROFILE_BACKEND_POLICY.should_try_native_image_fallback(picture_adapter, "curve"))
        self.assertFalse(DEFAULT_PROFILE_BACKEND_POLICY.should_try_native_image_fallback(picture_adapter, None))
        self.assertTrue(DEFAULT_PROFILE_BACKEND_POLICY.requires_manual_native_binding(native_manual_adapter))
        self.assertTrue(DEFAULT_PROFILE_BACKEND_POLICY.should_configure_atlas_native_ranges(native_atlas_adapter))
        self.assertFalse(DEFAULT_PROFILE_BACKEND_POLICY.requires_manual_native_binding(native_atlas_adapter))


if __name__ == "__main__":
    unittest.main()
