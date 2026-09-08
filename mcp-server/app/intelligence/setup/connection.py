"""One-provider connection testing for the setup command.

This is intentionally independent of ProviderManager and application bootstrap:
setup constructs, exercises, and closes exactly one selected adapter.
"""

from __future__ import annotations

import asyncio
import inspect
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from app.intelligence.providers.base_provider import BaseProviderRuntime
from app.intelligence.providers.credential import ProviderCredential
from app.intelligence.providers.provider_factory import ProviderFactory
from app.intelligence.registry.models.provider import AuthType, ProviderRecord


class ConnectionState(str, Enum):
    NOT_TESTED = "not_tested"
    READY = "ready"
    FAILED = "failed"
    UNSUPPORTED = "unsupported"


@dataclass(frozen=True, slots=True)
class ConnectionResult:
    state: ConnectionState
    detail: str = ""


class ProviderConnectionTester:
    """Exercise a selected provider without starting the MCP application."""

    def __init__(self, *, factory: ProviderFactory) -> None:
        self._factory = factory

    def test(
        self,
        provider: ProviderRecord,
        *,
        candidate_credential: Optional[str] = None,
    ) -> ConnectionResult:
        """Return a secret-free probe result and always close started resources."""
        return asyncio.run(self._test_async(provider, candidate_credential))

    async def _test_async(
        self, provider: ProviderRecord, candidate_credential: Optional[str]
    ) -> ConnectionResult:
        adapter = None
        started = False
        try:
            adapter = self._factory.create(provider)
            if provider.auth.type is AuthType.API_KEY:
                if not candidate_credential:
                    return ConnectionResult(ConnectionState.FAILED, "Credential is missing")
                attach = getattr(adapter, "attach_credential", None)
                if attach is None:
                    return ConnectionResult(ConnectionState.UNSUPPORTED, "Credential probe unsupported")
                attach(ProviderCredential(api_key=candidate_credential))

            initialize = getattr(adapter, "initialize", None)
            if initialize is not None:
                initialize()
            adapter.validate_configuration()
            await adapter.start()
            started = True
            probe = getattr(adapter, "check_connection", None)
            if probe is None:
                return ConnectionResult(ConnectionState.UNSUPPORTED, "Connection test unsupported")
            outcome = probe()
            if inspect.isawaitable(outcome):
                outcome = await outcome
            if outcome is True:
                return ConnectionResult(ConnectionState.READY, "Connection successful")
            if outcome is False:
                return ConnectionResult(ConnectionState.FAILED, "Connection failed")
            healthy = getattr(outcome, "healthy", None)
            if healthy is True:
                return ConnectionResult(ConnectionState.READY, "Connection successful")
            if healthy is False:
                return ConnectionResult(ConnectionState.FAILED, "Connection failed")
            return ConnectionResult(ConnectionState.UNSUPPORTED, "Connection test unsupported")
        except Exception as exc:  # Deliberately do not expose provider exception text.
            return ConnectionResult(
                ConnectionState.FAILED,
                f"Connection failed ({type(exc).__name__})",
            )
        finally:
            if adapter is not None and started:
                close = getattr(adapter, "close", None)
                if close is not None:
                    try:
                        outcome = close()
                        if inspect.isawaitable(outcome):
                            await outcome
                    except Exception:
                        pass
            if candidate_credential is not None:
                del candidate_credential


__all__ = ["ConnectionResult", "ConnectionState", "ProviderConnectionTester"]
