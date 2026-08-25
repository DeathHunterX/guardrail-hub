"""Ports for the credential setup workflow (hexagonal boundary).

These Protocols describe the collaborators the :class:`CredentialSetupService`
depends on, without binding it to any concrete I/O mechanism. Concrete
implementations live in :mod:`app.intelligence.setup.adapters`; tests supply
in-memory fakes.

Keeping these as ports is what lets the setup workflow be exercised without a
real terminal, without the AWS SDK, and without an OS keyring — the secret
never has to pass through a real TTY to be tested.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class SecretPrompt(Protocol):
    """Reads a secret from the operator using hidden (non-echoed) input.

    Implementations MUST NOT echo the typed characters, and MUST NOT log,
    persist, or otherwise expose the returned value. The returned string is
    handed straight to the CredentialStore by the service and then discarded.
    """

    def read_secret(self, prompt_text: str) -> str:
        """Return the secret entered by the operator (may be empty)."""
        ...


@runtime_checkable
class AwsCredentialDetector(Protocol):
    """Detects whether the AWS SDK credential chain can resolve credentials.

    This is a presence check only. Implementations MUST NOT read, return, or
    log the actual AWS credential values — Bedrock authentication is delegated
    entirely to the AWS SDK at runtime (never to the CredentialStore).
    """

    def is_available(self) -> bool:
        """Return True if the AWS credential chain resolves to usable credentials."""
        ...


@runtime_checkable
class OutputWriter(Protocol):
    """Sink for the command's user-facing output.

    This is presentation output (the command's stdout contract), not
    operational logging: it never carries a secret, so it does not go through
    ``MCPLogger``. Tests inject a buffer to assert on the rendered lines.
    """

    def write_line(self, text: str) -> None:
        """Write a single line of user-facing output."""
        ...


__all__ = [
    "AwsCredentialDetector",
    "OutputWriter",
    "SecretPrompt",
]
