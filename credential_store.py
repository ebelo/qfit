"""Compatibility shim for qfit credential storage helpers.

Prefer importing from ``qfit.configuration.infrastructure.credential_store``.
This module remains as a stable forwarding import during the package move.
"""

from .configuration.infrastructure.credential_store import (
    KEYRING_SERVICE,
    CredentialStore,
    InMemoryCredentialStore,
    KeyringCredentialStore,
    NullCredentialStore,
    make_credential_store,
)

__all__ = [
    "KEYRING_SERVICE",
    "CredentialStore",
    "InMemoryCredentialStore",
    "KeyringCredentialStore",
    "NullCredentialStore",
    "make_credential_store",
]
