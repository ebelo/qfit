from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProfileBackendDecision:
    """Chosen profile backend for a layout item / page update flow."""

    layout_backend: str
    render_backend: str

    @property
    def uses_native_layout_item(self) -> bool:
        return self.layout_backend == "native"

    @property
    def uses_picture_layout_item(self) -> bool:
        return self.layout_backend == "picture"

    @property
    def prefers_svg_rendering(self) -> bool:
        return self.render_backend == "svg"

    @property
    def allows_native_image_fallback(self) -> bool:
        return self.render_backend in {"svg", "native-image"}


class ProfileBackendPolicy:
    """Centralize atlas profile backend decisions.

    Current qfit production policy:
    - atlas-driven line coverage layers use the native QGIS layout item
    - polygon/manual per-page updates use a picture-backed layout item
    - picture-backed items prefer qfit SVG rendering and may fall back to
      synchronous native image rendering when a usable 3D curve exists
    """

    def decide(self, native_config=None) -> ProfileBackendDecision:
        atlas_driven = bool(getattr(native_config, "atlas_driven", False))
        if atlas_driven:
            return ProfileBackendDecision(layout_backend="native", render_backend="native-item")
        return ProfileBackendDecision(layout_backend="picture", render_backend="svg")

    def should_use_native_item(self, native_config=None) -> bool:
        return self.decide(native_config).uses_native_layout_item

    def should_render_svg(self, profile_adapter) -> bool:
        supports_native_profile = getattr(profile_adapter, "supports_native_profile", None)
        if isinstance(supports_native_profile, bool):
            return not supports_native_profile
        return getattr(profile_adapter, "kind", None) == "picture"

    def should_try_native_image_fallback(self, profile_adapter, native_curve) -> bool:
        return self.should_render_svg(profile_adapter) and native_curve is not None

    def should_configure_atlas_native_ranges(self, profile_adapter) -> bool:
        return bool(
            getattr(profile_adapter, "supports_native_profile", False)
            and getattr(profile_adapter, "atlas_driven", False)
        )

    def requires_manual_native_binding(self, profile_adapter) -> bool:
        return bool(
            getattr(profile_adapter, "supports_native_profile", False)
            and not getattr(profile_adapter, "atlas_driven", False)
        )


DEFAULT_PROFILE_BACKEND_POLICY = ProfileBackendPolicy()
