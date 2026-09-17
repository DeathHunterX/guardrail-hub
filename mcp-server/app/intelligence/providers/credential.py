"""Runtime-only authentication material for provider adapters.

This module defines :class:`ProviderCredential`, the object that carries a
resolved secret (an API key) from the :class:`CredentialStore` into a provider
runtime. It exists ONLY on the provider runtime / bootstrap path.

Hard boundaries (enforced by design, verified by the Phase 3 security tests):

* A ``ProviderCredential`` is created by the :class:`ProviderManager` while
  initializing a provider, and attached to the adapter before ``initialize()``.
* It MUST NOT be placed in the ModelCatalog, ModelRecord, ProviderRecord,
  RoutingDecision, or ChatOptions.
* Its value MUST NOT appear in logs or in exception messages. The ``repr`` and
  ``str`` of this object are masked so that accidental interpolation of the
  object itself (``f"{credential}"``, ``logging`` calls, exception text) never
  leaks the secret.

Only the adapter that actually authenticates reads the raw value via the
``api_key`` attribute, at the moment it builds its HTTP client.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar


@dataclass(frozen=True, slots=True, repr=False)
class ProviderCredential:
    """A resolved API-key credential scoped to a single provider.

    Attributes:
        api_key: The secret API key resolved from the CredentialStore. Read
            only by the provider adapter when constructing its authenticated
            client.

    The value is deliberately masked in ``repr`` / ``str`` so that logging or
    interpolating the credential object never reveals the secret.
    """

    api_key: str

    # Masked representation used everywhere the object itself is stringified.
    # Declared as ClassVar so the dataclass never treats it as a field.
    _MASK: ClassVar[str] = "********"

    def __repr__(self) -> str:
        # Never reveal the secret value in diagnostics or tracebacks.
        return f"ProviderCredential(api_key={self._MASK})"

    # str() and f-string formatting fall back to the masked repr as well.
    __str__ = __repr__
