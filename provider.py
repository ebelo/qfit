"""Compatibility shim for provider contracts.

Prefer importing provider contracts from ``qfit.providers.domain``.
This module stays in place temporarily to keep older imports working while the
feature-oriented package layout settles.
"""

from .providers.domain.provider import ActivityProvider, ProviderError

__all__ = ["ActivityProvider", "ProviderError"]
